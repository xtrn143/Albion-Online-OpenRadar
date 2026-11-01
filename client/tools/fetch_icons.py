"""把玩家可见装备槽的全部图标预下载到 data/icons，供离线打包使用。

用法（在 client/ 目录下）：
    python tools/fetch_icons.py              # 默认 48px、8 线程，可断点续跑
    python tools/fetch_icons.py --size 64    # 换分辨率（会重下，因为文件名不变会跳过）

只覆盖玩家身上实际会出现的槽位（武器/副手/头/胸/脚/披风/坐骑/背包/药水食物），
不下载资源、家具、采集工具等永远不可能出现在装备栏的物品。
"""
from __future__ import annotations

import argparse
import io
import json
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

CATS = {
    "weapons", "offhands", "head", "armors", "shoes",
    "capes", "mounts", "bags", "consumables",
}
# 渲染服务不加任何查询参数才稳定；@ 是附魔分隔符，不能编码成 %40
RENDER_URL = "https://render.albiononline.com/v1/item/{name}.png"
ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "AlbionAware/0.1 (+https://portaler.pages.dev/)"


def slug(unique: str) -> str:
    return urllib.parse.quote(unique, safe='@')


def target_names(items: list) -> list[str]:
    return [e["n"] for e in items if e and e.get("n") and e.get("cat") in CATS]


def fetch_one(session: requests.Session, name: str, size: int, out_dir: Path) -> bool:
    dest = out_dir / f"{slug(name)}.png"
    if dest.exists():
        return True
    try:
        response = session.get(RENDER_URL.format(name=slug(name)), timeout=15)
    except requests.RequestException:
        return False
    if response.status_code != 200:
        return False
    try:
        image = Image.open(io.BytesIO(response.content)).convert("RGBA")
    except OSError:
        return False
    image.thumbnail((size, size), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(buffer.getvalue())
    tmp.replace(dest)
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="预下载物品图标")
    parser.add_argument("--size", type=int, default=48)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args(argv)

    items = json.loads((ROOT / "data" / "items.min.json").read_text(encoding="utf-8"))
    names = target_names(items)
    out_dir = ROOT / "data" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [name for name in names if not (out_dir / f"{slug(name)}.png").exists()]
    print(f"目标 {len(names)} 个物品，已存在 {len(names) - len(todo)} 个，待下载 {len(todo)} 个")

    local = threading.local()

    def worker(name: str) -> bool:
        session = getattr(local, "session", None)
        if session is None:
            session = local.session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
        for _ in range(args.retries + 1):
            if fetch_one(session, name, args.size, out_dir):
                return True
            time.sleep(0.3)
        return False

    failed: list[str] = []
    started = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        for index, ok in enumerate(pool.map(worker, todo), 1):
            if not ok:
                failed.append(todo[index - 1])
            if index % 200 == 0:
                rate = index / max(time.time() - started, 1e-6)
                print(f"{index}/{len(todo)} 已处理（{rate:.1f}/s，失败 {len(failed)}）", flush=True)

    total = sum(1 for p in out_dir.glob("*.png"))
    print(f"完成：目录内 {total} 个图标，失败 {len(failed)} 个，用时 {time.time() - started:.0f}s")
    if failed:
        print("失败示例：" + ", ".join(failed[:10]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

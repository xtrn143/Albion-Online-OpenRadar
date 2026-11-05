"""生成阿瓦隆查图索引：合并 zones.json 与地图图库，复制/下载 webp 截图。

用法（在 client/ 目录下）：
    python tools/sync_avalon_maps.py                  # 本地图库优先，缺图自动下载
    python tools/sync_avalon_maps.py --no-download    # 只用本机已有的 webp，不联网

图库默认为 D:\\work\\avalon-gold-finder\\public；若本机没有 data.json，
会退回到 https://portaler.pages.dev 下载，避免写出没有图标和截图的空索引。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))

from albion_aware.map_index import build_index_records, key3  # noqa: E402

ZONES = ROOT / "web" / "ao-bin-dumps" / "zones.json"
DEST = ROOT / "client" / "data" / "avalon"
DEFAULT_SOURCE = Path(r"D:\work\avalon-gold-finder\public")
REMOTE = "https://portaler.pages.dev"
USER_AGENT = "AlbionAware/0.1 (+https://portaler.pages.dev/)"


def _fetch_json(url: str) -> list:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _download(filename: str, target: Path) -> bool:
    url = f"{REMOTE}/maps/{quote(filename, safe='')}"
    part = target.with_name(target.name + ".part")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            part.write_bytes(response.read())
        payload = part.read_bytes()
        if not payload or not payload.startswith(b"RIFF"):
            raise ValueError("payload is not a webp file")
        part.replace(target)
        return True
    except (OSError, ValueError, URLError) as error:  # 网络失败不应阻断打包
        print(f"download failed: {filename}: {error}")
        part.unlink(missing_ok=True)
        return False


def sync(source: Path, dest: Path, zones_path: Path, allow_download: bool = True) -> dict:
    zones = json.loads(zones_path.read_text(encoding="utf-8"))
    gallery_path = source / "data.json"
    if gallery_path.exists():
        gallery = json.loads(gallery_path.read_text(encoding="utf-8"))
    elif allow_download:
        print(f"gallery missing locally, downloading {REMOTE}/data.json")
        try:
            gallery = _fetch_json(f"{REMOTE}/data.json")
        except (OSError, ValueError, URLError) as error:
            raise SystemExit(f"gallery missing: {gallery_path}: {error}")
    else:
        raise SystemExit(f"gallery missing: {gallery_path}")
    if not gallery:
        raise SystemExit(f"gallery missing or empty: {gallery_path}")

    records = build_index_records(zones, gallery)
    if not records:
        raise SystemExit("no TNL zones found in zones.json")

    maps_dir = dest / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    available = missing = failures = 0
    for record in records:
        filename = record["imgFile"]
        if not filename:
            missing += 1
            continue
        if Path(filename).name != filename:
            raise SystemExit(f"unsafe image name: {filename}")
        target = maps_dir / filename
        if target.exists() and target.stat().st_size > 0:
            available += 1
            continue
        origin = source / "maps" / filename
        if origin.exists() and origin.stat().st_size > 0:
            shutil.copy2(origin, target)
            available += 1
        elif allow_download:
            if _download(filename, target):
                available += 1
                failures = 0
            else:
                missing += 1
                failures += 1
                if failures >= 10:
                    raise SystemExit("too many failed downloads; aborting index generation")
        else:
            missing += 1

    keys = Counter(key3(record["name"]) for record in records)
    collisions = {key: count for key, count in keys.items() if count > 1}
    if collisions:
        print(f"WARNING: {len(collisions)} duplicate 3-letter keys, first: {list(collisions)[:3]}")

    payload = {"version": 1, "maps": records}
    index_path = dest / "index.json"
    tmp_path = index_path.with_name(index_path.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp_path.replace(index_path)
    return {"maps": len(records), "images": available, "missing_images": missing,
            "key_collisions": len(collisions)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="生成阿瓦隆查图索引，并复制/下载地图截图。")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=DEST)
    parser.add_argument("--zones", type=Path, default=ZONES)
    parser.add_argument("--no-download", action="store_true")
    args = parser.parse_args()
    result = sync(args.source, args.dest, args.zones, allow_download=not args.no_download)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

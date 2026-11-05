"""生成阿瓦隆查图索引：合并 zones.json 与地图图库，复制/下载 webp 截图。"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))

from albion_aware.map_index import build_index_records, parts_of  # noqa: E402

ZONES = ROOT / "web" / "ao-bin-dumps" / "zones.json"
DEST = ROOT / "client" / "data" / "avalon"
DEFAULT_SOURCE = Path(r"D:\work\avalon-gold-finder\public")
REMOTE = "https://portaler.pages.dev"


def _download(filename: str, target: Path) -> bool:
    url = f"{REMOTE}/maps/{quote(filename, safe='')}"
    try:
        with urlopen(url, timeout=30) as response:
            target.write_bytes(response.read())
        return True
    except Exception as error:  # 网络失败不应阻断打包
        print(f"download failed: {filename}: {error}")
        return False


def sync(source: Path, dest: Path, zones_path: Path, allow_download: bool = True) -> dict:
    zones = json.loads(zones_path.read_text(encoding="utf-8"))
    gallery_path = source / "data.json"
    gallery = json.loads(gallery_path.read_text(encoding="utf-8")) if gallery_path.exists() else []
    records = build_index_records(zones, gallery)

    maps_dir = dest / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    available = missing = 0
    for record in records:
        filename = record["imgFile"]
        if not filename:
            missing += 1
            continue
        target = maps_dir / filename
        if target.exists():
            available += 1
            continue
        origin = source / "maps" / filename
        if origin.exists():
            shutil.copy2(origin, target)
            available += 1
        elif allow_download and _download(filename, target):
            available += 1
        else:
            missing += 1

    keys = Counter("".join(part[:3] for part in parts_of(record["name"]))
                   for record in records)
    collisions = {key: count for key, count in keys.items() if count > 1}
    if collisions:
        print(f"WARNING: {len(collisions)} duplicate 3-letter keys, first: {list(collisions)[:3]}")

    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "maps": records,
    }
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"maps": len(records), "images": available, "missing_images": missing,
            "key_collisions": len(collisions)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=DEST)
    parser.add_argument("--zones", type=Path, default=ZONES)
    parser.add_argument("--no-download", action="store_true")
    args = parser.parse_args()
    result = sync(args.source, args.dest, args.zones, allow_download=not args.no_download)
    print(json.dumps(result, ensure_ascii=False))
    if result["maps"] == 0:
        raise SystemExit("no TNL zones found in zones.json")


if __name__ == "__main__":
    main()

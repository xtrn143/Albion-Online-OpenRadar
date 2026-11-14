"""区域 PvP 等级：把 op41/op2 的 mapId 映射为 safe/yellow/red/black/unknown。"""
from __future__ import annotations

import json
from pathlib import Path

LEVELS = ("safe", "yellow", "red", "black")
DANGER = frozenset({"red", "black"})
ROADS_PREFIX = "TNL-"
MISTS_PREFIX = "@MISTS"


def build_level_map(zones: dict) -> dict[str, str]:
    """从 ao-bin-dumps zones.json 提取 {zoneId: pvpType}，阿瓦隆之路强制黑区。"""
    levels: dict[str, str] = {}
    for zone_id, zone in (zones or {}).items():
        if not isinstance(zone, dict):
            continue
        if str(zone.get("type") or "").startswith("TUNNEL_"):
            levels[str(zone_id).strip().upper()] = "black"
            continue
        level = str(zone.get("pvpType") or "").strip().lower()
        if level not in LEVELS:
            continue
        levels[str(zone_id).strip().upper()] = level
    return levels


class ZoneLevels:
    def __init__(self, levels: dict[str, str] | None = None):
        self._levels = dict(levels or {})

    @classmethod
    def load(cls, path) -> "ZoneLevels":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        zones = raw.get("zones") if isinstance(raw, dict) else None
        if not isinstance(zones, dict):
            return cls()
        return cls({str(key).upper(): str(value) for key, value in zones.items()
                    if str(value) in LEVELS})

    def level(self, zone_id, previous: str = "safe") -> str:
        if previous not in LEVELS and previous != "unknown":
            previous = "safe"
        zone = str(zone_id or "").strip().upper()
        if not zone or zone.startswith(MISTS_PREFIX):
            return previous
        if zone.startswith(ROADS_PREFIX):
            return "black"
        return self._levels.get(zone) or self._levels.get(zone.split("-", 1)[0]) or "unknown"


def is_danger(level: str) -> bool:
    return level in DANGER

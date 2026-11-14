"""区域 PvP 等级：把 op41/op2 的 mapId 映射为 safe/yellow/red/black/unknown。"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

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
            log.warning("zone level table unavailable: %s", path)
            return cls()
        zones = raw.get("zones") if isinstance(raw, dict) else None
        if not isinstance(zones, dict):
            log.warning("zone level table unavailable: %s", path)
            return cls()
        levels: dict[str, str] = {}
        for key, value in zones.items():
            level = str(value).strip().lower()
            if level in LEVELS:
                levels[str(key).strip().upper()] = level
        return cls(levels)

    def level(self, zone_id, previous: str = "safe") -> str:
        if previous not in LEVELS and previous != "unknown":
            previous = "safe"
        zone = str(zone_id or "").strip().upper()
        if not zone or zone.startswith(MISTS_PREFIX):
            return previous
        if zone.startswith(ROADS_PREFIX):
            return "black"
        return self._levels.get(zone) or self._levels.get(zone.split("-", 1)[0]) or "unknown"


def mist_level(zone_id, previous: str, lethal: bool | None) -> str:
    """迷雾等级：选过致命入口按黑区、非致命按黄区，没选过则继承进入前等级。"""
    if lethal is True:
        return "black"
    if lethal is False:
        return "yellow"
    return previous


def is_danger(level: str) -> bool:
    return level in DANGER

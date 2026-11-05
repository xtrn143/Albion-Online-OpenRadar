"""阿瓦隆区名索引：折叠归一化、速记键、三级匹配与排序。纯 Python，无 UI 依赖。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SEPARATOR = re.compile(r"[-_ ]+")
ROADS_ZONE = re.compile(r"TNL-\d+", re.IGNORECASE)
# 游戏字体里大写 I 与 l 难以区分，0/O、1/I 同理，统一折叠
CONFUSABLES = str.maketrans({"L": "I", "0": "O", "1": "I"})
TIER_BONUS = {8: 8, 6: 5, 4: 2}


def fold(text: str) -> str:
    return (text or "").upper().translate(CONFUSABLES)


def compact(text: str) -> str:
    return SEPARATOR.sub("", fold(text).strip())


def parts_of(name: str) -> tuple[str, ...]:
    return tuple(part for part in SEPARATOR.split(fold(name).strip()) if part)


def key3(name: str) -> str:
    return "".join(part[:3] for part in parts_of(name))


def is_roads_zone(zone_id: str | None) -> bool:
    return bool(zone_id) and bool(ROADS_ZONE.fullmatch(str(zone_id)))


def tokenize(text: str) -> tuple[list[str], str]:
    folded = fold(text).strip()
    return [part for part in SEPARATOR.split(folded) if part], SEPARATOR.sub("", folded)


@dataclass(frozen=True)
class MapEntry:
    name: str
    tier: int
    parts: tuple[str, ...]
    key3: str
    icons: tuple[tuple[str, int], ...]
    img_file: str
    zone_ids: tuple[str, ...]

    @property
    def has_gold(self) -> bool:
        return any(alt == "GOLD" for alt, _badge in self.icons)


@dataclass(frozen=True)
class MapHit:
    entry: MapEntry
    score: int
    matched_parts: int
    is_current: bool


def make_entry(name, tier=0, icons=(), img_file="", zone_ids=()) -> MapEntry:
    zones = tuple(str(zone).strip().upper() for zone in zone_ids if str(zone).strip())
    return MapEntry(
        name=str(name),
        tier=int(tier or 0),
        parts=parts_of(name),
        key3=key3(name),
        icons=tuple(icons),
        img_file=str(img_file or ""),
        zone_ids=zones,
    )


def token_prefix_match(tokens, parts) -> int:
    """每个 token 必须是同位置段的前缀；返回命中的段数，0 表示不匹配。"""
    if not tokens or len(tokens) > len(parts):
        return 0
    for token, part in zip(tokens, parts):
        if not part.startswith(token):
            return 0
    return len(tokens)


def _dp_value(state) -> int:
    parts_matched, chars, threes = state
    return 40 * chars + 30 * parts_matched + 5 * threes


def compact_prefix_match(comp: str, parts) -> tuple[int, int, int] | None:
    """把无分隔符输入切成若干块，按顺序匹配各段前缀。返回 (字符数, 段数, 3字母块数)。"""
    if not comp or not parts:
        return None
    count = len(parts)

    @lru_cache(maxsize=None)
    def best(i: int, j: int):
        if j >= len(comp):
            return (0, 0, 0)
        if i >= count:
            return None
        limit = min(len(parts[i]), len(comp) - j)
        found = None
        for size in range(limit, 0, -1):
            if parts[i][:size] != comp[j:j + size]:
                continue
            tail = best(i + 1, j + size)
            if tail is None:
                continue
            candidate = (tail[0] + 1, tail[1] + size, tail[2] + (1 if size == 3 else 0))
            if found is None or _dp_value(candidate) > _dp_value(found):
                found = candidate
        return found

    result = best(0, 0)
    if result is None or result[0] == 0:
        return None
    return result[1], result[0], result[2]


def within_one_edit(left: str, right: str, limit: int = 1) -> bool:
    if abs(len(left) - len(right)) > limit:
        return False
    previous = list(range(len(right) + 1))
    for i, char in enumerate(left, 1):
        current = [i]
        row_min = i
        for j, other in enumerate(right, 1):
            cost = 0 if char == other else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
            row_min = min(row_min, current[j])
        if row_min > limit:
            return False
        previous = current
    return previous[-1] <= limit


class AvalonMapIndex:
    def __init__(self, entries):
        self.entries = sorted(entries, key=lambda entry: entry.name)
        self._by_name = {entry.name: entry for entry in self.entries}
        self._by_zone = {zone: entry for entry in self.entries for zone in entry.zone_ids}

    @classmethod
    def load(cls, path) -> "AvalonMapIndex":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        items = raw.get("maps") if isinstance(raw, dict) else None
        if not isinstance(items, list) or not items:
            raise ValueError("index.json has no maps")
        entries = []
        for item in items:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            icons = []
            for icon in item.get("icons") or []:
                alt = str(icon.get("alt") or "").upper().replace("HIRE", "HIDE")
                if alt:
                    icons.append((alt, int(icon.get("badge") or 0)))
            entries.append(make_entry(
                item["name"], item.get("tier") or 0, tuple(icons),
                item.get("imgFile") or "", tuple(item.get("zoneIds") or ())))
        if not entries:
            raise ValueError("index.json has no valid maps")
        return cls(entries)

    def by_name(self, name):
        return self._by_name.get(name or "")

    def by_zone(self, zone_id):
        return self._by_zone.get(str(zone_id or "").upper())

    def query(self, text: str, *, current_zone=None, history=(), limit: int = 8) -> list[MapHit]:
        tokens, comp = tokenize(text or "")
        if not comp:
            return self._defaults(current_zone, history, limit)
        scored = []
        for entry in self.entries:
            result = _score_entry(entry, tokens, comp)
            if result is not None:
                scored.append((result[0], result[1], entry))
        if not scored:
            for entry in self.entries:
                if within_one_edit(comp, entry.key3):
                    scored.append((300 + 10 * len(comp), len(entry.parts), entry))
        hits = [self._hit(base, matched, entry, current_zone, history)
                for base, matched, entry in scored]
        hits.sort(key=lambda hit: (-hit.score, hit.entry.name))
        return hits[:limit]

    def _hit(self, base, matched, entry, current_zone, history) -> MapHit:
        score = base
        is_current = bool(current_zone) and str(current_zone).upper() in entry.zone_ids
        if is_current:
            score += 200
        history = list(history)
        if entry.name in history:
            score += max(50 - 3 * history.index(entry.name), 5)
        if entry.has_gold:
            score += 10
        score += TIER_BONUS.get(entry.tier, 0)
        return MapHit(entry=entry, score=score, matched_parts=matched, is_current=is_current)

    def _defaults(self, current_zone, history, limit) -> list[MapHit]:
        picked, seen = [], set()
        current = self.by_zone(current_zone) if current_zone else None
        if current is not None:
            picked.append(self._hit(200, 0, current, current_zone, history))
            seen.add(current.name)
        for name in list(history)[:limit]:
            entry = self.by_name(name)
            if entry is not None and entry.name not in seen:
                picked.append(self._hit(100, 0, entry, current_zone, history))
                seen.add(entry.name)
        extras = [entry for entry in self.entries if entry.name not in seen]
        extras.sort(key=lambda entry: (-(1 if entry.has_gold else 0), -entry.tier, entry.name))
        for entry in extras:
            if len(picked) >= limit:
                break
            picked.append(self._hit(0, 0, entry, current_zone, history))
        return picked[:limit]


def _score_entry(entry, tokens, comp):
    if comp == compact(entry.name):
        return 1010, len(entry.parts)
    if comp == entry.key3:
        return 1000, len(entry.parts)
    if tokens:
        matched = token_prefix_match(tokens, entry.parts)
        if matched:
            return 600 + 40 * sum(len(token) for token in tokens) + 30 * matched, matched
    state = compact_prefix_match(comp, entry.parts)
    if state is not None:
        chars, matched, threes = state
        return 550 + 40 * chars + 30 * matched + 5 * threes, matched
    return None


def build_index_records(zones: dict, gallery: list) -> list[dict]:
    """zones 为 ao-bin-dumps zones.json 的 dict；gallery 为 avalon-gold-finder data.json。"""
    by_compact = {compact(item.get("name")): item for item in gallery if item.get("name")}
    records: dict[str, dict] = {}
    for zone_id in sorted(zones):
        if not str(zone_id).upper().startswith("TNL-"):
            continue
        zone = zones[zone_id]
        name = str(zone.get("name") or "").strip()
        if not name:
            continue
        meta = by_compact.get(compact(name), {})
        record = records.setdefault(name.lower(), {
            "name": name,
            "tier": int(zone.get("tier") or meta.get("tier") or 0),
            "icons": [
                {"alt": str(icon.get("alt") or "").upper().replace("HIRE", "HIDE"),
                 "badge": int(icon.get("badge") or 0)}
                for icon in meta.get("icons") or [] if icon.get("alt")
            ],
            "imgFile": Path(str(meta.get("img") or "")).with_suffix(".webp").name
            if meta.get("img") else "",
            "zoneIds": [],
        })
        record["zoneIds"].append(str(zone_id).strip().upper())
    return list(records.values())

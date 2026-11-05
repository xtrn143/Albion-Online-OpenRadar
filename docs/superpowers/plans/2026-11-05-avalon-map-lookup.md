# 阿瓦隆查图（Avalon Map Lookup）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 玩家在 AlbionAware 中按 `F6` 或点击悬浮窗地图图标，输入区名速记即可查看对应阿瓦隆地图截图，全程离线。

**Architecture:** 构建期把 `zones.json`（400 个 TNL 区）与 avalon-gold-finder 图库合并成 `client/data/avalon/index.json` 并复制 webp 图片；运行期新增 `map_index.py`（纯 Python 三级匹配）与 `map_window.py`（Tk Toplevel 查图窗），由 `main.py` 负责热键、进区识别、懒加载与历史持久化。

**Tech Stack:** Python 3.11+、tkinter、Pillow 10.4、pytest 8.3、PyInstaller、Inno Setup

参考 spec：[2026-11-05-avalon-map-lookup-design.md](../specs/2026-11-05-avalon-map-lookup-design.md)

---

## 文件结构

| 文件 | 操作 | 职责 |
|---|---|---|
| `client/albion_aware/map_index.py` | 创建 | 归一化/折叠、速记键、三级匹配、排序、索引加载、`build_index_records`、`is_roads_zone` |
| `client/albion_aware/map_window.py` | 创建 | 查图窗 UI：搜索、候选、缩放拖动、历史回调 |
| `client/albion_aware/overlay.py` | 修改 | 顶部常驻地图图标 + 5 秒金色高亮 |
| `client/albion_aware/config.py` | 修改 | `hotkeys.map_lookup`、`overlay.map_x/map_y`、`map_history` |
| `client/albion_aware/main.py` | 修改 | F6、进区识别、索引懒加载、窗口生命周期、历史与位置持久化 |
| `client/albion_aware/tray.py` | 修改 | 托盘“阿瓦隆查图” |
| `client/albion_aware/lang/zh-CN.json`、`en.json` | 修改 | `map.*`、`tray.map_lookup` |
| `client/tools/sync_avalon_maps.py` | 创建 | 合并索引、复制/下载图片、碰撞校验 |
| `client/data/avalon/index.json` | 生成并入库 | 400 条索引（约 250KB） |
| `client/data/avalon/maps/*.webp` | 生成，不入库 | 397 张截图（18.8MB） |
| `client/packaging/albion_aware.spec` | 修改 | 打包 `data/avalon` |
| `client/build.ps1` | 修改 | 构建前同步地图 |
| `client/tests/test_map_index.py` | 创建 | 匹配/排序/索引构建单测 |
| `client/tests/test_map_window.py` | 创建 | 窗口纯逻辑单测 |
| `client/tests/test_overlay.py` | 修改 | 地图图标测试 |
| `client/tests/test_main.py` | 修改 | `push_history` 测试 |
| `client/tests/test_config.py` | 修改 | 新默认值测试 |
| `.gitignore` | 修改 | 忽略 `client/data/avalon/maps/` |
| `client/packaging/NOTICE.txt`、`README.txt` | 修改 | 数据来源声明 |

所有命令在 `d:\work\Albion-Online-OpenRadar\client` 下执行；测试统一 `python -m pytest tests/<file> -v`。

---

### Task 1: 纯匹配模块 `map_index.py`

**Files:**
- Create: `client/albion_aware/map_index.py`
- Test: `client/tests/test_map_index.py`

- [ ] **Step 1: 写失败测试**

创建 `client/tests/test_map_index.py`：

```python
from albion_aware.map_index import (
    AvalonMapIndex,
    build_index_records,
    compact,
    is_roads_zone,
    key3,
    make_entry,
    parts_of,
    tokenize,
)


def _entry(name, tier=6, icons=(), zone_ids=()):
    return make_entry(name, tier, icons, f"{name} T{tier}.webp", zone_ids)


def _index():
    return AvalonMapIndex([
        _entry("Hetitos-Iuaerom", 6, (("GOLD", 0),), ("TNL-225",)),
        _entry("Hetitos-Ouanerom", 8, (), ("TNL-226",)),
        _entry("Secent-Qi-Odesom", 4, (("BLUE", 0),), ("TNL-377",)),
        _entry("Cases-Ugumlos", 6, (), ("TNL-100",)),
    ])


def test_fold_treats_capital_i_and_l_as_same():
    assert compact("HET LUA") == "HETIUA"
    assert compact("HET-LUA") == "HETIUA"
    assert key3("Hetitos-Iuaerom") == "HETIUA"


def test_key3_uses_first_three_letters_of_each_part():
    assert key3("Hetitos-Iuaerom") == "HETIUA"
    assert key3("Secent-Qi-Odesom") == "SECQIODE"
    assert parts_of("Secent-Qi-Odesom") == ("SECENT", "QI", "ODESOM")


def test_tokenize_keeps_tokens_and_compact_form():
    assert tokenize("SEC QI ODE") == (["SEC", "QI", "ODE"], "SECQIODE")


def test_is_roads_zone_accepts_only_tnl_ids():
    assert is_roads_zone("TNL-241") is True
    assert is_roads_zone("tnl-241") is True
    assert is_roads_zone("5001") is False
    assert is_roads_zone(None) is False


def test_three_letter_habit_hits_exactly_one_map():
    hits = _index().query("HET LUA")
    assert hits[0].entry.name == "Hetitos-Iuaerom"
    assert len(hits) == 1


def test_compact_habit_without_separator_hits():
    hits = _index().query("HETLUA")
    assert hits[0].entry.name == "Hetitos-Iuaerom"


def test_three_part_habit_hits():
    hits = _index().query("SEC QI ODE")
    assert hits[0].entry.name == "Secent-Qi-Odesom"


def test_three_part_compact_hits():
    hits = _index().query("SECQIODE")
    assert hits[0].entry.name == "Secent-Qi-Odesom"


def test_full_name_is_ranked_first():
    hits = _index().query("hetitos-iuaerom")
    assert hits[0].entry.name == "Hetitos-Iuaerom"


def test_typo_falls_back_to_fuzzy():
    hits = _index().query("HETLUB")
    assert hits and hits[0].entry.name == "Hetitos-Iuaerom"


def test_current_zone_is_boosted_to_top():
    hits = _index().query("HET", current_zone="TNL-226")
    assert hits[0].entry.name == "Hetitos-Ouanerom"
    assert hits[0].is_current is True


def test_gold_beats_tier_when_scores_tie():
    hits = _index().query("HET")
    # 两者基础分相同：含金箱的 T6 排在 T8 之前
    assert hits[0].entry.name == "Hetitos-Iuaerom"


def test_limit_is_respected():
    hits = _index().query("", limit=2)
    assert len(hits) == 2


def test_empty_query_puts_current_zone_first():
    hits = _index().query("", current_zone="TNL-100")
    assert hits[0].entry.name == "Cases-Ugumlos"
    assert hits[0].is_current is True


def test_no_match_returns_empty_list():
    assert _index().query("ZZZ") == []


def test_build_index_records_merges_zone_and_gallery():
    zones = {
        "TNL-001": {"name": "Hetitos-Iuaerom", "tier": 6},
        "TNL-002": {"name": "Secent-Qi-Odesom", "tier": 4},
    }
    gallery = [
        {"name": "Hetitos-IUaerom", "tier": 6,
         "icons": [{"alt": "GOLD"}, {"alt": "HIRE"}],
         "img": "img/Hetitos-Iuaerom T6.png"},
    ]
    records = build_index_records(zones, gallery)
    by_name = {record["name"]: record for record in records}
    assert by_name["Hetitos-Iuaerom"]["imgFile"] == "Hetitos-Iuaerom T6.webp"
    assert by_name["Hetitos-Iuaerom"]["zoneIds"] == ["TNL-001"]
    assert by_name["Hetitos-Iuaerom"]["icons"] == [
        {"alt": "GOLD", "badge": 0}, {"alt": "HIDE", "badge": 0}]
    assert by_name["Secent-Qi-Odesom"]["imgFile"] == ""
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_map_index.py -v`

Expected: FAIL，`ModuleNotFoundError: No module named 'albion_aware.map_index'`

- [ ] **Step 3: 实现 `map_index.py`**

创建 `client/albion_aware/map_index.py`：

```python
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
    return MapEntry(
        name=str(name),
        tier=int(tier or 0),
        parts=parts_of(name),
        key3=key3(name),
        icons=tuple(icons),
        img_file=str(img_file or ""),
        zone_ids=tuple(zone_ids),
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
        record["zoneIds"].append(zone_id)
    return list(records.values())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_map_index.py -v`

Expected: 全部 PASS（16 个用例）

- [ ] **Step 5: 提交**

```bash
git add albion_aware/map_index.py tests/test_map_index.py
git commit -m "feat(map): add avalon map name index with three-stage matching"
```

---

### Task 2: 数据同步脚本并生成索引

**Files:**
- Create: `client/tools/sync_avalon_maps.py`
- Modify: `.gitignore`
- Generate: `client/data/avalon/index.json`（入库）

- [ ] **Step 1: 写同步脚本**

创建 `client/tools/sync_avalon_maps.py`：

```python
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

from albion_aware.map_index import build_index_records, fold, parts_of  # noqa: E402

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
```

- [ ] **Step 2: 运行同步**

Run: `python tools/sync_avalon_maps.py`

Expected: 输出类似 `{"maps": 400, "images": 397, "missing_images": 3, "key_collisions": 0}`；生成 `client/data/avalon/index.json` 与 `client/data/avalon/maps/*.webp`

- [ ] **Step 3: 忽略图片目录**

在 `.gitignore` 的“Python 客户端”段追加：

```
# 阿瓦隆地图截图：构建前由 tools/sync_avalon_maps.py 生成，不入库
/client/data/avalon/maps/
```

- [ ] **Step 4: 验证索引可加载**

Run:

```bash
python -c "from albion_aware.map_index import AvalonMapIndex; i=AvalonMapIndex.load('data/avalon/index.json'); print(len(i.entries), i.query('HET LUA')[:1])"
```

Expected: 打印 `400` 与首位命中 `Hetitos-Iuaerom`

- [ ] **Step 5: 提交（只提交索引与脚本）**

```bash
git add tools/sync_avalon_maps.py data/avalon/index.json ../.gitignore
git commit -m "feat(map): add avalon map data sync and generated index"
```

---

### Task 3: 查图窗 `map_window.py`

**Files:**
- Create: `client/albion_aware/map_window.py`
- Test: `client/tests/test_map_window.py`

- [ ] **Step 1: 写失败测试**

创建 `client/tests/test_map_window.py`：

```python
from albion_aware.map_window import MapWindow, fit_scale, move_selection, next_zoom


def test_fit_scale_letterboxes_wide_image():
    assert fit_scale(720, 400, 1546, 1068) == 400 / 1068


def test_fit_scale_never_upscales():
    assert fit_scale(2000, 2000, 400, 300) == 1.0


def test_fit_scale_handles_empty_image():
    assert fit_scale(720, 400, 0, 0) == 1.0


def test_next_zoom_clamps_to_range():
    zoom = 1.0
    for _ in range(10):
        zoom = next_zoom(zoom, 1)
    assert zoom == 2.0
    for _ in range(20):
        zoom = next_zoom(zoom, -1)
    assert zoom == 0.5


def test_move_selection_stays_inside_list():
    assert move_selection(0, -1, 3) == 0
    assert move_selection(0, 1, 3) == 1
    assert move_selection(2, 1, 3) == 2
    assert move_selection(0, 1, 0) == 0


def test_escape_closes_window():
    window = MapWindow.__new__(MapWindow)
    window._closed = False

    def close():
        window._closed = True

    window.close = close
    assert window._on_escape() == "break"
    assert window._closed is True


def test_tab_completes_first_hit():
    class _Entry:
        value = ""

        def get(self):
            return self.value

        def delete(self, *_args):
            self.value = ""

        def insert(self, _index, text):
            self.value = text

        def icursor(self, *_args):
            pass

    class _Hit:
        class entry:
            name = "Hetitos-Iuaerom"

    window = MapWindow.__new__(MapWindow)
    window.entry = _Entry()
    window._hits = [_Hit]
    window._refresh = lambda text: None
    assert window._on_tab() == "break"
    assert window.entry.value == "Hetitos-Iuaerom"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_map_window.py -v`

Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 实现 `map_window.py`**

创建 `client/albion_aware/map_window.py`：

```python
"""阿瓦隆查图窗：搜索、候选列表、地图缩放与拖动。"""
from __future__ import annotations

import tkinter as tk
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageTk

BG = "#141414"
BG_ALT = "#1b1b1b"
FG = "#e6e6e6"
SUB = "#9a9a9a"
GOLD = "#e8c04a"
SELECT_BG = "#2a2a2a"
ZOOM_MIN = 0.5
ZOOM_MAX = 2.0
ROW_H = 22
MAX_ROWS = 8
ICON_SIZE = 7
ICON_COLORS = {
    "GOLD": "#e8c04a", "BLUE": "#4a9be8", "GREEN": "#3fb950",
    "DUNGEON": "#b06ae0", "LOGS": "#c08a4a", "ORE": "#9aa0a6",
    "ROCK": "#7a7a7a", "COTTON": "#e6e6e6", "HIDE": "#c46a4a",
}
CACHE_LIMIT = 5


def fit_scale(canvas_w, canvas_h, image_w, image_h) -> float:
    if image_w <= 0 or image_h <= 0:
        return 1.0
    return min(canvas_w / image_w, canvas_h / image_h, 1.0)


def next_zoom(zoom: float, direction: int) -> float:
    step = 1.2 if direction > 0 else 1 / 1.2
    return max(ZOOM_MIN, min(ZOOM_MAX, zoom * step))


def move_selection(index: int, delta: int, count: int) -> int:
    if count <= 0:
        return 0
    return max(0, min(count - 1, index + delta))


class MapWindow:
    def __init__(self, master, i18n, index=None, data_dir=None, history=(),
                 on_position_changed=None, on_selected=None):
        self.i18n = i18n
        self._index = index
        self._data_dir = Path(data_dir) if data_dir else None
        self._history = list(history)[:10]
        self._on_position_changed = on_position_changed
        self._on_selected = on_selected

        self._hits = []
        self._selected = 0
        self._row_frames = []
        self._images = OrderedDict()
        self._pil = None
        self._photo = None
        self._fit = 1.0
        self._zoom = 1.0
        self._offset = [0.0, 0.0]
        self._drag = None
        self._zone = None
        self._closed = True
        self._state = "loading"  # loading / ready / missing

        self.top = tk.Toplevel(master)
        self.top.title(i18n.t("map.title"))
        self.top.attributes("-topmost", True)
        self.top.configure(bg=BG, padx=10, pady=8)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.geometry("720x560")
        self.top.bind("<Escape>", lambda _event: self._on_escape())
        self.top.withdraw()

        bar = tk.Frame(self.top, bg=BG)
        bar.pack(fill="x")
        self.count = tk.Label(bar, text="", bg=BG, fg=SUB, font=("Segoe UI", 9))
        self.count.pack(side="right")
        tk.Button(bar, text="×", command=self.close, bg=BG, fg=SUB, bd=0,
                  activebackground=BG, activeforeground=FG,
                  font=("Segoe UI", 11)).pack(side="right", padx=(4, 0))
        self.entry = tk.Entry(bar, bg=BG_ALT, fg=FG, insertbackground=FG,
                              relief="flat", font=("Segoe UI", 12))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry.bind("<KeyRelease>", self._on_query)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Up>", lambda _event: self._move(-1))
        self.entry.bind("<Down>", lambda _event: self._move(1))
        self.entry.bind("<Tab>", self._on_tab)
        self.entry.bind("<Escape>", lambda _event: self._on_escape())

        self.rows = tk.Frame(self.top, bg=BG)
        self.rows.pack(fill="x", pady=(6, 6))

        self.canvas = tk.Canvas(self.top, bg="#0f0f0f", highlightthickness=0, height=380)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", lambda _event: self._reset_view())

        tk.Label(self.top, text=i18n.t("map.hint"), bg=BG, fg=SUB,
                 font=("Segoe UI", 8), anchor="w").pack(fill="x", pady=(4, 0))
        self._status(i18n.t("map.loading"))

    @property
    def alive(self) -> bool:
        try:
            return bool(self.top.winfo_exists())
        except tk.TclError:
            return False

    @property
    def is_open(self) -> bool:
        return not self._closed

    def place_at(self, x, y) -> None:
        self.top.geometry(f"+{int(x)}+{int(y)}")

    def set_index(self, index) -> None:
        self._index = index
        self._state = "ready" if index is not None else "missing"
        if self._closed:
            return
        if index is None:
            self._hits = []
            self._render_rows([])
            self._status(self.i18n.t("map.missing"))
            return
        self._refresh(self.entry.get())

    def open(self, current_zone=None, prefill=None) -> None:
        self._closed = False
        self._zone = current_zone
        self.top.deiconify()
        self.top.lift()
        self.top.attributes("-topmost", True)
        text = prefill or ""
        if not text and current_zone and self._index is not None:
            entry = self._index.by_zone(current_zone)
            text = entry.name if entry else current_zone
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self._zoom = 1.0
        self._offset = [0.0, 0.0]
        self._refresh(text)
        self.entry.focus_force()
        self.entry.select_range(0, "end")
        self.entry.icursor("end")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._save_position()
        self.top.withdraw()

    def destroy(self) -> None:
        try:
            self.top.destroy()
        except tk.TclError:
            pass

    # ---------- 搜索与候选 ----------
    def _on_query(self, _event=None) -> None:
        self._refresh(self.entry.get())

    def _refresh(self, text: str) -> None:
        if self._index is None:
            self._hits = []
            self._render_rows([])
            self._status(self.i18n.t("map.loading") if self._state == "loading"
                         else self.i18n.t("map.missing"))
            return
        self._hits = self._index.query(text, current_zone=self._zone,
                                       history=self._history, limit=MAX_ROWS)
        self._selected = 0
        self._render_rows(self._hits)
        self.count.configure(text=self.i18n.t("map.count", count=len(self._hits))
                             if text.strip() else "")
        # 只有唯一命中才自动出图；多候选时保持列表，避免边打字边闪图
        if len(self._hits) == 1:
            self._select(self._hits[0].entry, remember=False)
        elif not self._hits:
            self._pil = None
            self._status(self.i18n.t("map.no_result") if text.strip() else "")
        else:
            self._pil = None
            self._status("")

    def _render_rows(self, hits) -> None:
        for child in self.rows.winfo_children():
            child.destroy()
        self._row_frames = []
        for hit in hits:
            row = tk.Frame(self.rows, bg=BG, height=ROW_H)
            row.pack(fill="x")
            row.pack_propagate(False)
            labels = []
            name = tk.Label(row, text=hit.entry.name, bg=BG, fg=FG, anchor="w",
                            font=("Segoe UI", 9, "bold" if hit.is_current else "normal"))
            name.pack(side="left")
            labels.append(name)
            if hit.entry.tier:
                tier = tk.Label(row, text=self.i18n.t("map.tier", tier=hit.entry.tier),
                                bg=BG, fg=SUB, font=("Segoe UI", 8))
                tier.pack(side="left", padx=(6, 0))
                labels.append(tier)
            if hit.is_current:
                current = tk.Label(row, text=self.i18n.t("map.current"),
                                   bg=BG, fg=GOLD, font=("Segoe UI", 8))
                current.pack(side="left", padx=(4, 0))
                labels.append(current)
            for alt, _badge in hit.entry.icons[:6]:
                dot = tk.Frame(row, bg=ICON_COLORS.get(alt, SUB),
                               width=ICON_SIZE, height=ICON_SIZE)
                dot.pack(side="left", padx=(2, 0), pady=7)
            for widget in (row, *labels):
                widget.bind("<Button-1>",
                            lambda _event, h=hit: self._select(h.entry))
            self._row_frames.append((row, labels))
        self._highlight(0)

    def _highlight(self, index: int) -> None:
        for position, (row, labels) in enumerate(self._row_frames):
            color = SELECT_BG if position == index else BG
            row.configure(bg=color)
            for label in labels:
                label.configure(bg=color)

    def _move(self, delta: int) -> str:
        if not self._hits:
            return "break"
        self._selected = move_selection(self._selected, delta, len(self._hits))
        self._highlight(self._selected)
        self._select(self._hits[self._selected].entry, remember=False)
        return "break"

    def _on_enter(self, _event=None) -> str:
        if self._hits:
            self._select(self._hits[self._selected].entry)
            self.canvas.focus_set()
        return "break"

    def _on_tab(self, _event=None) -> str:
        if self._hits:
            self.entry.delete(0, "end")
            self.entry.insert(0, self._hits[0].entry.name)
            self.entry.icursor("end")
            self._refresh(self.entry.get())
        return "break"

    def _on_escape(self) -> str:
        self.close()
        return "break"

    # ---------- 地图显示 ----------
    def _select(self, entry, remember=True) -> None:
        self._pil = None
        self._zoom = 1.0
        self._offset = [0.0, 0.0]
        image = self._image(entry)
        if image is None:
            self._status(self.i18n.t("map.no_image"))
        else:
            self._pil = image
            self._status("")
            self._redraw()
        if remember and self._on_selected is not None:
            self._on_selected(entry.name)

    def _image(self, entry):
        if self._data_dir is None or not entry.img_file:
            return None
        key = entry.img_file
        if key in self._images:
            self._images.move_to_end(key)
            return self._images[key]
        try:
            image = Image.open(self._data_dir / key)
            image.load()
        except (OSError, ValueError):
            return None
        self._images[key] = image
        while len(self._images) > CACHE_LIMIT:
            self._images.popitem(last=False)
        return image

    def _canvas_size(self):
        return max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)

    def _redraw(self) -> None:
        self.canvas.delete("all")
        self._photo = None
        if self._pil is None:
            return
        width, height = self._canvas_size()
        self._fit = fit_scale(width, height, self._pil.width, self._pil.height)
        scale = self._fit * self._zoom
        size = (max(int(self._pil.width * scale), 1), max(int(self._pil.height * scale), 1))
        image = self._pil.resize(size, Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(image, master=self.top)
        self.canvas.create_image(width / 2 + self._offset[0],
                                 height / 2 + self._offset[1],
                                 image=self._photo, anchor="center", tags="map")

    def _status(self, text: str) -> None:
        self.canvas.delete("all")
        self._photo = None
        if text:
            width, _height = self._canvas_size()
            self.canvas.create_text(width / 2, 120, text=text, fill=SUB,
                                    font=("Segoe UI", 10), tags="status")

    def _on_wheel(self, event) -> None:
        if self._pil is None:
            return
        previous = self._zoom
        self._zoom = next_zoom(previous, 1 if getattr(event, "delta", 0) > 0 else -1)
        if self._zoom == previous:
            return
        width, height = self._canvas_size()
        old_scale = self._fit * previous
        new_scale = self._fit * self._zoom
        if old_scale <= 0:
            return
        left = width / 2 - self._pil.width * old_scale / 2 + self._offset[0]
        top = height / 2 - self._pil.height * old_scale / 2 + self._offset[1]
        image_x = (event.x - left) / old_scale
        image_y = (event.y - top) / old_scale
        self._offset[0] = (event.x - image_x * new_scale
                           - (width / 2 - self._pil.width * new_scale / 2))
        self._offset[1] = (event.y - image_y * new_scale
                           - (height / 2 - self._pil.height * new_scale / 2))
        self._redraw()

    def _on_press(self, event) -> None:
        self._drag = (event.x, event.y, self._offset[0], self._offset[1])

    def _on_drag(self, event) -> None:
        if self._drag is None:
            return
        start_x, start_y, offset_x, offset_y = self._drag
        self._offset[0] = offset_x + event.x - start_x
        self._offset[1] = offset_y + event.y - start_y
        self._redraw()

    def _on_release(self, _event=None) -> None:
        self._drag = None

    def _reset_view(self) -> None:
        self._zoom = 1.0
        self._offset = [0.0, 0.0]
        self._redraw()

    def _save_position(self) -> None:
        if self._on_position_changed is None:
            return
        try:
            self._on_position_changed(self.top.winfo_x(), self.top.winfo_y())
        except tk.TclError:
            pass
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_map_window.py -v`

Expected: 7 个用例 PASS

- [ ] **Step 5: 提交**

```bash
git add albion_aware/map_window.py tests/test_map_window.py
git commit -m "feat(map): add avalon map lookup window with zoom and pan"
```

---

### Task 4: 悬浮窗地图图标

**Files:**
- Modify: `client/albion_aware/overlay.py`
- Test: `client/tests/test_overlay.py`

- [ ] **Step 1: 写失败测试**

在 `client/tests/test_overlay.py` 末尾追加（`_FakeLabel` 已在第 133 行定义，可直接复用）：

```python
# 首行 import 改为：
from albion_aware.overlay import (GLOW_LAYERS, GLOW_STEP, PAD, ROW_H, TOP_H, WIDTH,
                                  OverlayWindow, format_ip, ip_color, map_icon, sound_icon)


def test_map_icon_highlights_in_gold():
    normal = map_icon(False)
    hot = map_icon(True)
    assert normal.size == hot.size == (12, 12)
    assert normal.getpixel((1, 1))[3] == 0

    def has_gold(image):
        return any(r > 180 and g > 140 and b < 120 and a > 0 for r, g, b, a in image.getdata())

    assert has_gold(hot) is True
    assert has_gold(normal) is False


def test_flash_map_icon_swaps_image_then_cools():
    class _Root:
        def __init__(self):
            self.jobs = {}

        def after(self, ms, callback):
            self.jobs["last"] = (ms, callback)
            return "job-1"

        def after_cancel(self, job):
            self.jobs["cancelled"] = job

    window = OverlayWindow.__new__(OverlayWindow)
    window.root = _Root()
    window.map_icon = _FakeLabel()
    window._map_images = {False: "off-image", True: "hot-image"}
    window._map_job = None
    window.flash_map_icon(5000)
    assert window.map_icon.kwargs["image"] == "hot-image"
    assert window.root.jobs["last"][0] == 5000
    window.root.jobs["last"][1]()
    assert window.map_icon.kwargs["image"] == "off-image"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_overlay.py -v`

Expected: FAIL，`ImportError: cannot import name 'map_icon'`

- [ ] **Step 3: 修改 `overlay.py`**

3a. 在 `sound_icon` 后新增 `map_icon`，并补充颜色常量：

```python
MAP_ON = (230, 230, 230, 255)
MAP_HOT = (232, 192, 74, 255)


def map_icon(hot: bool = False) -> Image.Image:
    """12px 地图图标：常态白色，进入阿瓦隆后临时变金色。"""
    image = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = MAP_HOT if hot else MAP_ON
    draw.rectangle((1, 2, 10, 10), outline=color, width=1)
    draw.line((4, 2, 4, 10), fill=color)
    draw.line((7, 2, 7, 10), fill=color)
    draw.line((1, 6, 10, 6), fill=color)
    return image
```

3b. 构造函数签名增加 `on_map_click=None`：

```python
    def __init__(self, i18n, icon_loader, on_row_click, on_more_click, on_drag_end,
                 on_sound_click=None, on_map_click=None):
        ...
        self._on_map_click = on_map_click
```

3c. 在 `sound_icon` 创建之后插入地图图标（注意仍要早于 `self.status.pack`）：

```python
        self._map_images = {hot: ImageTk.PhotoImage(map_icon(hot), master=self.root)
                            for hot in (False, True)}
        self._map_job = None
        self.map_icon = tk.Label(self.top_row, bg=BG, bd=0,
                                 image=self._map_images[False])
        self.map_icon.pack(side="left", padx=(2, 0))
        self.map_icon.bind("<Button-1>", self._map_click)
```

3d. 在 `_toggle_sound_click` 附近新增方法：

```python
    def _map_click(self, _event=None):
        if self._on_map_click is not None:
            self._on_map_click()
        return "break"

    def flash_map_icon(self, duration_ms: int = 5000) -> None:
        """进入阿瓦隆时短暂变金，提示可以按 F6 查图。"""
        if self._map_job is not None:
            try:
                self.root.after_cancel(self._map_job)
            except tk.TclError:
                pass
            self._map_job = None
        self._set_map_hot(True)
        self._map_job = self.root.after(duration_ms, self._cool_map)

    def _cool_map(self) -> None:
        self._map_job = None
        self._set_map_hot(False)

    def _set_map_hot(self, hot: bool) -> None:
        self.map_icon.configure(image=self._map_images[bool(hot)])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_overlay.py -v`

Expected: 全部 PASS（含新增 2 个）

- [ ] **Step 5: 提交**

```bash
git add albion_aware/overlay.py tests/test_overlay.py
git commit -m "feat(overlay): add persistent map icon with 5s gold highlight"
```

---

### Task 5: 配置默认值与多语言文案

**Files:**
- Modify: `client/albion_aware/config.py`
- Modify: `client/albion_aware/lang/zh-CN.json`
- Modify: `client/albion_aware/lang/en.json`
- Test: `client/tests/test_config.py`、`client/tests/test_i18n.py`

- [ ] **Step 1: 写失败测试**

在 `client/tests/test_config.py` 末尾追加：

```python
def test_map_defaults_present():
    cfg = default_config()
    assert cfg["hotkeys"]["map_lookup"] == "F6"
    assert cfg["overlay"]["map_x"] is None
    assert cfg["overlay"]["map_y"] is None
    assert cfg["map_history"] == []
```

在 `client/tests/test_i18n.py` 末尾追加：

```python
def test_map_texts_exist_in_both_languages():
    zh = I18n("zh-CN", LANG_DIR)
    en = I18n("en", LANG_DIR)
    for key in ("map.title", "map.loading", "map.missing",
                "map.no_result", "map.current", "map.no_image", "map.hint",
                "map.count", "map.tier", "tray.map_lookup"):
        assert zh.t(key) != key, key
        assert en.t(key) != key, key
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_config.py tests/test_i18n.py -v`

Expected: FAIL（`KeyError: 'map_lookup'` / i18n 返回 key 本身）

- [ ] **Step 3: 修改配置与文案**

`config.py` 的 `DEFAULT_CONFIG` 改为：

```python
    "hotkeys": {
        "toggle_click_through": "F10",
        "mark_party": "F9",
        "toggle_visible": "F8",
        "toggle_sound": "F7",
        "map_lookup": "F6",
    },
    "overlay": {"x": None, "y": None, "opacity": 0.9, "sound": False,
                "map_x": None, "map_y": None},
    "map_history": [],
```

`lang/zh-CN.json` 在 `"tray.sound"` 后插入并追加地图文案：

```json
  "tray.map_lookup": "阿瓦隆查图 (F6)",
```

在末尾 `"common.cancel": "取消"` 后补逗号并追加：

```json
  "map.title": "阿瓦隆查图",
  "map.loading": "地图数据加载中…",
  "map.missing": "地图数据缺失，请重新安装",
  "map.no_result": "没有匹配的区",
  "map.current": "当前",
  "map.no_image": "该区暂无截图",
  "map.hint": "输入 HET LUA 或 SEC QI ODE · Enter 查看 · ↑↓ 选择 · Esc 关闭",
  "map.count": "{count} 个结果",
  "map.tier": "T{tier}"
```

`lang/en.json` 对应追加：

```json
  "tray.map_lookup": "Avalon map (F6)",
  "map.title": "Avalon map lookup",
  "map.loading": "Loading map data…",
  "map.missing": "Map data missing, please reinstall",
  "map.no_result": "No matching zone",
  "map.current": "Current",
  "map.no_image": "No screenshot for this zone",
  "map.hint": "Type HET LUA or SEC QI ODE · Enter view · ↑↓ select · Esc close",
  "map.count": "{count} results",
  "map.tier": "T{tier}"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_config.py tests/test_i18n.py -v`

Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add albion_aware/config.py albion_aware/lang/zh-CN.json albion_aware/lang/en.json tests/test_config.py tests/test_i18n.py
git commit -m "feat(config): add map hotkey, window position and map i18n texts"
```

---

### Task 6: 主程序集成

**Files:**
- Modify: `client/albion_aware/main.py`
- Modify: `client/albion_aware/tray.py`
- Test: `client/tests/test_main.py`

- [ ] **Step 1: 写失败测试**

把 `client/tests/test_main.py` 第 5 行的 import 改为：

```python
from albion_aware.main import (push_history, sound_cooldown_ok, _resource_dir,
                               has_new_stranger, user_data_dir)
```

然后在文件末尾追加：

```python
def test_push_history_puts_newest_first_and_dedupes():
    assert push_history(["A", "B"], "C") == ["C", "A", "B"]
    assert push_history(["A", "B"], "B") == ["B", "A"]


def test_push_history_caps_length():
    history = [f"Z{i}" for i in range(10)]
    assert len(push_history(history, "NEW", limit=10)) == 10
    assert push_history(history, "NEW", limit=10)[0] == "NEW"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_main.py -v`

Expected: FAIL，`ImportError: cannot import name 'push_history'`

- [ ] **Step 3: 修改 `main.py`**

3a. 新增 import（`threading` 已在第 5 行导入，无需重复）：

```python
from albion_aware.map_index import AvalonMapIndex, is_roads_zone
from albion_aware.map_window import MapWindow
```

3b. 在 `sound_cooldown_ok` 后新增纯函数：

```python
def push_history(history, name: str, limit: int = 10) -> list[str]:
    cleaned = [str(item) for item in history if str(item) != name]
    return [str(name)] + cleaned[:limit - 1]
```

3c. `__init__` 中在 `self._no_radar_warned = False` 后新增：

```python
        self._zone_id = ""
        self._in_roads = False
        self._map_index = None
        self._map_index_loading = False
        self._map_window = None
        self._map_history = [str(name) for name in (self.config.get("map_history") or [])]
```

3d. `OverlayWindow(...)` 调用增加地图回调：

```python
        self.window = OverlayWindow(
            i18n=self.i18n,
            icon_loader=self._row_icon,
            on_row_click=self._on_row_click,
            on_more_click=self._on_more_click,
            on_drag_end=self._save_position,
            on_sound_click=self._toggle_sound,
            on_map_click=self._open_maps,
        )
```

3e. 热键字典增加 F6：

```python
            self.config.get("hotkeys.map_lookup", "F6"): self._queue_toggle_maps,
```

3f. 队列封装：在 `_queue_mark_selected` 后新增

```python
    def _queue_open_maps(self):
        self._queue_action(self._open_maps)

    def _queue_toggle_maps(self):
        self._queue_action(self._toggle_maps)

    def _toggle_maps(self) -> None:
        if self._map_window is not None and self._map_window.is_open:
            self._map_window.close()
            return
        self._open_maps()
```

3g. `_apply` 的 `ZoneChanged` 分支改为：

```python
            elif isinstance(event, ZoneChanged):
                self._zone_id = event.zone_id
                self.store.clear()
                self.panel.hide()
                if is_roads_zone(event.zone_id):
                    if not self._in_roads:
                        self.window.flash_map_icon()
                    self._in_roads = True
                else:
                    self._in_roads = False
                applied = True
```

3h. 在 `_open_diagnostics` 之前新增地图相关方法：

```python
    def _open_maps(self) -> None:
        if self._map_window is None or not self._map_window.alive:
            self._map_window = MapWindow(
                self.window.root,
                self.i18n,
                data_dir=_resource_dir(self.app_dir) / "data" / "avalon",
                history=self._map_history,
                on_position_changed=self._save_map_position,
                on_selected=self._remember_map,
            )
            if self._map_index is not None:
                self._map_window.set_index(self._map_index)
            else:
                self._load_map_index()
            map_x = self.config.get("overlay.map_x")
            map_y = self.config.get("overlay.map_y")
            if map_x is not None and map_y is not None:
                self._map_window.place_at(map_x, map_y)
        self._map_window.open(self._zone_id if self._in_roads else None)

    def _load_map_index(self) -> None:
        if self._map_index is not None or self._map_index_loading:
            return
        self._map_index_loading = True
        path = _resource_dir(self.app_dir) / "data" / "avalon" / "index.json"

        def work() -> None:
            try:
                index = AvalonMapIndex.load(path)
            except (OSError, ValueError):
                index = None
            self._queue_action(self._map_index_ready, index)

        threading.Thread(target=work, name="avalon-map-index", daemon=True).start()

    def _map_index_ready(self, index) -> None:
        self._map_index_loading = False
        self._map_index = index
        if self._map_window is not None:
            self._map_window.set_index(index)

    def _save_map_position(self, x: int, y: int) -> None:
        self.config.set("overlay.map_x", int(x))
        self.config.set("overlay.map_y", int(y))
        self.config.save()

    def _remember_map(self, name: str) -> None:
        self._map_history = push_history(self._map_history, name)
        self.config.set("map_history", self._map_history)
        self.config.save()
```

3i. 窗口位置恢复已包含在 3h 的 `_open_maps` 中（读取 `overlay.map_x/map_y` 后 `place_at`），无需在 `__init__` 额外初始化。

3j. 托盘动作增加：

```python
            "map_lookup": lambda: self._queue_action(self._open_maps),
```

3k. `_set_language` 中关闭旧窗口（避免旧语言残留）：

```python
        if self._map_window is not None:
            self._map_window.destroy()
            self._map_window = None
```

3l. `_quit` 中关闭窗口：

```python
        if self._map_window is not None:
            self._map_window.destroy()
            self._map_window = None
```

3m. `tray.py` 在“鼠标穿透”之后插入菜单项：

```python
        pystray.MenuItem(i18n.t("tray.map_lookup"), wrap("map_lookup")),
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_main.py tests/test_overlay.py -v`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add albion_aware/main.py albion_aware/tray.py tests/test_main.py
git commit -m "feat(map): wire F6 hotkey, zone detection and map window lifecycle"
```

---

### Task 7: 打包与来源声明

**Files:**
- Modify: `client/packaging/albion_aware.spec`
- Modify: `client/build.ps1`
- Modify: `client/packaging/NOTICE.txt`
- Modify: `client/packaging/README.txt`

- [ ] **Step 1: 打包数据**

`albion_aware.spec` 的 `datas` 改为：

```python
    datas=[
        ("../albion_aware/lang", "albion_aware/lang"),
        ("../data/items.min.json", "data"),
        ("../data/icons", "data/icons"),
        ("../data/avalon", "data/avalon"),
    ],
```

- [ ] **Step 2: 构建前同步**

`build.ps1` 在 PyInstaller 之前插入：

```powershell
python tools\sync_avalon_maps.py
if ($LASTEXITCODE -ne 0) { throw 'Avalon map sync failed' }
if (-not (Test-Path 'data\avalon\index.json')) { throw 'Avalon map index missing' }
```

- [ ] **Step 3: 来源声明**

在 `client/packaging/NOTICE.txt` 末尾追加：

```
Avalon map screenshots and resource data come from the avalon-gold-finder
community project and https://portaler.pages.dev. They are bundled for
offline convenience only; all rights remain with their original authors.
```

在 `client/packaging/README.txt` 末尾追加：

```
阿瓦隆查图（F6）：地图截图与资源数据来自 avalon-gold-finder 与 portaler.pages.dev，
仅供离线查询使用，版权归原作者所有。
```

- [ ] **Step 4: 验证打包内容**

Run: `python tools/sync_avalon_maps.py; python -c "import json,pathlib; d=pathlib.Path('data/avalon'); print(len(list((d/'maps').glob('*.webp')), )); print(json.loads((d/'index.json').read_text(encoding='utf-8'))['version'])"`

Expected: 打印图片数量（约 397）与 `1`

- [ ] **Step 5: 提交**

```bash
git add packaging/albion_aware.spec build.ps1 packaging/NOTICE.txt packaging/README.txt
git commit -m "build(map): bundle avalon map data and document its source"
```

---

### Task 8: 全量验证

**Files:** 无新增

- [ ] **Step 1: 运行全部单测**

Run: `python -m pytest -q`

Expected: 全部 PASS（原有 60+ 用例 + 新增约 25 个）

- [ ] **Step 2: 冒烟启动（无游戏也可）**

Run: `python -m albion_aware.main`

Expected: 悬浮窗出现，顶部有白色地图图标；点击图标弹出查图窗，显示“地图数据加载中…”后出现候选；输入 `HET LUA` 自动出图；`Esc` 关闭。若当前不在阿瓦隆，列表按 Gold/阶数排序。

- [ ] **Step 3: 手工验收（有游戏时）**

逐项确认：

1. 进入 `TNL-xxx` 区 → 地图图标变金色，5 秒后恢复白色；
2. 点击图标或按 `F6` → 窗口打开并预填当前区、自动出图；
3. 输入 `HET LUA`、`HETLUA`、`SEC QI ODE`、`SECQIODE` → 分别命中对应区；
4. 滚轮以鼠标位置为中心缩放（0.5×–2.0×），左键拖动，双击复位；
5. 关闭再打开 → 窗口位置保持；
6. 托盘“阿瓦隆查图 (F6)”可打开；
7. 断网后重复 2–4 步仍可用。

- [ ] **Step 4: 提交验证记录（如有微调）**

```bash
git status --short
git add -A albion_aware tests data/avalon/index.json
git commit -m "test(map): verify avalon map lookup end to end"
```

（无代码改动时跳过此步。）

---

## 自检结果

- **Spec 覆盖**：数据合并/索引（Task 1、2）、三级匹配与排序（Task 1）、查图窗与缩放拖动（Task 3）、图标与 F6 双入口（Task 4、6）、进区识别与金点（Task 6）、配置与 i18n（Task 5）、打包与来源声明（Task 7）、测试与验收（各任务 + Task 8）。
- **占位符**：无 TBD/TODO；每个代码步骤均为完整实现。
- **类型一致性**：`MapEntry(name, tier, parts, key3, icons, img_file, zone_ids)`、`MapHit(entry, score, matched_parts, is_current)`、`MapWindow.open(current_zone, prefill)`、`set_index(index)`、`place_at(x, y)` 在各任务中用法一致。
- **已知偏差**：spec 里工具名写作 `tools/sync-avalon-maps`，实际实现为 `client/tools/sync_avalon_maps.py`（与仓库 Python 工具命名一致）。

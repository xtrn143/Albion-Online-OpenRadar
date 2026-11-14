# 危险区限定探查与悬浮窗合并显示 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 只在红/黑区展示非队友玩家并自动开关提示音，其余区域在悬浮窗内展示资源，取消 gather/roam 双模式与独立资源面板。

**Architecture:** 客户端打包一份精简的 `zoneId → pvpType` 表，`ZoneChanged` 时判定危险等级；`OverlayWindow` 增加资源行渲染，与玩家行共用同一套 36px 行高与 102px 窗宽；`main.py` 每 100ms 按「危险区有陌生人 → 玩家，否则 → 资源」决策。删除 `GatheringPanel` 与模式切换。

**Tech Stack:** Python 3.11 + tkinter + Pillow + pytest。

**规格：** [2026-11-14-danger-zone-merged-overlay-design.md](../specs/2026-11-14-danger-zone-merged-overlay-design.md)

**开始前注意：** 当前工作树里有采集顾问功能的未提交改动。先跑一遍测试确认基线，并让用户确认把这些改动提交为基线，否则本计划的每个 commit 都会混入旧改动。

---

## 文件结构

| 文件 | 责任 |
|---|---|
| `client/albion_aware/zone_level.py` | 新增。区域表构建/加载与等级判定，纯逻辑 |
| `client/albion_aware/overlay.py` | 悬浮窗。新增资源行渲染、箭头绘制；删除模式图标 |
| `client/albion_aware/main.py` | 应用编排。区域判定、自动提示音、显示决策；删除模式与面板接线 |
| `client/albion_aware/config.py` | 默认配置删除 `gather.mode` |
| `client/albion_aware/lang/{zh-CN,en}.json` | 增加 `gather.short.*`，删除面板专用文案 |
| `client/tools/sync_avalon_maps.py` | 顺带生成 `client/data/zones.json` |
| `client/data/zones.json` | 生成物，随客户端打包 |
| `client/packaging/albion_aware.spec` | datas 加入 `../data/zones.json` |
| `client/tests/test_zone_level.py` | 新增 |
| `client/tests/test_overlay.py` | 资源行与箭头测试；删除模式测试 |
| `client/tests/test_main.py` | 显示/提示音纯函数测试 |
| `client/tests/test_config.py` | 删除 `gather.mode` 断言 |

---

### Task 0: 基线

**Files:** 无代码改动

- [ ] **Step 1: 查看工作树**

Run: `git status --short`

Expected: 有 `gather_*`、`overlay.py`、`main.py`、`config.py` 等未提交改动。

- [ ] **Step 2: 跑基线测试**

Run（cwd=`client`）: `python -m pytest -q`

Expected: 全部 PASS。若有失败，先修好或记录，再继续。

- [ ] **Step 3: 与用户确认并提交基线**

```bash
git add client/albion_aware client/tests client/tools
git commit -m "feat: add gathering advisor client support"
```

若用户不想提交，则跳过本步，但后续每个 commit 只 `git add` 计划点名的文件。

---

### Task 1: 区域等级模块

**Files:**
- Create: `client/albion_aware/zone_level.py`
- Test: `client/tests/test_zone_level.py`

- [ ] **Step 1: 写失败测试**

创建 `client/tests/test_zone_level.py`：

```python
import json

from albion_aware.zone_level import ZoneLevels, build_level_map, is_danger


def test_build_level_map_keeps_four_levels_and_forces_tunnels_black():
    levels = build_level_map({
        "1000": {"pvpType": "safe", "type": "PLAYERCITY_SAFEAREA_02"},
        "1007": {"pvpType": "yellow", "type": "OPENPVP_YELLOW"},
        "3005": {"pvpType": "red", "type": "OPENPVP_RED"},
        "5001": {"pvpType": "safe", "type": "TUNNEL_ROYAL"},
        "6000": {"pvpType": "weird", "type": "OPENPVP"},
        "6001": "not-a-dict",
    })
    assert levels == {"1000": "safe", "1007": "yellow", "3005": "red", "5001": "black"}


def test_load_roundtrip(tmp_path):
    path = tmp_path / "zones.json"
    path.write_text(json.dumps({"version": 1, "zones": {
        "3005": "red", "TNL-001": "black", "9": "bogus"}}), encoding="utf-8")
    levels = ZoneLevels.load(path)
    assert levels.level("3005") == "red"
    assert levels.level("TNL-001") == "black"
    assert levels.level("9") == "unknown"


def test_missing_file_is_empty():
    assert ZoneLevels.load("does-not-exist.json").level("3005") == "unknown"


def test_roads_always_black_even_without_table():
    assert ZoneLevels().level("TNL-042") == "black"


def test_mists_inherit_previous():
    levels = ZoneLevels({"3005": "red"})
    assert levels.level("@MISTS@123", "red") == "red"
    assert levels.level("@MISTSDUNGEON@1-2", "black") == "black"
    assert levels.level("@MISTS@123") == "safe"


def test_compound_ids_fall_back_to_base():
    levels = ZoneLevels({"1234": "black"})
    assert levels.level("1234-5") == "black"
    assert levels.level("1234-5-2") == "black"


def test_empty_id_keeps_previous():
    assert ZoneLevels().level("", "yellow") == "yellow"


def test_unknown_id_is_unknown():
    assert ZoneLevels({"1000": "safe"}).level("7777") == "unknown"


def test_is_danger_only_red_and_black():
    assert is_danger("red") is True
    assert is_danger("black") is True
    assert is_danger("yellow") is False
    assert is_danger("safe") is False
    assert is_danger("unknown") is False
```

- [ ] **Step 2: 跑测试确认失败**

Run（cwd=`client`）: `python -m pytest tests/test_zone_level.py -q`

Expected: FAIL，`ModuleNotFoundError: No module named 'albion_aware.zone_level'`。

- [ ] **Step 3: 实现模块**

创建 `client/albion_aware/zone_level.py`：

```python
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
        level = str(zone.get("pvpType") or "").strip().lower()
        if level not in LEVELS:
            continue
        if str(zone.get("type") or "").startswith("TUNNEL_"):
            level = "black"
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
```

- [ ] **Step 4: 跑测试确认通过**

Run（cwd=`client`）: `python -m pytest tests/test_zone_level.py -q`

Expected: 9 passed。

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/zone_level.py client/tests/test_zone_level.py
git commit -m "feat: map zone ids to pvp levels"
```

---

### Task 2: 生成并打包区域表

**Files:**
- Modify: `client/tools/sync_avalon_maps.py:27,134-140`
- Modify: `client/packaging/albion_aware.spec:7-12`
- Create: `client/data/zones.json`（脚本生成）

- [ ] **Step 1: 修改同步脚本**

在 `client/tools/sync_avalon_maps.py` 第 27 行后追加导入：

```python
from albion_aware.map_index import build_index_records, key3  # noqa: E402
from albion_aware.zone_level import build_level_map  # noqa: E402
```

在 `payload = {"version": 1, "maps": records}` 之前插入：

```python
    levels = build_level_map(zones)
    if not levels:
        raise SystemExit("no zone pvp levels found in zones.json")
    zones_dest = dest.parent / "zones.json"
    zones_payload = {"version": 1, "zones": levels}
    zones_tmp = zones_dest.with_name(zones_dest.name + ".tmp")
    zones_tmp.write_text(
        json.dumps(zones_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8")
    zones_tmp.replace(zones_dest)
```

把返回值改为：

```python
    return {"maps": len(records), "images": available, "missing_images": missing,
            "key_collisions": len(collisions), "zones": len(levels)}
```

- [ ] **Step 2: 生成区域表**

Run（cwd=`client`）: `python tools/sync_avalon_maps.py --no-download`

Expected: 输出 JSON 含 `"zones": 1423`；生成 `client/data/zones.json`。

- [ ] **Step 3: 校验生成物**

Run: `python -c "import json; d=json.load(open(r'D:\work\Albion-Online-OpenRadar\client\data\zones.json',encoding='utf-8')); print(d['version'], len(d['zones']), d['zones']['3005'], d['zones'].get('TNL-001'))"`

Expected: `1 1423 red black`。

- [ ] **Step 4: 打包配置加入文件**

`client/packaging/albion_aware.spec` 的 `datas` 列表改为：

```python
    datas=[
        ("../albion_aware/lang", "albion_aware/lang"),
        ("../data/items.min.json", "data"),
        ("../data/icons", "data/icons"),
        ("../data/avalon", "data/avalon"),
        ("../data/zones.json", "data"),
    ],
```

- [ ] **Step 5: 提交**

```bash
git add client/tools/sync_avalon_maps.py client/packaging/albion_aware.spec client/data/zones.json
git commit -m "build: bundle compact zone pvp level table"
```

---

### Task 3: 显示与提示音的纯函数

**Files:**
- Modify: `client/albion_aware/main.py:68-75`
- Test: `client/tests/test_main.py`

- [ ] **Step 1: 写失败测试**

在 `client/tests/test_main.py` 的导入里加入 `display_mode, sound_for_zone`，并在文件末尾追加：

```python
def test_display_mode_only_shows_players_when_dangerous_and_present():
    assert display_mode(True, True) == "players"
    assert display_mode(True, False) == "resources"
    assert display_mode(False, True) == "resources"
    assert display_mode(False, False) == "resources"


def test_sound_for_zone_follows_danger_levels():
    assert sound_for_zone("red", False) is True
    assert sound_for_zone("black", False) is True
    assert sound_for_zone("safe", True) is False
    assert sound_for_zone("yellow", True) is False
    assert sound_for_zone("unknown", True) is True
    assert sound_for_zone("unknown", False) is False
```

- [ ] **Step 2: 跑测试确认失败**

Run（cwd=`client`）: `python -m pytest tests/test_main.py -q`

Expected: FAIL，`ImportError: cannot import name 'display_mode'`。

- [ ] **Step 3: 实现纯函数**

在 `client/albion_aware/main.py` 的 `normalize_mode` 之前插入：

```python
def display_mode(danger: bool, has_strangers: bool) -> str:
    """危险区有人先看人，否则看资源。"""
    if danger and has_strangers:
        return "players"
    return "resources"


def sound_for_zone(level: str, current: bool) -> bool:
    """红/黑区强制开启提示音，蓝/黄区强制关闭，未知区保持原状。"""
    if level in ("red", "black"):
        return True
    if level in ("safe", "yellow"):
        return False
    return bool(current)
```

- [ ] **Step 4: 跑测试确认通过**

Run（cwd=`client`）: `python -m pytest tests/test_main.py -q`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/main.py client/tests/test_main.py
git commit -m "feat: add overlay content and zone sound helpers"
```

---

### Task 4: 悬浮窗资源行

**Files:**
- Modify: `client/albion_aware/overlay.py:1-40,108-150,213-266`
- Test: `client/tests/test_overlay.py`

- [ ] **Step 1: 写失败测试**

把 `client/tests/test_overlay.py` 顶部导入改为：

```python
import math

from albion_aware.gather_targets import GatherTarget
from albion_aware.models import View
from albion_aware.overlay import (ARROW_SIZE, GLOW_LAYERS, GLOW_STEP, PAD, ROW_H, TOP_H,
                                  WIDTH, OverlayWindow, arrow_points, filter_icon, format_ip,
                                  gather_icon, ip_color, map_icon, sound_icon)
```

在文件末尾追加：

```python
class _ResourceInner:
    def winfo_children(self):
        return []


def _resource_window():
    window = OverlayWindow.__new__(OverlayWindow)
    window.root = _DragRoot()
    window._pos = None
    window.inner = _ResourceInner()
    window._resources_hash = None
    window._images = []
    window._drawn = []
    window._add_resource_row = lambda target: window._drawn.append(target.harvestable_id)
    return window


def _target(harvestable_id=1, distance=23.0, bearing_deg=45.0):
    return GatherTarget(harvestable_id=harvestable_id, kind="Log", tier=6, enchant=2, size=3,
                        x=0.0, y=0.0, is_living=False, distance=distance,
                        bearing_deg=bearing_deg)


def test_render_resources_resizes_to_target_count():
    window = _resource_window()
    window.place_at(10, 20)
    window.render_resources([_target(1), _target(2), _target(3)])
    glow = GLOW_LAYERS * GLOW_STEP * 2
    assert window.root.geometries[-1] == f"{WIDTH}x{PAD * 2 + 3 * ROW_H + TOP_H + glow}+10+20"
    assert window._drawn == [1, 2, 3]


def test_render_resources_skips_unchanged_batch():
    window = _resource_window()
    targets = [_target(1)]
    window.render_resources(targets)
    window.render_resources(targets)
    assert window._drawn == [1]


def test_render_resources_keeps_one_row_when_empty():
    window = _resource_window()
    window.render_resources([])
    glow = GLOW_LAYERS * GLOW_STEP * 2
    assert window.root.geometries[-1] == f"{WIDTH}x{PAD * 2 + ROW_H + TOP_H + glow}+0+0"


def test_render_players_resets_resource_cache():
    window = _resource_window()
    targets = [_target(1)]
    window.render_resources(targets)
    window.render_resources(targets)
    assert window._drawn == [1]
    window.render(View(), lambda _player: None)
    window.render_resources(targets)
    assert window._drawn == [1, 1]


def test_arrow_points_tip_follows_angle():
    east = arrow_points(0)
    assert len(east) == 6
    assert east[0] > ARROW_SIZE / 2
    assert abs(east[1] - ARROW_SIZE / 2) < 0.001
    south = arrow_points(90)
    assert abs(south[0] - ARROW_SIZE / 2) < 0.001
    assert south[1] > ARROW_SIZE / 2


def test_arrow_points_stay_inside_canvas():
    for angle in list(range(0, 360, 15)) + [None, -135, 359.5]:
        assert all(math.isfinite(value) for value in arrow_points(angle))
        assert all(0 <= value <= ARROW_SIZE for value in arrow_points(angle))
```

- [ ] **Step 2: 跑测试确认失败**

Run（cwd=`client`）: `python -m pytest tests/test_overlay.py -q`

Expected: FAIL，`ImportError: cannot import name 'ARROW_SIZE'`。

- [ ] **Step 3: 实现资源行渲染**

在 `client/albion_aware/overlay.py` 顶部导入区加入：

```python
import math

from albion_aware.gather_targets import format_distance, format_tier_enchant, targets_hash
```

在 `PAD = 4` 之后加入常量：

```python
ARROW_SIZE = 10
RESOURCE_MUTED = "#9a9a9a"
RESOURCE_ARROW = "#e6e6e6"
KIND_COLORS = {
    "Log": "#96693c",
    "Rock": "#9696a0",
    "Fiber": "#5fbe78",
    "Hide": "#aa785a",
    "Ore": "#6496c8",
}
KIND_FALLBACK = "#787878"
```

在 `gather_icon` 之前加入（从 `gather_panel.py` 迁入，默认尺寸改为 10）：

```python
def arrow_points(angle_deg: float | None, size: int = ARROW_SIZE) -> list[float]:
    """按屏幕空间角度生成箭头三角形顶点（Canvas 的 y 轴向下）。"""
    if angle_deg is None or not math.isfinite(angle_deg):
        angle_deg = 0.0
    rad = math.radians(angle_deg)
    center = size / 2
    length = size / 2 - 1
    tip = (center + length * math.cos(rad), center + length * math.sin(rad))
    back = (center - length * 0.6 * math.cos(rad), center - length * 0.6 * math.sin(rad))
    wing = length * 0.55
    wing_rad = rad + math.pi / 2
    left = (back[0] + wing * math.cos(wing_rad), back[1] + wing * math.sin(wing_rad))
    right = (back[0] - wing * math.cos(wing_rad), back[1] - wing * math.sin(wing_rad))
    return [tip[0], tip[1], left[0], left[1], right[0], right[1]]
```

在 `__init__` 的 `self._images = []` 之后加入：

```python
        self._resources_hash = None
```

`render()` 开头加入：

```python
        self._resources_hash = None
```

`clear()` 开头加入：

```python
        self._resources_hash = None
```

在 `clear()` 之后加入：

```python
    def render_resources(self, targets) -> None:
        key = targets_hash(targets)
        if key == self._resources_hash:
            return
        self._resources_hash = key
        for child in self.inner.winfo_children():
            child.destroy()
        self._images.clear()
        for target in targets:
            self._add_resource_row(target)
        self._resize(len(targets))

    def invalidate_resources(self) -> None:
        self._resources_hash = None

    def _short_kind(self, kind: str) -> str:
        key = f"gather.short.{kind}"
        text = self.i18n.t(key)
        return text if text != key else (kind[:2].upper() or "--")

    def _add_resource_row(self, target) -> None:
        row = tk.Frame(self.inner, bg=BG, height=ROW_H)
        row.pack(fill="x", padx=PAD)
        row.pack_propagate(False)

        kind = tk.Label(row, text=self._short_kind(target.kind), bg=BG,
                        fg=KIND_COLORS.get(target.kind, KIND_FALLBACK),
                        font=("Segoe UI", 8, "bold"), anchor="w")
        kind.pack(side="left")

        detail = tk.Label(row, text=format_tier_enchant(target.tier, target.enchant),
                          bg=BG, fg=IP_GREY, font=("Segoe UI", 8), anchor="w")
        detail.pack(side="left", padx=(3, 0))

        arrow = tk.Canvas(row, width=ARROW_SIZE, height=ARROW_SIZE, bg=BG,
                          bd=0, highlightthickness=0)
        arrow.pack(side="right")
        if target.bearing_deg is None:
            arrow.create_oval(3, 3, 7, 7, outline=RESOURCE_MUTED, fill="")
        else:
            arrow.create_polygon(arrow_points(target.bearing_deg), fill=RESOURCE_ARROW,
                                 outline="")

        if target.distance is not None:
            tk.Label(row, text=format_distance(target.distance), bg=BG, fg=RESOURCE_MUTED,
                     font=("Segoe UI", 8), anchor="e").pack(side="right", padx=(0, 2))

        for widget in row.winfo_children() + [row]:
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)
```

- [ ] **Step 4: 跑测试确认通过**

Run（cwd=`client`）: `python -m pytest tests/test_overlay.py -q`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/overlay.py client/tests/test_overlay.py
git commit -m "feat: render resource rows inside overlay"
```

---

### Task 5: 删除模式图标

**Files:**
- Modify: `client/albion_aware/overlay.py:35-55,108-150,321-345`
- Test: `client/tests/test_overlay.py`

- [ ] **Step 1: 删除模式测试**

在 `client/tests/test_overlay.py`：

1. 导入里去掉 `gather_icon`。
2. 删除 `test_gather_icon_is_green_in_gather_mode`。
3. 删除 `test_set_mode_swaps_icon_and_exposes_state`。
4. 把 `test_mode_click_invokes_callback_and_breaks` 改为：

```python
def test_filter_click_invokes_callback_and_breaks():
    window = OverlayWindow.__new__(OverlayWindow)
    calls = []
    window._on_filter_click = lambda: calls.append("filter")
    assert window._filter_click() == "break"
    assert calls == ["filter"]
```

- [ ] **Step 2: 跑测试确认失败**

Run（cwd=`client`）: `python -m pytest tests/test_overlay.py -q`

Expected: `AttributeError`/`ImportError` 指向已删除的 `gather_icon` 或 `_mode_click`。

- [ ] **Step 3: 删除模式 UI**

> 注意：此刻 `main.py` 仍引用 `on_mode_click` 与 `set_mode`，应用在 Task 6 完成前无法启动。这是预期的中间状态，单元测试仍应全绿。

在 `client/albion_aware/overlay.py`：

1. 删除 `GATHER_ON`、`GATHER_OFF` 常量。
2. 删除整个 `gather_icon` 函数。
3. 构造函数签名去掉 `on_mode_click=None` 与 `self._on_mode_click = on_mode_click`。
4. 删除 `self._mode = "roam"`、`self._mode_images = ...`、`mode_icon = tk.Label(...)` 以及 `mode_icon.bind(...)`。
5. 删除 `set_mode`、`mode` property、`_mode_click` 三个方法。

- [ ] **Step 4: 跑测试确认通过**

Run（cwd=`client`）: `python -m pytest tests/test_overlay.py -q`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/overlay.py client/tests/test_overlay.py
git commit -m "refactor: drop gather/roam mode icon from overlay"
```

---

### Task 6: 主程序接线与旧面板移除

**Files:**
- Modify: `client/albion_aware/main.py`
- Delete: `client/albion_aware/gather_panel.py`
- Delete: `client/tests/test_gather_panel.py`
- Modify: `client/albion_aware/config.py:26-34`
- Modify: `client/albion_aware/lang/zh-CN.json`、`client/albion_aware/lang/en.json`
- Test: `client/tests/test_config.py`

- [ ] **Step 1: 更新配置测试**

在 `client/tests/test_config.py`：

1. 把 `test_gather_defaults_to_roam_mode` 整段替换为：

```python
def test_gather_defaults_without_mode():
    cfg = default_config()["gather"]
    assert "mode" not in cfg
    assert cfg["kinds"] == ["Log", "Rock", "Fiber", "Hide", "Ore"]
    assert cfg["show_living"] is True
    assert (cfg["tier_min"], cfg["tier_max"]) == (1, 8)
    assert cfg["sort"] == "nearest"
    assert cfg["max_targets"] == 5
```

2. `test_v3_config_gains_gather_defaults` 删掉 `assert cfg.get("gather.mode") == "roam"` 这一行。
3. `test_current_version_keeps_custom_gather_settings` 的配置 JSON 去掉 `"mode": "gather"`，并删掉对应断言。

- [ ] **Step 2: 跑测试确认失败**

Run（cwd=`client`）: `python -m pytest tests/test_config.py -q`

Expected: FAIL，`assert 'mode' not in cfg` 失败。

- [ ] **Step 3: 删除默认模式配置**

`client/albion_aware/config.py` 的 `gather` 段改为：

```python
    "gather": {
        "kinds": ["Log", "Rock", "Fiber", "Hide", "Ore"],
        "show_living": True,
        "tier_min": 1,
        "tier_max": 8,
        "sort": "nearest",
        "max_targets": 5,
    },
```

- [ ] **Step 4: 跑配置测试**

Run（cwd=`client`）: `python -m pytest tests/test_config.py -q`

Expected: 全部 PASS。

- [ ] **Step 5: 增加资源短名文案**

`client/albion_aware/lang/zh-CN.json` 删除 `gather.title`、`gather.empty`、`gather.no_position` 三个键，并加入：

```json
  "gather.short.Log": "木",
  "gather.short.Rock": "石",
  "gather.short.Fiber": "纤",
  "gather.short.Hide": "皮",
  "gather.short.Ore": "矿",
```

`client/albion_aware/lang/en.json` 删除同三个键，并加入：

```json
  "gather.short.Log": "LG",
  "gather.short.Rock": "RK",
  "gather.short.Fiber": "FB",
  "gather.short.Hide": "HD",
  "gather.short.Ore": "OR",
```

保留 `gather.kind.*`（筛选窗口仍在用）。

- [ ] **Step 6: 修改主程序状态初始化**

`client/albion_aware/main.py`：

1. 删除 `from albion_aware.gather_panel import GatheringPanel`。
2. 在 `from albion_aware.gather_targets import ...` 后加入：

```python
from albion_aware.zone_level import ZoneLevels, is_danger
```

3. 删除 `normalize_mode` 函数。
4. 把 `__init__` 中第 160-166 行与 193-203 行两段采集状态合并为一段（放在 `self.window = OverlayWindow(` 之前）：

```python
        # 采集与区域状态必须先于 OverlayWindow 创建：窗口构造会回调 _save_position
        self.gather = GatherStore()
        self.player_pos: tuple[float, float] | None = None
        self._gather_filters = GatherFilter.from_config(self.config)
        self._gather_last_at = 0.0
        self._resource_targets: list = []
        self._zone_levels = ZoneLevels.load(_resource_dir(app_dir) / "data" / "zones.json")
        self._zone_level = "safe"
        self._danger = False
```

注意 `ZoneLevels.load` 使用 `_resource_dir(self.app_dir)`，可在 `self.window` 创建前直接调用；若想复用局部变量，就把 `_resource_dir(app_dir)` 的结果赋给 `resource_dir` 后使用。

5. 构造 `OverlayWindow` 时删除 `on_mode_click=self._toggle_mode,`。
6. 删除第二段重复的 `self.gather = ...`、`self._mode = ...`、`self._gather_panel = ...`、`self.window.set_mode(...)` 以及 `if self._mode == "gather": ...` 块。
7. 保留 `self.window.set_filter_active(not self._gather_filters.is_default())`。

- [ ] **Step 7: 区域切换时判定危险区并自动开关提示音**

把 `_apply` 中 `elif isinstance(event, ZoneChanged):` 分支改为：

```python
            elif isinstance(event, ZoneChanged):
                self._zone_id = event.zone_id
                self.store.clear()
                self.gather.clear()
                self.player_pos = None
                self._resource_targets = []
                self._gather_last_at = 0.0
                self.panel.hide()
                self._zone_level = self._zone_levels.level(event.zone_id, self._zone_level)
                self._danger = is_danger(self._zone_level) or self._zone_level == "unknown"
                self._apply_sound_for_zone(self._zone_level)
                in_roads = is_roads_zone(event.zone_id)
                if in_roads:
                    if not self._in_roads:
                        self.window.flash_map_icon()
                    self._in_roads = True
                else:
                    self._in_roads = False
                if self._map_window is not None and self._map_window.is_open:
                    self._map_window.set_zone(event.zone_id if in_roads else None)
                applied = True
```

在 `_save_position` 之前加入：

```python
    def _apply_sound_for_zone(self, level: str) -> None:
        current = bool(self.config.get("overlay.sound", False))
        enabled = sound_for_zone(level, current)
        if enabled != current:
            self.config.set("overlay.sound", enabled)
            self.config.save()
        self.window.set_sound(enabled)
```

- [ ] **Step 8: 危险区才触发闪光与提示音**

`_apply` 结尾改为：

```python
        after = {player.id for player in self._view_rows()}
        if applied and self._danger and has_new_stranger(before, after):
            self._flash_pending = True
        return applied
```

`_play_sound` 第一行改为：

```python
        if (not bool(self.config.get("overlay.sound", False)) or not self._danger
                or sys.platform != "win32"):
            return
```

- [ ] **Step 9: 刷新时按优先级选择内容**

`_refresh` 中 `self.window.render(view, self._item_power)` 改为：

```python
        if display_mode(self._danger, bool(view.rows)) == "players":
            self.window.render(view, self._item_power)
        else:
            self.window.render_resources(self._resource_targets)
```

- [ ] **Step 10: 主循环、资源刷新、拖动与显隐**

`_drain` 中：

```python
            if self._mode == "gather":
                self._update_gather()
```

改为：

```python
            self._update_gather()
```

`_save_position` 改为：

```python
    def _save_position(self, x: int, y: int) -> None:
        self.config.set("overlay.x", int(x))
        self.config.set("overlay.y", int(y))
        self.config.save()
```

删除 `_toggle_mode`、`_apply_mode` 两个方法。

`_update_gather` 改为：

```python
    def _update_gather(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._gather_last_at < GATHER_REFRESH_S:
            return
        self._gather_last_at = now
        if not has_position(self.player_pos):
            self._resource_targets = []
        else:
            self._resource_targets = select_targets(self.gather.snapshot(), self.player_pos,
                                                     self._gather_filters)
        if display_mode(self._danger, bool(self._rows)) == "resources":
            self.window.render_resources(self._resource_targets)
```

`_toggle_visible` 改为：

```python
    def _toggle_visible(self) -> None:
        if self.window.toggle_visible():
            self._update_gather(force=True)
```

`_apply_gather_settings` 在 `self.window.set_filter_active(...)` 之后加入：

```python
        self.window.invalidate_resources()
```

`_set_language` 删除 `self._gather_panel.set_i18n(self.i18n)`，并在 `self.panel.i18n = self.i18n` 之后加入：

```python
        self.window.invalidate_resources()
```

`_quit` 删除 `self._gather_panel.destroy()`。

- [ ] **Step 11: 删除旧面板与测试**

```bash
git rm client/albion_aware/gather_panel.py client/tests/test_gather_panel.py
```

- [ ] **Step 12: 跑全量测试**

Run（cwd=`client`）: `python -m pytest -q`

Expected: 全部 PASS。若报 `NameError: _gather_panel`，说明还有残留引用，按报错行清理。

- [ ] **Step 13: 提交**

```bash
git add client/albion_aware/main.py client/albion_aware/config.py \
        client/albion_aware/lang/zh-CN.json client/albion_aware/lang/en.json \
        client/tests/test_config.py client/tests/test_overlay.py
git commit -m "feat: scan only in dangerous zones and merge resources into overlay"
```

---

### Task 7: 验证

**Files:** 无新增

- [ ] **Step 1: 全量测试**

Run（cwd=`client`）: `python -m pytest -q`

Expected: 全部 PASS。

- [ ] **Step 2: 启动客户端**

Run（cwd=`client`）: `python -m albion_aware.main`

Expected: 悬浮窗出现，顶栏只有筛选、提示音、查图、穿透警示、连接状态，没有模式图标。

- [ ] **Step 3: 手动验证清单**

1. 停在蓝区：提示音图标为灰，悬浮窗显示资源行（需有自身坐标）。
2. 进入红区或黑区：提示音图标自动点亮；附近出现非队友玩家后立即列出玩家、闪红并响铃。
3. 玩家离开并超过 `player_timeout`：自动切回资源行。
4. 回到蓝区：提示音自动关闭，玩家行消失。
5. 拖动窗口：位置保存；左缘不再出现旧资源小窗。
6. 切换语言：资源短名随语言变化。
7. 修改筛选（如只留 Ore）：资源行立即按新筛选刷新。

- [ ] **Step 4: 记录结果并提交（如有微调）**

```bash
git add -A client
git commit -m "test: verify dangerous-zone overlay behavior"
```

---

## 风险与回滚

- 区域表缺失时所有区为 `unknown`：会一直显示玩家、提示音保持手动设置。可在日志里看到一次加载失败；重新执行 Task 2 生成 `client/data/zones.json` 即可恢复。
- 64 位整数/复合区域 ID 解析只取第一段；遇到新格式时在 `ZoneLevels.level` 里补规则，并加一条测试。
- 回滚：`git revert` 对应 commit；`gather_panel.py` 在 Task 6 才删除，前面任务都可独立保留。

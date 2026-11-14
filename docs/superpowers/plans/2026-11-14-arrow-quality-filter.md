# 资源行带杆箭头 + 层级×附魔品质筛选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把资源行的方向指示从纯三角形改为更直观的带杆箭头，并把采集筛选从「层级区间」改为「T1~T8 × 附魔 0~4」的 40 项品质矩阵。

**Architecture:** 箭头是 `overlay.py` 内的纯几何函数 + Canvas 绘制；品质筛选在 `gather_targets.GatherFilter` 用 `frozenset[tuple[int, int]]` 表示，配置层负责 `"5.1"` 字符串与元组的转换，并做 v4→v5 迁移；设置窗只负责矩阵 UI 与收集字符串列表。

**Tech Stack:** Python 3.10+、tkinter、pytest、PyInstaller。

**规格来源:** `docs/superpowers/specs/2026-11-14-arrow-quality-filter-design.md`

---

### Task 1: 资源行带杆箭头

**Files:**
- Modify: `client/albion_aware/overlay.py:16`（ARROW_SIZE）、`client/albion_aware/overlay.py:54-67`（箭头几何）、`client/albion_aware/overlay.py:302-309`（绘制）
- Test: `client/tests/test_overlay.py:9-11`（导入）、`client/tests/test_overlay.py:348-361`（箭头测试）

- [ ] **Step 1: 写失败测试**

把 `client/tests/test_overlay.py` 的导入改为（`arrow_points` → `arrow_parts`）：

```python
from albion_aware.overlay import (ARROW_SIZE, GLOW_LAYERS, GLOW_STEP, PAD, ROW_H, TOP_H,
                                  WIDTH, OverlayWindow, arrow_parts, filter_icon,
                                  format_ip, ip_color, map_icon, sound_icon)
```

把第 348-361 行两个测试整体替换为：

```python
def test_arrow_parts_head_follows_angle():
    shaft, head = arrow_parts(0)
    assert len(shaft) == 4
    assert len(head) == 6
    assert head[0] > ARROW_SIZE / 2
    assert abs(head[1] - ARROW_SIZE / 2) < 0.001
    assert shaft[0] < ARROW_SIZE / 2
    south_shaft, south_head = arrow_parts(90)
    assert abs(south_head[0] - ARROW_SIZE / 2) < 0.001
    assert south_head[1] > ARROW_SIZE / 2
    assert south_shaft[1] < ARROW_SIZE / 2


def test_arrow_parts_stay_inside_canvas():
    for angle in list(range(0, 360, 15)) + [None, -135, 359.5]:
        shaft, head = arrow_parts(angle)
        points = shaft + head
        assert all(math.isfinite(value) for value in points)
        assert all(0 <= value <= ARROW_SIZE for value in points)


def test_arrow_parts_tip_leads_head():
    center = ARROW_SIZE / 2
    for angle in range(0, 360, 45):
        shaft, head = arrow_parts(angle)
        tip_dist = math.hypot(head[0] - center, head[1] - center)
        back_dist = math.hypot(shaft[2] - center, shaft[3] - center)
        assert tip_dist > back_dist > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_overlay.py -k arrow -v`（cwd: `client`）
Expected: FAIL / ERROR，提示 `ImportError: cannot import name 'arrow_parts'`

- [ ] **Step 3: 实现带杆箭头**

`client/albion_aware/overlay.py` 第 16 行改为：

```python
ARROW_SIZE = 12
```

把第 54-67 行的 `arrow_points` 整体替换为：

```python
def arrow_parts(angle_deg: float | None,
                size: int = ARROW_SIZE) -> tuple[list[float], list[float]]:
    """返回 (杆线段坐标, 三角头坐标)；Canvas 的 y 轴向下。"""
    if angle_deg is None or not math.isfinite(angle_deg):
        angle_deg = 0.0
    rad = math.radians(angle_deg)
    center = size / 2
    length = size / 2 - 1
    dx, dy = math.cos(rad), math.sin(rad)
    tip = (center + length * dx, center + length * dy)
    head_back = (center + length * 0.45 * dx, center + length * 0.45 * dy)
    tail = (center - length * dx, center - length * dy)
    wing = length * 0.42
    wing_x, wing_y = -dy, dx
    left = (head_back[0] + wing * wing_x, head_back[1] + wing * wing_y)
    right = (head_back[0] - wing * wing_x, head_back[1] - wing * wing_y)
    head = [tip[0], tip[1], left[0], left[1], right[0], right[1]]
    shaft = [tail[0], tail[1], head_back[0], head_back[1]]
    return shaft, head
```

把 `_add_resource_row` 中第 302-309 行的箭头块替换为：

```python
        arrow = tk.Canvas(row, width=ARROW_SIZE, height=ARROW_SIZE, bg=BG,
                          bd=0, highlightthickness=0)
        arrow.pack(side="right")
        if target.bearing_deg is None:
            arrow.create_oval(4, 4, 8, 8, outline=RESOURCE_MUTED, fill="")
        else:
            shaft, head = arrow_parts(target.bearing_deg)
            arrow.create_line(*shaft, fill=RESOURCE_ARROW, width=1)
            arrow.create_polygon(head, fill=RESOURCE_ARROW, outline="")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_overlay.py -v`（cwd: `client`）
Expected: 全部 PASS，包含 `test_arrow_parts_head_follows_angle`、`test_arrow_parts_stay_inside_canvas`、`test_arrow_parts_tip_leads_head`、`test_resource_row_text_fits_content_width`

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/overlay.py client/tests/test_overlay.py
git commit -m "feat(overlay): 资源行方向指示改为带杆箭头"
```

---

### Task 2: GatherFilter 品质集合与配置 v5 迁移

**Files:**
- Modify: `client/albion_aware/gather_targets.py:19-58`（常量与 GatherFilter）、`client/albion_aware/gather_targets.py:120`（筛选判定）
- Modify: `client/albion_aware/config.py:6`（版本）、`client/albion_aware/config.py:26-33`（默认值）、`client/albion_aware/config.py:96-110`（迁移）
- Test: `client/tests/test_gather_targets.py`、`client/tests/test_config.py:124-154`

- [ ] **Step 1: 写失败测试（筛选模型）**

在 `client/tests/test_gather_targets.py` 中，导入块改为：

```python
from albion_aware.gather_targets import (
    ALL_QUALITIES,
    GatherFilter,
    format_distance,
    format_tier_enchant,
    has_position,
    select_targets,
    targets_hash,
    to_screen_vector,
)
```

把 `test_tier_range_is_inclusive`（第 61-66 行）替换为：

```python
def test_quality_filter_matches_tier_and_enchant():
    filters = GatherFilter(qualities=frozenset({(5, 1), (5, 2), (6, 0)}))
    nodes = [node(1, 10, tier=5, enchant=1), node(2, 20, tier=5, enchant=0),
             node(3, 30, tier=6, enchant=0), node(4, 40, tier=5, enchant=3)]
    targets = select_targets(nodes, PLAYER, filters)
    assert [t.harvestable_id for t in targets] == [1, 3]


def test_qualities_parsed_from_config_strings():
    class FakeConfig:
        def get(self, key, default=None):
            return {"gather.qualities": ["5.1", "5.2", "6.0"]}.get(key, default)

    filters = GatherFilter.from_config(FakeConfig())
    assert filters.qualities == frozenset({(5, 1), (5, 2), (6, 0)})


def test_invalid_qualities_are_dropped():
    class FakeConfig:
        def get(self, key, default=None):
            return {"gather.qualities": ["5.1", "bogus", "9.1", "2.9", 3.0]}.get(key, default)

    filters = GatherFilter.from_config(FakeConfig())
    assert filters.qualities == frozenset({(5, 1)})


def test_empty_qualities_fall_back_to_all():
    class FakeConfig:
        def get(self, key, default=None):
            return {"gather.qualities": []}.get(key, default)

    assert GatherFilter.from_config(FakeConfig()).qualities == ALL_QUALITIES
```

把 `test_filter_round_trips_config_dict`（第 106-112 行）替换为：

```python
def test_filter_round_trips_config_dict():
    filters = GatherFilter(kinds=frozenset({"Ore", "Log"}),
                           qualities=frozenset({(4, 0), (6, 2)}),
                           sort="tier", max_targets=3, show_living=False)
    data = filters.to_dict()
    assert data["kinds"] == ["Log", "Ore"]
    assert data["qualities"] == ["4.0", "6.2"]
    assert filters.is_default() is False
    assert GatherFilter().is_default() is True
```

- [ ] **Step 2: 写失败测试（配置默认值与迁移）**

`client/tests/test_config.py` 第 124-131 行替换为：

```python
def test_gather_defaults_without_mode():
    cfg = default_config()["gather"]
    assert "mode" not in cfg
    assert "tier_min" not in cfg
    assert "tier_max" not in cfg
    assert cfg["kinds"] == ["Log", "Rock", "Fiber", "Hide", "Ore"]
    assert cfg["show_living"] is True
    assert len(cfg["qualities"]) == 40
    assert cfg["qualities"][0] == "1.0"
    assert cfg["qualities"][-1] == "8.4"
    assert cfg["sort"] == "nearest"
    assert cfg["max_targets"] == 5
```

在 `test_v3_config_gains_gather_defaults` 末尾追加一行：

```python
    assert len(cfg.get("gather.qualities")) == 40
```

把 `test_current_version_keeps_custom_gather_settings`（第 144-154 行）替换为下面两个测试：

```python
def test_current_version_keeps_custom_gather_settings(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": CONFIG_VERSION,
                                "gather": {"kinds": ["Ore"],
                                           "qualities": ["5.1", "5.2"],
                                           "max_targets": 3}}),
                    encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("gather.kinds") == ["Ore"]
    assert cfg.get("gather.qualities") == ["5.1", "5.2"]
    assert cfg.get("gather.max_targets") == 3


def test_v4_tier_range_expands_to_qualities(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": 4,
                                "gather": {"tier_min": 5, "tier_max": 6}}),
                    encoding="utf-8")
    cfg = Config(path)
    qualities = cfg.get("gather.qualities")
    assert len(qualities) == 10
    assert qualities[0] == "5.0"
    assert qualities[-1] == "6.4"
    assert "tier_min" not in cfg.get("gather")
    assert "tier_max" not in cfg.get("gather")
    assert cfg.get("config_version") == CONFIG_VERSION
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_gather_targets.py tests/test_config.py -v`（cwd: `client`）
Expected: FAIL（`ImportError: cannot import name 'ALL_QUALITIES'`、`TypeError: __init__() got an unexpected keyword argument 'qualities'`）

- [ ] **Step 4: 实现 GatherFilter 品质集合**

`client/albion_aware/gather_targets.py` 第 19-58 行（从 `@dataclass(frozen=True)` 到 `is_default`）整体替换为：

```python
ALL_QUALITIES = frozenset(
    (tier, enchant) for tier in range(1, 9) for enchant in range(0, 5)
)


@dataclass(frozen=True)
class GatherFilter:
    kinds: frozenset[str] = frozenset(KIND_ORDER)
    show_living: bool = True
    qualities: frozenset[tuple[int, int]] = ALL_QUALITIES
    sort: str = DEFAULT_SORT
    max_targets: int = DEFAULT_MAX_TARGETS

    @classmethod
    def from_config(cls, config) -> "GatherFilter":
        raw_kinds = config.get("gather.kinds", list(KIND_ORDER)) or []
        kinds = frozenset(kind for kind in raw_kinds if kind in KIND_ORDER) or frozenset(KIND_ORDER)
        sort = config.get("gather.sort", DEFAULT_SORT)
        return cls(
            kinds=kinds,
            show_living=bool(config.get("gather.show_living", True)),
            qualities=qualities_from_config(config.get("gather.qualities")),
            sort=sort if sort in SORT_MODES else DEFAULT_SORT,
            max_targets=_clamp_int(config.get("gather.max_targets", DEFAULT_MAX_TARGETS),
                                   1, 10, DEFAULT_MAX_TARGETS),
        )

    def to_dict(self) -> dict:
        return {
            "kinds": [kind for kind in KIND_ORDER if kind in self.kinds],
            "show_living": self.show_living,
            "qualities": [f"{tier}.{enchant}" for tier, enchant in sorted(self.qualities)],
            "sort": self.sort,
            "max_targets": self.max_targets,
        }

    def is_default(self) -> bool:
        return self == GatherFilter()


def parse_quality(value) -> tuple[int, int] | None:
    """把 "5.1" 解析成 (5, 1)；非法值返回 None。"""
    if not isinstance(value, str) or "." not in value:
        return None
    tier_text, enchant_text = value.split(".", 1)
    try:
        tier, enchant = int(tier_text), int(enchant_text)
    except ValueError:
        return None
    if 1 <= tier <= 8 and 0 <= enchant <= 4:
        return (tier, enchant)
    return None


def qualities_from_config(raw) -> frozenset[tuple[int, int]]:
    """非法元素丢弃；为空或类型不对时回退全选。"""
    if not isinstance(raw, (list, tuple)):
        return ALL_QUALITIES
    parsed = {quality for quality in (parse_quality(item) for item in raw) if quality}
    return frozenset(parsed) or ALL_QUALITIES
```

把第 120 行层级判断替换为：

```python
        if (node.tier, node.enchant or 0) not in filters.qualities:
            continue
```

（`_clamp_int` 保持原样，`select_targets` 其余逻辑不动。）

- [ ] **Step 5: 实现配置 v5 默认值与迁移**

`client/albion_aware/config.py` 第 6 行改为：

```python
CONFIG_VERSION = 5
```

第 26-33 行的 `gather` 默认值改为：

```python
    "gather": {
        "kinds": ["Log", "Rock", "Fiber", "Hide", "Ore"],
        "show_living": True,
        "qualities": [f"{tier}.{enchant}" for tier in range(1, 9) for enchant in range(0, 5)],
        "sort": "nearest",
        "max_targets": 5,
    },
```

`_migrate`（第 96-110 行）整体替换为：

```python
    def _migrate(self, version) -> None:
        """老配置一次性升级：v2 起提示音默认关闭；v3 起换用新的默认热键布局；
        v5 起把层级区间展开为 40 项品质集合。"""
        if isinstance(version, int) and version >= CONFIG_VERSION:
            return
        legacy = version if isinstance(version, int) else 0
        if legacy < 2:
            # 避免城里持续蜂鸣
            self.data["overlay"]["sound"] = False
        if legacy < 3:
            self.data["hotkeys"] = copy.deepcopy(DEFAULT_CONFIG["hotkeys"])
        if legacy < 5:
            self._migrate_qualities()
        self.data["config_version"] = CONFIG_VERSION
        self.save()

    def _migrate_qualities(self) -> None:
        """v4 及更早：把 tier_min~tier_max 展开为 [tier]×[0..4]，再删掉旧键。"""
        gather = self.data.get("gather")
        if not isinstance(gather, dict):
            return
        if "tier_min" not in gather and "tier_max" not in gather:
            return
        low = _tier_value(gather.get("tier_min"), 1)
        high = _tier_value(gather.get("tier_max"), 8)
        if low > high:
            low, high = high, low
        gather["qualities"] = [f"{tier}.{enchant}"
                               for tier in range(low, high + 1)
                               for enchant in range(0, 5)]
        gather.pop("tier_min", None)
        gather.pop("tier_max", None)
```

在 `config.py` 模块级（`_merge` 之后、`class Config` 之前）添加：

```python
def _tier_value(value, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(1, min(8, parsed))
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_gather_targets.py tests/test_config.py -v`（cwd: `client`）
Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add client/albion_aware/gather_targets.py client/albion_aware/config.py client/tests/test_gather_targets.py client/tests/test_config.py
git commit -m "feat(gather): 筛选改为层级×附魔品质集合并迁移旧配置"
```

---

### Task 3: 设置窗品质矩阵与文案

**Files:**
- Modify: `client/albion_aware/gather_settings_window.py`（validate、矩阵 UI、_collect、_reset）
- Modify: `client/albion_aware/lang/zh-CN.json:100-108`
- Modify: `client/albion_aware/lang/en.json:100-108`
- Test: `client/tests/test_gather_settings_window.py`

- [ ] **Step 1: 写失败测试**

`client/tests/test_gather_settings_window.py` 整体替换为：

```python
from albion_aware.gather_settings_window import validate_settings


def values(**overrides):
    base = {
        "kinds": ["Log", "Ore"],
        "show_living": True,
        "qualities": ["1.0", "8.4"],
        "sort": "nearest",
        "max_targets": 5,
    }
    base.update(overrides)
    return base


def test_valid_values_pass():
    assert validate_settings(values()) is None


def test_requires_at_least_one_kind():
    assert validate_settings(values(kinds=[]))[0] == "gather.settings.no_kinds"


def test_requires_at_least_one_quality():
    assert validate_settings(values(qualities=[]))[0] == "gather.settings.no_qualities"


def test_max_targets_range():
    assert validate_settings(values(max_targets=0))[0] == "gather.settings.max_targets_invalid"
    assert validate_settings(values(max_targets=11))[0] == "gather.settings.max_targets_invalid"
    assert validate_settings(values(max_targets="abc"))[0] == "gather.settings.max_targets_invalid"


def test_sort_must_be_known():
    assert validate_settings(values(sort="bogus"))[0] == "gather.settings.sort_invalid"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_gather_settings_window.py -v`（cwd: `client`）
Expected: FAIL，`test_requires_at_least_one_quality` 报 `AttributeError: 'NoneType' object has no attribute '__getitem__'`

- [ ] **Step 3: 实现 validate 与矩阵 UI**

`client/albion_aware/gather_settings_window.py` 第 1-27 行整体替换为：

```python
"""采集筛选设置窗：资源种类、活体开关、品质矩阵、排序与数量。"""
import tkinter as tk

from albion_aware.config import DEFAULT_CONFIG
from albion_aware.gather_targets import (ALL_QUALITIES, DEFAULT_MAX_TARGETS, DEFAULT_SORT,
                                         KIND_ORDER, SORT_MODES)

BG = "#1b1b1b"
FG = "#e6e6e6"
MUTED = "#9a9a9a"


def validate_settings(values: dict) -> tuple[str, str] | None:
    """返回 (错误 key, 出错内容)；全部合法返回 None。"""
    if not values.get("kinds"):
        return ("gather.settings.no_kinds", "")
    if not values.get("qualities"):
        return ("gather.settings.no_qualities", "")
    max_targets = _as_int(values.get("max_targets"))
    if max_targets is None or not 1 <= max_targets <= 10:
        return ("gather.settings.max_targets_invalid", str(values.get("max_targets")))
    if values.get("sort") not in SORT_MODES:
        return ("gather.settings.sort_invalid", "")
    return None


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
```

把构造函数里第 75-87 行从 `tier_row = tk.Frame(...)` 到 `self.tier_max.pack(...)` 的整段替换为品质矩阵：

```python
        quality_box = tk.Frame(self.top, bg=BG)
        quality_box.pack(fill="x", pady=(8, 2))
        tk.Label(quality_box, text=i18n.t("gather.settings.qualities"), bg=BG, fg=MUTED,
                 font=("Segoe UI", 8), anchor="w").grid(row=0, column=0, sticky="w")
        selected = set(values.get("qualities")
                       or [f"{tier}.{enchant}" for tier, enchant in sorted(ALL_QUALITIES)])
        self.quality_vars: dict[tuple[int, int], tk.BooleanVar] = {}
        for column, tier in enumerate(range(1, 9), start=1):
            tk.Label(quality_box, text=i18n.t("gather.settings.tier_column", value=tier),
                     bg=BG, fg=FG, font=("Segoe UI", 8)).grid(row=0, column=column,
                                                              padx=1)
            for row, enchant in enumerate(range(0, 5), start=1):
                if column == 1:
                    tk.Label(quality_box, text=str(enchant), bg=BG, fg=MUTED,
                             font=("Segoe UI", 8)).grid(row=row, column=0)
                text = f"{tier}.{enchant}"
                var = tk.BooleanVar(value=text in selected)
                self.quality_vars[(tier, enchant)] = var
                tk.Checkbutton(quality_box, text=text, variable=var, bg=BG, fg=FG,
                               selectcolor="#2a2a2a", activebackground=BG,
                               activeforeground=FG, font=("Segoe UI", 7),
                               highlightthickness=0, bd=0, padx=0).grid(
                                   row=row, column=column, sticky="w")

        quality_buttons = tk.Frame(self.top, bg=BG)
        quality_buttons.pack(fill="x", pady=(2, 0))
        tk.Button(quality_buttons, text=i18n.t("gather.settings.all"),
                  command=lambda: self._set_all_qualities(True)).pack(side="left")
        tk.Button(quality_buttons, text=i18n.t("gather.settings.clear"),
                  command=lambda: self._set_all_qualities(False)).pack(side="left",
                                                                      padx=(6, 0))
```

把 `_collect`（第 127-135 行）替换为：

```python
    def _collect(self) -> dict:
        return {
            "kinds": [kind for kind, var in self.kind_vars.items() if var.get()],
            "show_living": bool(self.living_var.get()),
            "qualities": [f"{tier}.{enchant}"
                          for (tier, enchant), var in self.quality_vars.items() if var.get()],
            "sort": self.sort_var.get(),
            "max_targets": self.max_targets.get().strip(),
        }

    def _set_all_qualities(self, value: bool) -> None:
        for var in self.quality_vars.values():
            var.set(value)
```

`_save`（第 137-148 行）替换为（只保留 max_targets 转换，删除两行 tier 转换）：

```python
    def _save(self) -> None:
        values = self._collect()
        problem = validate_settings(values)
        if problem:
            key, detail = problem
            self._error.set(self.i18n.t(key, value=detail))
            return
        values["max_targets"] = _as_int(values["max_targets"])
        self._on_save(values)
        self.close()
```

`_reset`（第 150-161 行）替换为：

```python
    def _reset(self) -> None:
        defaults = DEFAULT_CONFIG["gather"]
        for kind, var in self.kind_vars.items():
            var.set(kind in defaults["kinds"])
        self.living_var.set(defaults["show_living"])
        for var in self.quality_vars.values():
            var.set(True)
        self.max_targets.delete(0, "end")
        self.max_targets.insert(0, str(defaults["max_targets"]))
        self.sort_var.set(defaults["sort"])
        self._error.set("")
```

窗口初始位置改为给更高的矩阵留空间（第 50-52 行）：

```python
        self.top.geometry("+%d+%d" % (master.winfo_screenwidth() // 2 - 170,
                                      master.winfo_screenheight() // 2 - 220))
```

- [ ] **Step 4: 更新中英文文案**

`client/albion_aware/lang/zh-CN.json` 第 100 行改为：

```json
  "gather.settings.qualities": "品质（层级 × 附魔）",
  "gather.settings.tier_column": "T{value}",
  "gather.settings.all": "全选",
  "gather.settings.clear": "清空",
```

第 108 行改为：

```json
  "gather.settings.no_qualities": "至少选择一种品质",
```

`client/albion_aware/lang/en.json` 第 100 行改为：

```json
  "gather.settings.qualities": "Quality (tier × enchant)",
  "gather.settings.tier_column": "T{value}",
  "gather.settings.all": "Select all",
  "gather.settings.clear": "Clear",
```

第 108 行改为：

```json
  "gather.settings.no_qualities": "Select at least one quality",
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_gather_settings_window.py tests/test_i18n.py -v`（cwd: `client`）
Expected: 全部 PASS（`test_language_files_share_the_same_key_set` 通过说明中英文键一致）

- [ ] **Step 6: 提交**

```bash
git add client/albion_aware/gather_settings_window.py client/albion_aware/lang/zh-CN.json client/albion_aware/lang/en.json client/tests/test_gather_settings_window.py
git commit -m "feat(gather): 设置窗改为层级×附魔品质矩阵"
```

---

### Task 4: 全量验证、打包与手动验证

**Files:**
- 无代码改动（仅验证与产物）

- [ ] **Step 1: 全量测试**

Run: `python -m pytest -q`（cwd: `client`）
Expected: 全部通过，0 failed（基线为 274 passed，本计划会增减若干测试，数量变化正常）

- [ ] **Step 2: 冒烟启动（确保设置窗可打开）**

Run: `python -m albion_aware.main`（cwd: `client`，运行约 10 秒后关闭）
Expected: 悬浮窗正常出现，无异常 traceback

- [ ] **Step 3: 重建 exe**

先备份随包的 OpenRadar 二进制，再打包，最后恢复：

```bash
cp dist/AlbionAware/OpenRadar.exe dist/AlbionAware/OpenRadar.exe.bak
python -m PyInstaller packaging/albion_aware.spec --noconfirm
cp dist/AlbionAware/OpenRadar.exe.bak dist/AlbionAware/OpenRadar.exe
rm dist/AlbionAware/OpenRadar.exe.bak
```

（cwd: `client`；若仓库中的 OpenRadar 文件名不同，以 `dist/AlbionAware/` 下实际文件为准。）

Expected: `dist/AlbionAware/AlbionAware.exe` 生成，时间戳为本次构建。

- [ ] **Step 4: 手动验证清单（启动新 exe）**

1. 资源行方向指示为「短杆 + 三角头」，四个方向肉眼可辨。
2. 顶栏漏斗图标 → 设置窗出现 T1~T8 列 × 0~4 行共 40 个复选框。
3. 只勾选 `5.1`、`5.2`、`6.0` 保存后：地图上只出现这些品质的资源行。
4. 点「清空」再保存：显示错误「至少选择一种品质」，窗口不关闭。
5. 点「全选」再保存：恢复显示全部层级。
6. 重启程序后筛选仍生效（配置已持久化）。

- [ ] **Step 5: 提交（如有构建脚本/配置微调）**

若 Step 1-4 未产生代码改动则跳过；若有修复：

```bash
git add -A
git commit -m "fix(gather): 品质筛选与箭头手动验证修复"
```

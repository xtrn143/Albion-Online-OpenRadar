# 玩家平均档位威胁判断 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在检测到玩家的第一帧用「平均档位」（每件装备 T级+附魔 的 6 槽平均）替代 IP 显示，并按与自己档位的差距着色，让用户立刻判断打不打得过。

**Architecture:** 物品库从物品唯一名解析单件档位并求 6 槽平均（空槽 0、双手双计）；玩家表提供自己的记录以算出自身基准；悬浮窗行渲染改为接收 `(文字, 颜色)` 的取数函数；详情面板保留 IP 并新增档位行。全部改动在客户端 Python 层，不触碰协议解析与 op143 真实 IP 逻辑。

**Tech Stack:** Python 3.11、Tkinter、pytest；物品库 `client/data/items.min.json`。

**Spec:** `docs/superpowers/specs/2026-11-15-player-gear-threat-design.md`

---

## File Structure

| 文件 | 责任 |
| --- | --- |
| `client/albion_aware/icons.py` | 单件档位解析 `item_gear_level`、`ItemDatabase.gear_level`、`ItemDatabase.gear_average` |
| `client/albion_aware/player_store.py` | `self_player()`：取自己的玩家记录 |
| `client/albion_aware/overlay.py` | `GEAR_RED/GEAR_GREEN`、`gear_color`、`format_gear`；行渲染改 `metric_getter` |
| `client/albion_aware/main.py` | `_self_gear` 缓存、`_refresh_self_gear`、`_gear_metric`、渲染与详情面板接线 |
| `client/albion_aware/detail_panel.py` | 详情面板新增平均档位行 |
| `client/albion_aware/lang/zh-CN.json`、`en.json` | `detail.gear_average`、`detail.gear_self` |
| `client/packaging/README.txt` | 使用说明改为平均档位口径 |
| `client/tools/smoke_overlay.py` | 界面冒烟工具适配新渲染签名 |
| `client/tests/test_icons.py` 等 | 对应测试 |

所有命令的工作目录为 `d:\work\Albion-Online-OpenRadar\client`。

---

### Task 1: 单件档位与 6 槽平均档位

**Files:**
- Modify: `client/albion_aware/icons.py:13-15`（正则）、`:123-138`（在 `average_ip` 后追加方法）
- Test: `client/tests/test_icons.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `client/tests/test_icons.py` 末尾追加：

```python
def gear_db(tmp_path):
    path = tmp_path / "gear.json"
    items = [
        None,
        {"n": "T8_SWORD", "p": 1100, "t": "weapon", "cat": "weapons"},
        {"n": "T8_SHIELD", "p": 1100, "t": "equipmentitem", "cat": "offhands"},
        {"n": "T8_HEAD", "p": 1100, "t": "equipmentitem", "cat": "head"},
        {"n": "T8_ARMOR", "p": 1100, "t": "equipmentitem", "cat": "armors"},
        {"n": "T8_SHOES", "p": 1100, "t": "equipmentitem", "cat": "shoes"},
        {"n": "T8_CAPE", "p": 1100, "t": "equipmentitem", "cat": "capes"},
        {"n": "T8_2H_SWORD", "p": 1100, "h2": True, "t": "weapon", "cat": "weapons"},
        {"n": "T5_MAIN_SWORD@2", "p": 1000, "t": "weapon", "cat": "weapons"},
        {"n": "T5_HEAD", "p": 800, "t": "equipmentitem", "cat": "head"},
        {"n": "T5_ARMOR", "p": 800, "t": "equipmentitem", "cat": "armors"},
        {"n": "T5_SHOES", "p": 800, "t": "equipmentitem", "cat": "shoes"},
        {"n": "T5_OFFHAND", "p": 800, "t": "equipmentitem", "cat": "offhands"},
        {"n": "T5_CAPE", "p": 800, "t": "equipmentitem", "cat": "capes"},
        {"n": "UNIQUE_ITEM", "p": 900, "t": "equipmentitem", "cat": "armors"},
        {"n": "T8_SWORD@4", "p": 1500, "t": "weapon", "cat": "weapons"},
    ]
    path.write_text(json.dumps(items), encoding="utf-8")
    return ItemDatabase.load(path)


def test_gear_level_combines_tier_and_enchant(tmp_path):
    db = gear_db(tmp_path)
    assert db.gear_level(1) == 8.0
    assert db.gear_level(8) == 7.0        # T5_MAIN_SWORD@2
    assert db.gear_level(15) == 12.0      # T8_SWORD@4
    # 唯一名没有层级时按 p 回退：(900 - 300) / 100
    assert db.gear_level(14) == 6.0
    assert db.gear_level(0) is None


def test_gear_average_uses_six_slots_and_counts_two_handed_twice(tmp_path):
    db = gear_db(tmp_path)
    # 主手/副手/头/衣/鞋/披风 全 T8.0
    assert db.gear_average([1, 2, 3, 4, 5, 0, 6, 0, 0, 0]) == 8.0
    # 双手武器占主手+副手两个槽
    assert db.gear_average([7, 0, 3, 4, 5, 0, 6, 0, 0, 0]) == 8.0


def test_gear_average_treats_empty_slots_as_zero(tmp_path):
    db = gear_db(tmp_path)
    # 缺披风：5 件 T8.0 / 6
    assert db.gear_average([1, 2, 3, 4, 5]) == 6.7
    # 只有头衣鞋：3 件 T8.0 / 6
    assert db.gear_average([0, 0, 3, 4, 5]) == 4.0
    # T5.2 武器 + 副手/头/衣/鞋/披风 各 T5.0 = (7 + 5 * 5) / 6
    assert db.gear_average([8, 12, 9, 10, 11, 0, 13, 0, 0, 0]) == 5.3


def test_gear_average_matches_base_ip_scale(tmp_path):
    db = gear_db(tmp_path)
    equip = [1, 2, 3, 4, 5, 0, 6, 0, 0, 0]
    assert db.gear_average(equip) == (db.average_ip(equip) - 300) / 100


def test_gear_average_returns_none_without_combat_items(tmp_path):
    db = gear_db(tmp_path)
    assert db.gear_average([0] * 10) is None
    assert db.gear_average([]) is None
    # 只有背包槽（下标 5）有装备，不算战斗槽
    assert db.gear_average([0, 0, 0, 0, 0, 1, 0, 0, 0, 0]) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_icons.py -q`
Expected: FAIL，报 `AttributeError: 'ItemDatabase' object has no attribute 'gear_level'`

- [ ] **Step 3: 实现**

在 `client/albion_aware/icons.py` 的正则区（`_ENCHANT` 之后）加：

```python
# 层级数字（T8_ -> 8）
_TIER_NUM = re.compile(r"^T(\d+)_")
```

在 `enchant_level` 函数之后加模块级函数：

```python
def item_gear_level(unique: str | None, item_power: float | None = None) -> float | None:
    """单件装备档位 = T级 + 附魔；名字无法解析时按物品基础强度换算。

    物品库的 p 满足 ``p = 300 + 100 × (T级 + 附魔)``（T4.0=700、T5.2=1000）。
    """
    if unique:
        tier = _TIER_NUM.search(unique)
        if tier:
            return float(int(tier.group(1)) + enchant_level(unique))
    if item_power:
        return round((float(item_power) - 300) / 100, 1)
    return None
```

在 `ItemDatabase` 的 `average_ip` 方法之后加：

```python
    def gear_level(self, item_id: int) -> float | None:
        item = self.get(item_id)
        if not item:
            return None
        return item_gear_level(item.get("n"), item.get("p"))

    def gear_average(self, equip: list[int]) -> float | None:
        """6 个战斗槽的平均档位：空槽按 0，双手武器计两次，无装备返回 None。"""
        total = 0.0
        found = False
        for index in COMBAT_SLOTS:
            level = 0.0
            if index < len(equip):
                level = self.gear_level(equip[index]) or 0.0
            if level:
                found = True
            total += level
        main = self.get(equip[0]) if equip else None
        if found and main and main.get("h2") and main.get("cat") == "weapons" \
                and main.get("t") == "weapon":
            # 双手武器同时占主手与副手，副手按同一件装备再计一次
            total += self.gear_level(equip[0]) or 0.0
        return round(total / len(COMBAT_SLOTS), 1) if found else None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_icons.py -q`
Expected: PASS（含原有用例）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/icons.py client/tests/test_icons.py
git commit -m "feat(icons): 按 T级+附魔 计算 6 槽平均档位"
```

---

### Task 2: 玩家表暴露自己

**Files:**
- Modify: `client/albion_aware/player_store.py:63-70`（`is_self` 之后）
- Test: `client/tests/test_player_store.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `client/tests/test_player_store.py` 末尾追加：

```python
def test_self_player_returns_matching_record():
    store = PlayerStore(self_name="MyCharacter")
    store.upsert(1, {"nickname": "Other"})
    store.upsert(2, {"nickname": "mycharacter", "equip": [1]})
    player = store.self_player()
    assert player is not None
    assert player.id == 2


def test_self_player_is_none_without_name_or_match():
    store = PlayerStore()
    store.upsert(1, {"nickname": "Any"})
    assert store.self_player() is None
    store.set_self_name("Nobody")
    assert store.self_player() is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_player_store.py -q`
Expected: FAIL，报 `AttributeError: 'PlayerStore' object has no attribute 'self_player'`

- [ ] **Step 3: 实现**

在 `client/albion_aware/player_store.py` 的 `is_self` 之后加：

```python
    def self_player(self) -> Player | None:
        """自己的玩家记录：自己只是不显示，数据仍保留在表里。"""
        for player in self._players.values():
            if self.is_self(player):
                return player
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_player_store.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/player_store.py client/tests/test_player_store.py
git commit -m "feat(store): 提供 self_player 以计算自身基准"
```

---

### Task 3: 悬浮窗配色与行渲染

**Files:**
- Modify: `client/albion_aware/overlay.py:1`（模块说明）、`:39-50`（颜色常量）、`:110-121`（`ip_color` 之后）、`:238-269`（`render` / `_add_row`）
- Test: `client/tests/test_overlay.py`

- [ ] **Step 1: 写失败测试**

把 `client/tests/test_overlay.py` 顶部导入改为：

```python
from albion_aware.overlay import (ARROW_SIZE, GEAR_GREEN, GEAR_RED, GLOW_LAYERS, GLOW_STEP,
                                  PAD, ROW_H, TOP_H, WIDTH, IP_GREY, IP_ORANGE, IP_YELLOW,
                                  OverlayWindow, arrow_parts, filter_icon, format_gear,
                                  format_ip, gear_color, ip_color, map_icon, sound_icon)
```

在 `test_format_ip` 之后追加：

```python
def test_gear_color_compares_with_self():
    assert gear_color(8.9, 7.0) == GEAR_RED
    assert gear_color(8.0, 7.0) == GEAR_RED
    assert gear_color(7.9, 7.0) == IP_ORANGE
    assert gear_color(7.5, 7.0) == IP_ORANGE
    assert gear_color(7.4, 7.0) == IP_YELLOW
    assert gear_color(6.6, 7.0) == IP_YELLOW
    assert gear_color(6.5, 7.0) == GEAR_GREEN
    assert gear_color(5.0, 7.0) == GEAR_GREEN


def test_gear_color_falls_back_to_absolute_without_self():
    assert gear_color(7.1, None) == IP_ORANGE
    assert gear_color(7.0, None) == IP_YELLOW
    assert gear_color(5.0, None) == IP_YELLOW
    assert gear_color(4.9, None) == GEAR_GREEN
    assert gear_color(None, 7.0) == IP_GREY


def test_format_gear_keeps_one_decimal():
    assert format_gear(None) == "-"
    assert format_gear(7.0) == "7.0"
    assert format_gear(5.3) == "5.3"
```

同时把第 343 行的 `window.render(View(), lambda _player: None)` 改成：

```python
    window.render(View(), lambda _player: ("-", "#d6d6d6"))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_overlay.py -q`
Expected: FAIL，导入 `GEAR_GREEN` 时报 `ImportError`

- [ ] **Step 3: 实现**

`client/albion_aware/overlay.py` 第 1 行模块说明改为：

```python
"""窄条置顶主窗：武器图标 + 平均档位，行点击、闪烁、拖动、穿透。"""
```

在颜色常量区（`IP_ORANGE` 之后）加：

```python
GEAR_RED = "#ff4b3e"
GEAR_GREEN = "#5fbe78"
```

在 `format_ip` 之后加：

```python
def gear_color(gear: float | None, self_gear: float | None) -> str:
    """平均档位配色：有自身基准按差距，否则按绝对档位。"""
    if gear is None:
        return IP_GREY
    if self_gear is None:
        if gear > 7.0:
            return IP_ORANGE
        return IP_YELLOW if gear >= 5.0 else GEAR_GREEN
    diff = gear - self_gear
    if diff >= 1.0:
        return GEAR_RED
    if diff >= 0.5:
        return IP_ORANGE
    if diff <= -0.5:
        return GEAR_GREEN
    return IP_YELLOW


def format_gear(gear: float | None) -> str:
    return "-" if gear is None else f"{gear:.1f}"
```

把 `render` / `_add_row` 改为：

```python
    def render(self, view, metric_getter) -> None:
        self._resources_hash = None
        self._clear_rows()

        for player in view.rows:
            self._add_row(player, metric_getter)
        ...
```

```python
    def _add_row(self, player, metric_getter) -> None:
        row = tk.Frame(self.inner, bg=BG, height=ROW_H)
        row.pack(fill="x", padx=PAD)
        row.pack_propagate(False)

        photo = self._icon_loader(player)
        if photo is not None:
            self._images.append(photo)
            icon_label = tk.Label(row, bg=BG, image=photo)
        else:
            icon_label = tk.Label(row, bg=BG, text="?", fg=IP_GREY, font=("Segoe UI", 9))
        icon_label.pack(side="left")

        text, color = metric_getter(player)
        text_label = tk.Label(row, bg=BG, text=text, fg=color,
                              font=("Segoe UI", 9, "bold"), anchor="e")
        text_label.pack(side="right", fill="x", expand=True)

        for widget in (row, icon_label, text_label):
            widget.bind("<ButtonPress-1>", lambda event, p=player: self._start_drag(event, p))
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", lambda event, p=player: self._end_drag(event, p))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_overlay.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/overlay.py client/tests/test_overlay.py
git commit -m "feat(overlay): 主窗改显示平均档位并按自身档位着色"
```

---

### Task 4: 接线（自身基准、取数函数、详情面板传参）

**Files:**
- Modify: `client/albion_aware/main.py:62`（导入）、`:159-160`（`_self_gear`）、`:208`（初始渲染）、`:427-488`（`_apply` 末尾）、`:495-515`（`_refresh`、新增方法）、`:564-569`（`_on_row_click`）
- Test: `client/tests/test_main.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `client/tests/test_main.py` 的 `test_item_power_falls_back_to_base_ip_without_inspect` 之后追加：

```python
def test_gear_metric_compares_with_self_baseline():
    from types import SimpleNamespace
    from albion_aware.models import Player
    from albion_aware.overlay import GEAR_RED
    app = SimpleNamespace(db=SimpleNamespace(gear_average=lambda _equip: 8.0),
                          _self_gear=7.0)
    assert AlbionAwareApp._gear_metric(app, Player(id=1, equip=[1])) == ("8.0", GEAR_RED)


def test_gear_metric_without_equipment_is_dash():
    from types import SimpleNamespace
    from albion_aware.models import Player
    from albion_aware.overlay import IP_GREY
    app = SimpleNamespace(db=SimpleNamespace(gear_average=lambda _equip: None),
                          _self_gear=7.0)
    assert AlbionAwareApp._gear_metric(app, Player(id=1)) == ("-", IP_GREY)


def test_self_gear_survives_zone_clear():
    from types import SimpleNamespace
    from albion_aware.player_store import PlayerStore
    store = PlayerStore(self_name="Me")
    store.upsert(1, {"nickname": "me", "equip": [1]})
    app = SimpleNamespace(store=store, db=SimpleNamespace(gear_average=lambda _equip: 7.5),
                          _self_gear=None)
    AlbionAwareApp._refresh_self_gear(app)
    assert app._self_gear == 7.5
    # 换图 store.clear() 后缓存仍在
    store.clear()
    AlbionAwareApp._refresh_self_gear(app)
    assert app._self_gear == 7.5


def test_self_gear_stays_none_without_self_player():
    from types import SimpleNamespace
    from albion_aware.player_store import PlayerStore
    app = SimpleNamespace(store=PlayerStore(self_name="Me"),
                          db=SimpleNamespace(gear_average=lambda _equip: 7.5),
                          _self_gear=None)
    AlbionAwareApp._refresh_self_gear(app)
    assert app._self_gear is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_main.py -q`
Expected: FAIL，报 `AttributeError: type object 'AlbionAwareApp' has no attribute '_gear_metric'`

- [ ] **Step 3: 实现**

导入（第 62 行）：

```python
from albion_aware.overlay import ICON_SIZE, OverlayWindow, format_gear, gear_color
```

`__init__` 里 `self._real_ip` 之后加：

```python
        # 自己的平均档位：认出自己后缓存，换图清空玩家表也保留
        self._self_gear: float | None = None
```

第 208 行初始渲染改为：

```python
        self.window.render(View(), self._gear_metric)
```

`_apply` 在 for 循环结束后、`self.party.resolve(self.store)` 之前加：

```python
        self._refresh_self_gear()
```

`_refresh` 里的渲染改为：

```python
        if display_mode(self._scanning(), bool(view.rows)) == "players":
            self.window.render(view, self._gear_metric)
```

在 `_item_power` 之后加：

```python
    def _refresh_self_gear(self) -> None:
        """认出自己就刷新基准；暂时看不到自己时保留上次的值。"""
        player = self.store.self_player()
        if player is None:
            return
        average = self.db.gear_average(player.equip)
        if average is not None:
            self._self_gear = average

    def _gear_metric(self, player) -> tuple[str, str]:
        average = self.db.gear_average(player.equip)
        return format_gear(average), gear_color(average, self._self_gear)
```

`_on_row_click` 改为：

```python
    def _on_row_click(self, player) -> None:
        self.panel.show(player, self._item_power(player),
                        self.party.contains_name(player.nickname),
                        equipment_entries(player, self.db),
                        max(self.window.root.winfo_x() - 226, 0),
                        self.window.root.winfo_y(),
                        gear=self.db.gear_average(player.equip),
                        self_gear=self._self_gear)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_main.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/main.py client/tests/test_main.py
git commit -m "feat(main): 主窗改用平均档位并缓存自身基准"
```

---

### Task 5: 详情面板与文案

**Files:**
- Modify: `client/albion_aware/detail_panel.py:7`（导入）、`:58`（`show` 签名）、`:70-71`（IP 行之后）
- Modify: `client/albion_aware/lang/zh-CN.json:38`、`client/albion_aware/lang/en.json:38`
- Test: `client/tests/test_i18n.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `client/tests/test_i18n.py` 末尾追加：

```python
def test_gear_labels_exist_in_both_languages():
    zh = json.loads((LANG_DIR / "zh-CN.json").read_text(encoding="utf-8"))
    en = json.loads((LANG_DIR / "en.json").read_text(encoding="utf-8"))
    assert zh.get("detail.gear_average") == "平均档位"
    assert en.get("detail.gear_average") == "Avg. gear"
    assert zh.get("detail.gear_self") == "你"
    assert en.get("detail.gear_self") == "You"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_i18n.py -q`
Expected: FAIL，`AssertionError: assert None == '平均档位'`

- [ ] **Step 3: 实现**

`client/albion_aware/lang/zh-CN.json` 在 `"detail.item_power": "IP",` 之后加：

```json
  "detail.gear_average": "平均档位",
  "detail.gear_self": "你",
```

`client/albion_aware/lang/en.json` 在 `"detail.item_power": "IP",` 之后加：

```json
  "detail.gear_average": "Avg. gear",
  "detail.gear_self": "You",
```

`client/albion_aware/detail_panel.py` 导入改为：

```python
from albion_aware.overlay import format_gear, format_ip
```

`show` 签名改为：

```python
    def show(self, player, item_power, is_party: bool, entries, x: int, y: int,
             gear: float | None = None, self_gear: float | None = None) -> None:
```

在 IP 行之后加：

```python
        tk.Label(self.body,
                 text=f"{self.i18n.t('detail.gear_average')}: {format_gear(gear)}   "
                      f"{self.i18n.t('detail.gear_self')}: {format_gear(self_gear)}",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_i18n.py tests/test_detail_panel.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/detail_panel.py client/albion_aware/lang/zh-CN.json client/albion_aware/lang/en.json client/tests/test_i18n.py
git commit -m "feat(detail): 详情面板显示平均档位与自身基准"
```

---

### Task 6: 说明文档、冒烟工具与全量验证

**Files:**
- Modify: `client/packaging/README.txt:6-11`
- Modify: `client/tools/smoke_overlay.py:26-27`

- [ ] **Step 1: 更新使用说明**

`client/packaging/README.txt` 第 4 条替换为：

```text
4. 进入游戏后，屏幕右侧会出现 102px 宽的小窗，只显示非队友玩家：
   武器图标 + 平均档位（每件装备 T级+附魔 的平均值，T5.2 记作 7）。
   平均档位说明：主手/副手/头/衣/鞋/披风 6 个战斗槽取平均，空槽按 0，
   双手武器计两次；检测到玩家即可算出，不需要查看装备。
   颜色按与你自己的平均档位比较：高 1 档以上红色、高 0.5~1 档橙色、
   相差 0.5 档以内黄色、低 0.5 档以上绿色；还没识别到你自己时按
   7 档 / 5 档的绝对档位着色。数值与基础 IP 同源（平7 ≈ 1000 IP）。
   在游戏里点开查看装备后，详情面板仍会显示游戏同源的真实 IP（含专精）。
```

- [ ] **Step 2: 适配冒烟工具**

`client/tools/smoke_overlay.py` 的导入改为：

```python
from albion_aware.overlay import OverlayWindow, format_gear, gear_color
```

`window.render(...)` 一行替换为：

```python
    def metric(player):
        gear = 6.0 + (player.id - 1000) * 0.25
        return format_gear(gear), gear_color(gear, 7.0)

    window.render(view, metric)
```

- [ ] **Step 3: 运行全量测试**

Run: `python -m pytest -q`
Expected: 全部通过（原 296 个 + 本次新增用例）

- [ ] **Step 4: 界面冒烟（人工）**

Run: `python tools/smoke_overlay.py`
Expected: 小窗显示 `6.0`、`6.2`、`6.5`、`6.8`、`7.0`、`7.2`、`7.5`、`7.8` 共 8 行；`6.0`/`6.2`/`6.5` 绿色、`6.8`/`7.0`/`7.2` 黄色、`7.5`/`7.8` 橙色（自身基准 7.0）。

- [ ] **Step 5: 提交**

```bash
git add client/packaging/README.txt client/tools/smoke_overlay.py
git commit -m "docs(client): 说明平均档位的显示与配色口径"
```

---

## 验收清单

- [ ] 主窗每行只显示一个平均档位数字，颜色符合第 4 节规则
- [ ] 详情面板同时有 IP 与 `平均档位 / 你`
- [ ] 换图后自身基准不丢失
- [ ] 未查看装备的玩家也能直接算出平均档位
- [ ] 全量测试通过，冒烟工具显示正常

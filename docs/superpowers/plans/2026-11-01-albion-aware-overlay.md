# AlbionAware 战况悬浮窗实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 做一个常驻游戏画面上方、仅 68px 宽的小窗，只显示当前区域的非队友玩家（武器图标 + 4 位 IP），新玩家出现时闪红边框，点击可看详情。

**Architecture:** 单进程 Python 桌面程序，作为 OpenRadar 的 WebSocket 消费者运行。`radar_client` 连接 `ws://localhost:5001/ws`，`event_parser` 把原始事件转成领域事件，`player_store` 维护玩家表并按“自己/队友”过滤，`overlay` 用 tkinter 无边框置顶窗渲染，`win32_ext` 负责置顶/穿透/全局热键。启动器负责 Npcap 与雷达的环境检测。所有模块独立可测，UI 层不含协议知识。

**Tech Stack:** Python 3.11+、tkinter（stdlib）、websocket-client、Pillow、requests、pystray、pytest、PyInstaller、Inno Setup。

**工作目录约定：** 新代码全部放在 `client/`，与 Go 版雷达并行存在。命令默认在 `client/` 下执行；git 命令在仓库根 `d:\work\Albion-Online-OpenRadar` 下执行。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `client/requirements.txt` / `requirements-dev.txt` | 运行与测试依赖 |
| `client/pytest.ini` | pytest 配置 |
| `client/albion_aware/models.py` | `Player` 数据类、`View`（列表快照） |
| `client/albion_aware/event_parser.py` | OpenRadar 消息 → 领域事件 |
| `client/albion_aware/player_store.py` | 玩家表：增删改、超时清理、过滤、排序、截断 |
| `client/albion_aware/party.py` | 队友名单（自动 + 手动）、持久化 |
| `client/albion_aware/config.py` | 配置读写、损坏备份、语言解析 |
| `client/albion_aware/i18n.py` | 文案加载与格式化 |
| `client/albion_aware/lang/zh-CN.json`、`en.json` | 文案表 |
| `client/albion_aware/icons.py` | 物品库、IPP 计算、图标下载与缓存、占位图 |
| `client/albion_aware/radar_client.py` | WebSocket 连接、批量拆分、指数退避重连 |
| `client/albion_aware/win32_ext.py` | 置顶/不抢焦点/鼠标穿透/全局热键 |
| `client/albion_aware/overlay.py` | 主窗渲染、闪烁、点击、拖动、显隐 |
| `client/albion_aware/detail_panel.py` | 详情面板（装备格、操作按钮） |
| `client/albion_aware/launcher.py` | Npcap 检测、雷达拉起与就绪等待、网卡全选、首启向导 |
| `client/albion_aware/diagnostics.py` | 零流量诊断：加速器识别、分场景步骤、诊断摘要（只进剪贴板） |
| `client/albion_aware/tray.py` | 托盘菜单 |
| `client/albion_aware/main.py` | 组装所有组件、主循环 |
| `client/tools/smoke_overlay.py` | 界面冒烟：注入假玩家表 |
| `client/data/items.min.json` | 物品库（从 `web/ao-bin-dumps/items.min.json` 复制，打包时随程序分发） |
| `client/tests/**` | pytest 用例与离线 JSONL 样本（`tests/fixtures/session.jsonl`） |
| `client/packaging/albion_aware.spec` | PyInstaller 配置 |
| `client/packaging/albion_aware.iss` | Inno Setup 脚本 |
| `client/packaging/NOTICE.txt`、`README.txt` | 分发合规与说明 |

依赖方向（禁止反向引用）：`models ← event_parser ← player_store ← overlay`；`icons` 只被 `overlay` / `detail_panel` 使用；`party` 依赖 `player_store` 的只读接口（通过传入的 store 对象）；`main.py` 是唯一装配点。

---

### Task 1: 项目骨架与测试环境

**Files:**
- Create: `client/requirements.txt`
- Create: `client/requirements-dev.txt`
- Create: `client/pytest.ini`
- Create: `client/albion_aware/__init__.py`
- Test: `client/tests/test_smoke.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_smoke.py
def test_package_importable():
    import albion_aware
    assert albion_aware.__version__ == "0.1.0"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_smoke.py -v`（cwd = `client`）
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware'`

- [ ] **Step 3: 创建骨架文件**

```
# client/requirements.txt
websocket-client==1.8.0
Pillow==10.4.0
requests==2.32.3
pystray==0.19.5
```

```
# client/requirements-dev.txt
-r requirements.txt
pytest==8.3.3
```

```ini
# client/pytest.ini
[pytest]
testpaths = tests
pythonpath = .
addopts = -q
```

```python
# client/albion_aware/__init__.py
"""AlbionAware：只显示非队友玩家的极简悬浮窗。"""

__version__ = "0.1.0"
```

- [ ] **Step 4: 安装依赖并运行测试**

Run: `python -m pip install -r requirements-dev.txt`
Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: 提交**

```bash
git add client/requirements.txt client/requirements-dev.txt client/pytest.ini client/albion_aware/__init__.py client/tests/test_smoke.py
git commit -m "chore(client): scaffold Python package and pytest setup"
```

---

### Task 2: 领域模型

**Files:**
- Create: `client/albion_aware/models.py`
- Test: `client/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_models.py
from albion_aware.models import Player, View


def test_player_defaults_are_empty():
    player = Player(id=42)
    assert player.nickname == ""
    assert player.equip == []
    assert player.first_seen == 0.0


def test_players_do_not_share_mutable_defaults():
    a, b = Player(id=1), Player(id=2)
    a.equip.append(999)
    a.spells.append("Whirlwind")
    assert b.equip == []
    assert b.spells == []


def test_view_holds_rows_and_hidden_count():
    view = View(rows=[Player(id=1), Player(id=2)], hidden=3)
    assert len(view.rows) == 2
    assert view.hidden == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.models'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/models.py
from dataclasses import dataclass, field


@dataclass
class Player:
    """一个玩家在协议里的可观测状态，字段一律就地更新，不重建对象。"""

    id: int
    nickname: str = ""
    guild: str = ""
    alliance: str = ""
    faction: int = 0
    equip: list[int] = field(default_factory=list)
    spells: list[str] = field(default_factory=list)
    hp: int = 0
    max_hp: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0


@dataclass
class View:
    """一次界面刷新所需的玩家快照；hidden 为被折叠的行数。"""

    rows: list[Player] = field(default_factory=list)
    hidden: int = 0
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/models.py client/tests/test_models.py
git commit -m "feat(client): add Player and View domain models"
```

---

### Task 3: 事件解析器

协议字段来自已验证的原型 `simple-players.html`：事件码在参数 `252`；换图响应 `op 41` 的 `param 0`、Join 响应 `op 2` 的 `param 8` 是区 ID；`NewCharacter=29`（`1`昵称、`8`公会、`51`联盟、`53`阵营、`40`装备、`43`技能）；`HealthUpdate=6`（`2` 当前血量、`3` 最大血量）；`Move=3`；`Leave=1`（`0` 为离开者 id）；队伍事件 `231/233/234/235/236`。

**Files:**
- Create: `client/albion_aware/event_parser.py`
- Test: `client/tests/test_event_parser.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_event_parser.py
from albion_aware.event_parser import (
    PartyEvent,
    PlayerLeft,
    PlayerSeen,
    PlayerUpdated,
    ZoneChanged,
    parse_message,
)


def frame(params, kind="event"):
    return {"code": kind, "dictionary": {"parameters": params}}


def test_new_character_maps_all_known_fields():
    events = parse_message(frame({
        "252": 29, "0": 12345, "1": "Razoth", "8": "Hoard",
        "51": "SEASONS", "53": 2, "40": [0, 1234, 5678], "43": ["Whirlwind"],
    }))
    assert isinstance(events[0], PlayerSeen)
    assert events[0].player_id == 12345
    assert events[0].fields == {
        "nickname": "Razoth", "guild": "Hoard", "alliance": "SEASONS",
        "faction": 2, "equip": [0, 1234, 5678], "spells": ["Whirlwind"],
    }


def test_missing_optional_fields_are_omitted():
    events = parse_message(frame({"252": 29, "0": 7}))
    assert events[0].fields == {}


def test_leave_removes_player():
    events = parse_message(frame({"252": 1, "0": 99}))
    assert isinstance(events[0], PlayerLeft)
    assert events[0].player_id == 99


def test_health_update():
    events = parse_message(frame({"252": 6, "0": 99, "2": 300, "3": 1200}))
    assert events[0].fields == {"hp": 300, "max_hp": 1200}


def test_move_only_touches_player():
    events = parse_message(frame({"252": 3, "0": 99}))
    assert isinstance(events[0], PlayerUpdated)
    assert events[0].fields == {}


def test_zone_change_from_response_op41():
    events = parse_message({"code": "response", "dictionary": {"parameters": {"253": 41, "0": "TNL-001-2"}}})
    assert isinstance(events[0], ZoneChanged)
    assert events[0].zone_id == "TNL-001-2"


def test_join_response_op2_uses_param8():
    events = parse_message({"code": "response", "dictionary": {"parameters": {"253": 2, "8": "0311"}}})
    assert events[0].zone_id == "0311"


def test_party_event_is_forwarded_raw():
    events = parse_message(frame({"252": 233, "0": 555, "1": 12345}))
    assert isinstance(events[0], PartyEvent)
    assert events[0].code == 233
    assert events[0].parameters["1"] == 12345


def test_unknown_and_request_messages_are_ignored():
    assert parse_message(frame({"252": 999})) == []
    assert parse_message(frame({"252": 41}, kind="request")) == []


def test_dictionary_may_be_json_string():
    raw = '{"code":"event","dictionary":"{\\"parameters\\":{\\"252\\":29,\\"0\\":7}}"}'
    import json
    events = parse_message(json.loads(raw))
    assert events[0].player_id == 7
    assert events[0].fields == {}


def test_malformed_dictionary_does_not_raise():
    assert parse_message({"code": "event", "dictionary": "{not json"}) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_event_parser.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.event_parser'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/event_parser.py
"""把 OpenRadar 的 WebSocket 消息转换为与协议无关的领域事件。"""
import json
from dataclasses import dataclass, field
from typing import Any

EVENT_CODE_KEY = "252"
OP_CODE_KEY = "253"
PARTY_CODES = {231, 233, 234, 235, 236}


@dataclass
class PlayerSeen:
    player_id: int
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlayerUpdated:
    player_id: int
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlayerLeft:
    player_id: int


@dataclass
class ZoneChanged:
    zone_id: str


@dataclass
class PartyEvent:
    code: int
    parameters: dict[str, Any]


DomainEvent = PlayerSeen | PlayerUpdated | PlayerLeft | ZoneChanged | PartyEvent


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract(message: dict) -> tuple[str, dict]:
    """返回 (消息类型, 参数字典)；dictionary 可能是对象也可能是 JSON 字符串。"""
    dictionary = message.get("dictionary") or {}
    if isinstance(dictionary, str):
        try:
            dictionary = json.loads(dictionary)
        except json.JSONDecodeError:
            return "", {}
    if not isinstance(dictionary, dict):
        return "", {}
    parameters = dictionary.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {}
    return str(message.get("code") or ""), parameters


def _character_fields(p: dict) -> dict:
    fields: dict[str, Any] = {}
    if isinstance(p.get("1"), str):
        fields["nickname"] = p["1"]
    if isinstance(p.get("8"), str):
        fields["guild"] = p["8"]
    if isinstance(p.get("51"), str):
        fields["alliance"] = p["51"]
    faction = _as_int(p.get("53"))
    if faction is not None:
        fields["faction"] = faction
    equip = p.get("40")
    if isinstance(equip, list):
        fields["equip"] = [_as_int(x) or 0 for x in equip]
    spells = p.get("43")
    if isinstance(spells, list):
        fields["spells"] = [str(x) for x in spells]
    return fields


def parse_message(message: dict) -> list[DomainEvent]:
    code, p = extract(message)

    if code == "response":
        op = _as_int(p.get(OP_CODE_KEY))
        if op in (41, 2):
            zone = p.get("0" if op == 41 else "8")
            if isinstance(zone, (str, int)) and str(zone).strip():
                return [ZoneChanged(str(zone))]
        return []

    if code != "event":
        return []

    event = _as_int(p.get(EVENT_CODE_KEY))
    player_id = _as_int(p.get("0"))

    if event == 1 and player_id is not None:
        return [PlayerLeft(player_id)]
    if event == 29 and player_id is not None:
        return [PlayerSeen(player_id, _character_fields(p))]
    if event == 6 and player_id is not None:
        fields: dict[str, Any] = {}
        hp, max_hp = _as_int(p.get("2")), _as_int(p.get("3"))
        if hp is not None:
            fields["hp"] = hp
        if max_hp is not None:
            fields["max_hp"] = max_hp
        return [PlayerUpdated(player_id, fields)]
    if event == 3 and player_id is not None:
        return [PlayerUpdated(player_id, {})]
    if event in PARTY_CODES:
        return [PartyEvent(event, p)]
    return []
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_event_parser.py -v`
Expected: PASS（11 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/event_parser.py client/tests/test_event_parser.py
git commit -m "feat(client): parse OpenRadar events into domain events"
```

---

### Task 4: 玩家表

规则：自己（昵称匹配）与队友（队友名单命中）不进列表；`Leave` 立即移除；60 秒无更新移除；排序默认“最新出现优先”，可选“IP 从高到低”；超出 6 行折叠为 `+N`。

**Files:**
- Create: `client/albion_aware/player_store.py`
- Test: `client/tests/test_player_store.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_player_store.py
from albion_aware.models import Player
from albion_aware.player_store import PlayerStore


class StubParty:
    def __init__(self, names=()):
        self.names = {n.strip().lower() for n in names}

    def contains_name(self, name):
        return (name or "").strip().lower() in self.names


def test_upsert_reports_new_player_and_keeps_first_seen():
    store = PlayerStore(clock=lambda: 100.0)
    player, is_new = store.upsert(1, {"nickname": "Razoth"})
    assert is_new is True
    assert player.nickname == "Razoth"
    assert player.first_seen == 100.0

    store = PlayerStore(clock=lambda: 200.0)
    store.upsert(1, {"nickname": "Razoth"}, now=100.0)
    updated, is_new = store.upsert(1, {"guild": "Hoard"}, now=200.0)
    assert is_new is False
    assert updated.first_seen == 100.0
    assert updated.guild == "Hoard"


def test_leave_removes_player():
    store = PlayerStore()
    store.upsert(1, {"nickname": "Razoth"})
    assert store.remove(1) is True
    assert store.get(1) is None


def test_prune_removes_players_idle_longer_than_timeout():
    store = PlayerStore(timeout=60.0)
    store.upsert(1, {"nickname": "Old"}, now=10.0)
    store.upsert(2, {"nickname": "Fresh"}, now=100.0)
    removed = store.prune(now=120.0)
    assert removed == [1]
    assert store.get(2) is not None


def test_self_is_filtered_by_nickname_case_insensitively():
    store = PlayerStore(self_name="MyCharacter")
    store.upsert(1, {"nickname": "mycharacter"})
    store.upsert(2, {"nickname": "Razoth"})
    view = store.view(StubParty(), max_rows=10, now=100.0)
    assert [p.id for p in view.rows] == [2]


def test_party_members_are_filtered_out():
    store = PlayerStore()
    store.upsert(1, {"nickname": "Buddy"})
    store.upsert(2, {"nickname": "Razoth"})
    view = store.view(StubParty(["buddy"]), max_rows=10)
    assert [p.id for p in view.rows] == [2]


def test_unknown_nickname_is_visible():
    store = PlayerStore(self_name="Mine")
    store.upsert(1, {})
    view = store.view(StubParty(), max_rows=10)
    assert [p.id for p in view.rows] == [1]


def test_recent_sort_is_newest_first():
    store = PlayerStore()
    store.upsert(1, {"nickname": "A"}, now=10.0)
    store.upsert(2, {"nickname": "B"}, now=20.0)
    store.upsert(3, {"nickname": "C"}, now=30.0)
    view = store.view(StubParty(), max_rows=10)
    assert [p.id for p in view.rows] == [3, 2, 1]


def test_ip_sort_is_high_to_low_and_unknown_last():
    store = PlayerStore()
    store.upsert(1, {"nickname": "A"}, now=10.0)
    store.upsert(2, {"nickname": "B"}, now=20.0)
    store.upsert(3, {"nickname": "C"}, now=30.0)
    view = store.view(StubParty(), max_rows=10, sort_mode="ip", ip_getter=lambda p: {1: 900, 2: 1200}.get(p.id))
    assert [p.id for p in view.rows] == [2, 1, 3]


def test_overflow_counts_folded_rows():
    store = PlayerStore()
    for pid in range(1, 9):
        store.upsert(pid, {"nickname": f"P{pid}"}, now=float(pid))
    view = store.view(StubParty(), max_rows=6)
    assert len(view.rows) == 6
    assert view.hidden == 2


def test_clear_empties_store():
    store = PlayerStore()
    store.upsert(1, {"nickname": "A"})
    store.clear()
    assert store.view(StubParty(), max_rows=10).rows == []


def test_upsert_ignores_unknown_and_reserved_fields():
    store = PlayerStore()
    player, _ = store.upsert(1, {"id": 999, "first_seen": 0.0, "password": "x", "guild": "Hoard"})
    assert player.id == 1
    assert player.guild == "Hoard"
    assert not hasattr(player, "password")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_player_store.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.player_store'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/player_store.py
"""玩家表：唯一事实来源，负责增删改、超时清理与展示过滤。"""
import time
from dataclasses import fields

from albion_aware.models import Player, View

_RESERVED = {"id", "first_seen", "last_seen"}


class PlayerStore:
    def __init__(self, self_name: str = "", timeout: float = 60.0, clock=time.time):
        self._players: dict[int, Player] = {}
        self._self_name = (self_name or "").strip().lower()
        self.timeout = timeout
        self._clock = clock

    def set_self_name(self, name: str) -> None:
        self._self_name = (name or "").strip().lower()

    def get(self, player_id: int) -> Player | None:
        return self._players.get(player_id)

    def upsert(self, player_id: int, fields: dict, now: float | None = None) -> tuple[Player, bool]:
        now = self._clock() if now is None else now
        player = self._players.get(player_id)
        is_new = player is None
        if is_new:
            player = Player(id=player_id, first_seen=now)
            self._players[player_id] = player
        allowed = {f.name for f in fields(Player)} - _RESERVED
        for key, value in fields.items():
            if key in allowed and value is not None:
                setattr(player, key, value)
        player.last_seen = now
        return player, is_new

    def touch(self, player_id: int, now: float | None = None) -> None:
        now = self._clock() if now is None else now
        player = self._players.get(player_id)
        if player is not None:
            player.last_seen = now

    def remove(self, player_id: int) -> bool:
        return self._players.pop(player_id, None) is not None

    def clear(self) -> None:
        self._players.clear()

    def prune(self, now: float | None = None) -> list[int]:
        now = self._clock() if now is None else now
        stale = [pid for pid, p in self._players.items() if now - p.last_seen > self.timeout]
        for pid in stale:
            del self._players[pid]
        return stale

    def is_self(self, player: Player) -> bool:
        if not self._self_name:
            return False
        return player.nickname.strip().lower() == self._self_name

    def known_names(self) -> dict[str, int]:
        """小写昵称 → 玩家 id，供队友事件的名称匹配使用。"""
        return {p.nickname.strip().lower(): p.id for p in self._players.values() if p.nickname}

    def view(self, party, max_rows: int = 6, sort_mode: str = "recent",
             ip_getter=None, now: float | None = None) -> View:
        now = self._clock() if now is None else now
        self.prune(now)
        rows = [
            p for p in self._players.values()
            if not self.is_self(p) and not party.contains_name(p.nickname)
        ]
        if sort_mode == "ip" and ip_getter is not None:
            rows.sort(key=lambda p: (-(ip_getter(p) if ip_getter(p) is not None else -1), -p.first_seen))
        else:
            rows.sort(key=lambda p: -p.first_seen)
        shown = rows[:max_rows]
        return View(rows=shown, hidden=max(len(rows) - len(shown), 0))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_player_store.py -v`
Expected: PASS（11 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/player_store.py client/tests/test_player_store.py
git commit -m "feat(client): player store with filtering, pruning and overflow"
```

---

### Task 5: 队友名单

自动：队伍事件里出现且能在玩家表命中的 id / 昵称加入名单。手动：点击详情面板加入。持久化到 `party.json`。

**Files:**
- Create: `client/albion_aware/party.py`
- Test: `client/tests/test_party.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_party.py
import json

from albion_aware.party import PartyList
from albion_aware.player_store import PlayerStore


def test_add_and_contains_is_case_insensitive():
    party = PartyList()
    party.add_name("Buddy")
    assert party.contains_name("buddy")
    assert not party.contains_name("Razoth")
    assert party.contains_name("") is False


def test_remove_name():
    party = PartyList()
    party.add_name("Buddy")
    party.remove_name("BUDDY")
    assert not party.contains_name("Buddy")


def test_persistence_roundtrip(tmp_path):
    path = tmp_path / "party.json"
    party = PartyList(path)
    party.add_name("Buddy")
    party.save()
    loaded = PartyList(path)
    assert loaded.contains_name("buddy")


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "party.json"
    path.write_text("{not json", encoding="utf-8")
    party = PartyList(path)
    assert party.names == set()


def test_add_by_id_resolves_nickname_from_store():
    store = PlayerStore()
    store.upsert(12345, {"nickname": "Buddy"})
    party = PartyList()
    party.add_by_id(12345, store)
    assert party.contains_name("Buddy")


def test_add_by_id_defers_until_nickname_known():
    store = PlayerStore()
    store.upsert(12345, {})
    party = PartyList()
    party.add_by_id(12345, store)
    assert party.contains_name("") is False
    store.upsert(12345, {"nickname": "Buddy"}, now=100.0)
    party.resolve(store)
    assert party.contains_name("Buddy")


def test_handle_event_marks_numeric_member_ids():
    store = PlayerStore()
    store.upsert(12345, {"nickname": "Buddy"})
    party = PartyList()
    party.handle_event({"252": 233, "0": 1, "1": 12345}, store)
    assert party.contains_name("Buddy")


def test_handle_event_marks_matching_nickname_strings():
    store = PlayerStore()
    store.upsert(12345, {"nickname": "Buddy"})
    party = PartyList()
    party.handle_event({"252": 231, "0": 1, "2": "Buddy"}, store)
    assert party.contains_name("buddy")


def test_handle_event_ignores_unknown_numbers():
    store = PlayerStore()
    party = PartyList()
    party.handle_event({"252": 233, "1": 99999}, store)
    assert party.names == set()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_party.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.party'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/party.py
"""队友名单：昵称为主键，支持自动事件与手动标记，落盘到 party.json。"""
import json
import os
from pathlib import Path


def _normalize(name) -> str:
    return (name or "").strip().lower()


class PartyList:
    def __init__(self, path: str | Path | None = None):
        self._names: set[str] = set()
        self._pending_ids: set[int] = set()
        self.path = Path(path) if path else None
        if self.path is not None:
            self._load()

    @property
    def names(self) -> set[str]:
        return set(self._names)

    def contains_name(self, name) -> bool:
        key = _normalize(name)
        return bool(key) and key in self._names

    def add_name(self, name) -> None:
        key = _normalize(name)
        if key:
            self._names.add(key)

    def remove_name(self, name) -> None:
        self._names.discard(_normalize(name))

    def add_by_id(self, player_id: int, store) -> None:
        player = store.get(player_id)
        if player is not None and player.nickname:
            self.add_name(player.nickname)
        else:
            self._pending_ids.add(player_id)

    def resolve(self, store) -> None:
        for player_id in list(self._pending_ids):
            player = store.get(player_id)
            if player is not None and player.nickname:
                self.add_name(player.nickname)
                self._pending_ids.discard(player_id)

    def handle_event(self, parameters: dict, store) -> None:
        known = store.known_names()
        for key, value in parameters.items():
            if key == "252":
                continue
            if isinstance(value, int) and not isinstance(value, bool) and value > 10000:
                self.add_by_id(value, store)
            elif isinstance(value, str) and _normalize(value) in known:
                self.add_name(value)

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        names = raw.get("names") if isinstance(raw, dict) else None
        if isinstance(names, list):
            for name in names:
                self.add_name(name)

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"names": sorted(self._names)}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_party.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/party.py client/tests/test_party.py
git commit -m "feat(client): persistent party list with auto and manual marking"
```

---

### Task 6: 配置与语言解析

**Files:**
- Create: `client/albion_aware/config.py`
- Test: `client/tests/test_config.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_config.py
import json

from albion_aware.config import Config, default_config, resolve_language


def test_missing_file_yields_defaults(tmp_path):
    cfg = Config(tmp_path / "config.json")
    assert cfg.get("max_rows") == 6
    assert cfg.get("language") == "auto"


def test_save_and_reload_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(path)
    cfg.set("self_name", "MyCharacter")
    cfg.set("overlay.x", 1200)
    cfg.save()
    reloaded = Config(path)
    assert reloaded.get("self_name") == "MyCharacter"
    assert reloaded.get("overlay.x") == 1200


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("max_rows") == 6
    assert (tmp_path / "config.json.bak").exists()


def test_partial_config_is_merged_with_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"self_name": "X"}), encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("self_name") == "X"
    assert cfg.get("hotkeys.toggle_click_through") == "F10"


def test_language_auto_detects_chinese_windows():
    assert resolve_language("auto", langid=0x0804) == "zh-CN"
    assert resolve_language("auto", langid=0x0404) == "zh-CN"


def test_language_auto_falls_back_to_english():
    assert resolve_language("auto", langid=0x0409) == "en"
    assert resolve_language("auto", langid=0x0411) == "en"


def test_explicit_language_wins():
    assert resolve_language("zh-TW", langid=0x0409) == "zh-CN"
    assert resolve_language("en", langid=0x0804) == "en"


def test_default_config_is_not_shared():
    a, b = default_config(), default_config()
    a["hotkeys"]["mark_party"] = "F7"
    assert b["hotkeys"]["mark_party"] == "F9"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.config'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/config.py
"""配置读写、损坏备份与语言解析。"""
import copy
import json
from pathlib import Path

DEFAULT_CONFIG = {
    "language": "auto",
    "self_name": "",
    "player_timeout": 60,
    "max_rows": 6,
    "sort_mode": "recent",
    "icon_cache_days": 30,
    "hotkeys": {
        "toggle_click_through": "F10",
        "mark_party": "F9",
        "toggle_visible": "F8",
    },
    "overlay": {"x": None, "y": None},
    "radar": {
        "base_url": "http://localhost:5001",
        "ws_url": "ws://localhost:5001/ws",
    },
}

ZH_LANGIDS = {0x0804: "zh-CN", 0x0404: "zh-TW", 0x0C04: "zh-HK", 0x1004: "zh-SG"}


def default_config() -> dict:
    return copy.deepcopy(DEFAULT_CONFIG)


def windows_language_id() -> int:
    try:
        import ctypes
        return int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
    except Exception:
        return 0


def resolve_language(setting: str, langid: int | None = None) -> str:
    setting = (setting or "auto").strip()
    if setting in ("zh-CN", "zh-TW", "zh-HK"):
        return "zh-CN"
    if setting == "en":
        return "en"
    if langid is None:
        langid = windows_language_id()
    return "zh-CN" if ZH_LANGIDS.get(langid) else "en"


def _merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


class Config:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = default_config()
        self.load()

    def load(self) -> dict:
        if not self.path.exists():
            return self.data
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("config root must be an object")
        except (OSError, ValueError, json.JSONDecodeError):
            self._backup()
            self.data = default_config()
            return self.data
        self.data = _merge(default_config(), raw)
        return self.data

    def get(self, dotted: str, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def language(self) -> str:
        return resolve_language(self.get("language", "auto"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _backup(self) -> None:
        try:
            self.path.replace(self.path.with_suffix(self.path.suffix + ".bak"))
        except OSError:
            pass
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS（8 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/config.py client/tests/test_config.py
git commit -m "feat(client): config with defaults, backup and language resolution"
```

---

### Task 7: 多语言文案

**Files:**
- Create: `client/albion_aware/i18n.py`
- Create: `client/albion_aware/lang/zh-CN.json`
- Create: `client/albion_aware/lang/en.json`
- Test: `client/tests/test_i18n.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_i18n.py
from pathlib import Path

from albion_aware.i18n import I18n

LANG_DIR = Path(__file__).resolve().parents[1] / "albion_aware" / "lang"


def test_chinese_text_is_loaded():
    i18n = I18n("zh-CN", LANG_DIR)
    assert i18n.t("tray.show") == "显示"


def test_english_text_is_loaded():
    i18n = I18n("en", LANG_DIR)
    assert i18n.t("tray.show") == "Show"


def test_unknown_key_returns_key():
    i18n = I18n("en", LANG_DIR)
    assert i18n.t("no.such.key") == "no.such.key"


def test_unknown_language_falls_back_to_english():
    i18n = I18n("pt-BR", LANG_DIR)
    assert i18n.t("tray.show") == "Show"


def test_format_placeholders():
    i18n = I18n("en", LANG_DIR)
    assert i18n.t("about.version", version="1.0.0") == "Version 1.0.0"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_i18n.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.i18n'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/i18n.py
"""文案加载：主语言缺失时回落到英文，再缺失则返回 key。"""
import json
from pathlib import Path

DEFAULT_LANG_DIR = Path(__file__).parent / "lang"


def _load(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


class I18n:
    def __init__(self, lang: str = "en", lang_dir: str | Path | None = None):
        base = Path(lang_dir) if lang_dir else DEFAULT_LANG_DIR
        self.lang = lang
        self._primary = _load(base / f"{lang}.json")
        self._fallback = _load(base / "en.json")

    def t(self, key: str, **kwargs) -> str:
        text = self._primary.get(key) or self._fallback.get(key) or key
        if not isinstance(text, str):
            return key
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
```

```json
// client/albion_aware/lang/zh-CN.json
{
  "app.title": "AlbionAware",
  "status.connected": "已连接",
  "status.disconnected": "未连接",
  "tray.show": "显示",
  "tray.hide": "隐藏",
  "tray.click_through": "鼠标穿透",
  "tray.reset_position": "重置位置",
  "tray.language": "语言",
  "tray.language.auto": "跟随系统",
  "tray.language.zh": "中文",
  "tray.language.en": "English",
  "tray.feedback": "反馈问题",
  "tray.about": "关于",
  "tray.quit": "退出",
  "overlay.unknown_ip": "-",
  "overlay.more": "+{count}",
  "detail.mark_party": "标记队友",
  "detail.unmark_party": "取消队友",
  "detail.copy_name": "复制名字",
  "detail.item_power": "IP",
  "detail.guild": "公会",
  "detail.alliance": "联盟",
  "detail.first_seen": "首次发现",
  "detail.last_seen": "最近更新",
  "detail.potion": "药水",
  "detail.food": "食物",
  "detail.spells": "技能",
  "wizard.title": "首次启动设置",
  "wizard.language": "界面语言",
  "wizard.self_name": "你的角色名",
  "wizard.self_name_hint": "用于在列表里排除自己",
  "wizard.next": "下一步",
  "wizard.skip": "跳过",
  "diag.title": "抓不到游戏数据",
  "diag.no_npcap": "未检测到 Npcap，请先安装",
  "diag.npcap_not_running": "Npcap 服务未运行，请以管理员身份启动",
  "diag.no_traffic": "60 秒内没有收到游戏数据包",
  "diag.accelerator": "我使用加速器",
  "diag.direct": "我没有使用加速器",
  "diag.select_all": "刷新并全选网卡",
  "diag.copy_and_open": "复制诊断信息并打开反馈页",
  "diag.npcap_download": "安装 Npcap（打开官网）",
  "diag.select_all_done": "已选择 {count} 个网卡",
  "diag.accelerator.thunder": "雷神：把加速模式改成「模式三 / 路由模式」，再点上面的「刷新并全选网卡」。",
  "diag.accelerator.exitlag": "ExitLag：必须把游戏改成 Route 模式；默认 WFP 模式在任何抓包工具下都看不到游戏包。",
  "diag.accelerator.uu": "UU / 迅游 / 奇游：改用「虚拟网卡 / 路由」模式，不要用进程加速。",
  "diag.accelerator.generic": "把加速器改成虚拟网卡或路由模式，然后点上面的「刷新并全选网卡」。",
  "diag.direct.firewall": "确认 Windows 防火墙或安全软件没有拦截至 OpenRadar 的流量。",
  "diag.direct.process": "确认游戏已启动，并且已经进入某个区域。",
  "diag.direct.restart": "关闭 OpenRadar 后重新启动，再点「刷新并全选网卡」。",
  "diag.generic.one": "确认 Npcap 已安装并运行。",
  "diag.generic.two": "点「刷新并全选网卡」。",
  "diag.generic.three": "仍无数据时，点「复制诊断信息并打开反馈页」。",
  "feedback.title": "反馈问题",
  "about.version": "版本 {version}",
  "about.license": "包含 OpenRadar（MIT，作者 Nouuu）",
  "common.ok": "确定",
  "common.cancel": "取消"
}
```

```json
// client/albion_aware/lang/en.json
{
  "app.title": "AlbionAware",
  "status.connected": "Connected",
  "status.disconnected": "Disconnected",
  "tray.show": "Show",
  "tray.hide": "Hide",
  "tray.click_through": "Click-through",
  "tray.reset_position": "Reset position",
  "tray.language": "Language",
  "tray.language.auto": "Follow system",
  "tray.language.zh": "中文",
  "tray.language.en": "English",
  "tray.feedback": "Feedback",
  "tray.about": "About",
  "tray.quit": "Quit",
  "overlay.unknown_ip": "-",
  "overlay.more": "+{count}",
  "detail.mark_party": "Mark as party",
  "detail.unmark_party": "Unmark party",
  "detail.copy_name": "Copy name",
  "detail.item_power": "IP",
  "detail.guild": "Guild",
  "detail.alliance": "Alliance",
  "detail.first_seen": "First seen",
  "detail.last_seen": "Last update",
  "detail.potion": "Potion",
  "detail.food": "Food",
  "detail.spells": "Spells",
  "wizard.title": "First run setup",
  "wizard.language": "Interface language",
  "wizard.self_name": "Your character name",
  "wizard.self_name_hint": "Used to hide yourself from the list",
  "wizard.next": "Next",
  "wizard.skip": "Skip",
  "diag.title": "No game data received",
  "diag.no_npcap": "Npcap not found, please install it",
  "diag.npcap_not_running": "Npcap service is not running, start it as administrator",
  "diag.no_traffic": "No game packets received in 60 seconds",
  "diag.accelerator": "I use an accelerator",
  "diag.direct": "I do not use an accelerator",
  "diag.select_all": "Refresh and select all adapters",
  "diag.copy_and_open": "Copy diagnostics and open feedback page",
  "diag.npcap_download": "Install Npcap (open website)",
  "diag.select_all_done": "{count} adapters selected",
  "diag.accelerator.thunder": "Thunder: switch the accelerator to route mode, then hit \"Refresh and select all adapters\".",
  "diag.accelerator.exitlag": "ExitLag: you must use Route mode. Its default WFP mode is invisible to every packet capture tool.",
  "diag.accelerator.uu": "UU / Xunyou / Qiyou: use virtual-adapter or route mode instead of process mode.",
  "diag.accelerator.generic": "Switch your accelerator to virtual-adapter or route mode, then hit \"Refresh and select all adapters\".",
  "diag.direct.firewall": "Make sure Windows Firewall or your security suite is not blocking OpenRadar.",
  "diag.direct.process": "Make sure the game is running and you have entered a zone.",
  "diag.direct.restart": "Restart OpenRadar, then hit \"Refresh and select all adapters\".",
  "diag.generic.one": "Make sure Npcap is installed and running.",
  "diag.generic.two": "Hit \"Refresh and select all adapters\".",
  "diag.generic.three": "If there is still no data, copy the diagnostics and open the feedback page.",
  "feedback.title": "Feedback",
  "about.version": "Version {version}",
  "about.license": "Includes OpenRadar (MIT, by Nouuu)",
  "common.ok": "OK",
  "common.cancel": "Cancel"
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_i18n.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/i18n.py client/albion_aware/lang client/tests/test_i18n.py
git commit -m "feat(client): bilingual strings with english fallback"
```

---

### Task 8: 物品库、IP 与图标缓存

物品库直接复用仓库里的 `web/ao-bin-dumps/items.min.json`（数组下标即物品 id，条目字段 `n` 唯一名、`p` 物品强度）。图标来源 `https://render.albiononline.com/v1/item/<唯一名>.png`。战斗槽沿用雷达算法：装备下标 0–4 与 8。

> 注：打包的 dump 只有唯一名（`T6_MAIN_SWORD`），没有官方本地化名（如 “Master's Sword”）。悬停/详情显示 `MAIN SWORD` 这类去层级后的英文名，不再伪造中文译名。

**Files:**
- Create: `client/albion_aware/icons.py`
- Test: `client/tests/test_icons.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_icons.py
import json

from albion_aware.icons import COMBAT_SLOTS, EQUIP_SLOTS, IconCache, ItemDatabase


def make_db(tmp_path):
    path = tmp_path / "items.json"
    items = [None, {"n": "T6_MAIN_SWORD", "p": 900, "cat": "weapons", "t": "weapon"}]
    for index in range(2, 12):
        items.append({"n": f"ITEM_{index}", "p": 900, "cat": "armor", "t": "equipmentitem"})
    path.write_text(json.dumps(items), encoding="utf-8")
    return ItemDatabase.load(path)


def test_lookup_unique_and_display_name(tmp_path):
    db = make_db(tmp_path)
    assert db.unique_name(1) == "T6_MAIN_SWORD"
    assert db.display_name(1) == "MAIN SWORD"
    assert db.unique_name(0) is None


def test_display_name_strips_enchant_suffix(tmp_path):
    db = make_db(tmp_path)
    db._items[1] = {"n": "T6_MAIN_SWORD@3", "p": 1200}
    assert db.display_name(1) == "MAIN SWORD"


def test_slot_mapping_covers_all_detail_panel_slots():
    assert EQUIP_SLOTS["mainhand"] == 0
    assert EQUIP_SLOTS["bag"] == 7
    assert EQUIP_SLOTS["potion"] == 8
    assert EQUIP_SLOTS["food"] == 9
    assert COMBAT_SLOTS == (0, 1, 2, 3, 4, 8)


def test_average_ip_only_uses_combat_slots(tmp_path):
    db = make_db(tmp_path)
    equip = [1, 1, 1, 1, 1, 99, 99, 99, 2, 99]
    assert db.average_ip(equip) == 900


def test_average_ip_returns_none_without_valid_items(tmp_path):
    db = make_db(tmp_path)
    assert db.average_ip([0, 0]) is None
    assert db.average_ip([]) is None


def test_icon_is_downloaded_once(tmp_path):
    db = make_db(tmp_path)
    calls = []

    def fetch(url, dest):
        calls.append(url)
        dest.write_bytes(b"fake-png")
        return True

    cache = IconCache(tmp_path / "cache", db, fetch=fetch)
    first = cache.get(1)
    second = cache.get(1)
    assert first == second
    assert len(calls) == 1
    assert first.read_bytes() == b"fake-png"


def test_failed_download_uses_placeholder(tmp_path):
    db = make_db(tmp_path)
    cache = IconCache(tmp_path / "cache", db, fetch=lambda url, dest: False)
    path = cache.get(1)
    assert path.exists()
    assert path.name.startswith("_placeholder_")


def test_unknown_item_uses_placeholder(tmp_path):
    db = make_db(tmp_path)
    cache = IconCache(tmp_path / "cache", db, fetch=lambda url, dest: False)
    assert cache.get(0).name.startswith("_placeholder_")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_icons.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.icons'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/icons.py
"""物品库、平均物品强度、武器图标下载与本地缓存。"""
import json
import re
import urllib.parse
from pathlib import Path

from PIL import Image, ImageDraw

RENDER_URL = "https://render.albiononline.com/v1/item/{name}.png?size={size}"
_TIER = re.compile(r"^T\d+_")
_ENCHANT = re.compile(r"@\d+$")

EQUIP_SLOTS = {
    "mainhand": 0,
    "offhand": 1,
    "head": 2,
    "chest": 3,
    "shoes": 4,
    "cape": 5,
    "mount": 6,
    "bag": 7,
    "potion": 8,
    "food": 9,
}
COMBAT_SLOTS = (0, 1, 2, 3, 4, 8)


class ItemDatabase:
    def __init__(self, items: list):
        self._items = {
            index: entry
            for index, entry in enumerate(items)
            if isinstance(entry, dict) and entry.get("n")
        }

    @classmethod
    def load(cls, path: str | Path) -> "ItemDatabase":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(raw if isinstance(raw, list) else [])

    def get(self, item_id: int) -> dict | None:
        return self._items.get(int(item_id))

    def unique_name(self, item_id: int) -> str | None:
        item = self.get(item_id)
        return item.get("n") if item else None

    def display_name(self, item_id: int) -> str | None:
        unique = self.unique_name(item_id)
        if not unique:
            return None
        base = _ENCHANT.sub("", _TIER.sub("", unique))
        return base.replace("_", " ")

    def average_ip(self, equip: list[int]) -> int | None:
        total = valid = 0
        for index in COMBAT_SLOTS:
            if index >= len(equip):
                continue
            item = self.get(equip[index])
            power = int(item.get("p") or 0) if item else 0
            if power > 0:
                total += power
                valid += 1
        return round(total / valid) if valid else None


class IconCache:
    def __init__(self, cache_dir: str | Path, db: ItemDatabase, fetch=None, size: int = 60):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db = db
        self.size = size
        self._fetch = fetch or self._http_fetch

    def get(self, item_id: int) -> Path:
        unique = self.db.unique_name(item_id)
        if not unique:
            return self.placeholder("unknown")
        dest = self.cache_dir / f"{urllib.parse.quote(unique, safe='')}.png"
        if dest.exists():
            return dest
        url = RENDER_URL.format(name=urllib.parse.quote(unique, safe=''), size=self.size)
        if self._fetch(url, dest) and dest.exists():
            return dest
        return self.placeholder(self._category(item_id))

    def placeholder(self, category: str = "unknown") -> Path:
        dest = self.cache_dir / f"_placeholder_{category or 'unknown'}.png"
        if dest.exists():
            return dest
        colors = {
            "weapons": (150, 150, 165),
            "armor": (120, 135, 155),
            "consumable": (145, 120, 95),
        }
        color = colors.get(category, (105, 105, 110))
        image = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((4, 4, self.size - 4, self.size - 4), radius=6, fill=color + (215,))
        image.save(dest, format="PNG")
        return dest

    def _category(self, item_id: int) -> str:
        item = self.db.get(item_id)
        return str(item.get("cat") or "unknown") if item else "unknown"

    @staticmethod
    def _http_fetch(url: str, dest: Path) -> bool:
        import requests
        try:
            response = requests.get(url, timeout=5)
        except requests.RequestException:
            return False
        if response.status_code != 200 or not response.content:
            return False
        dest.write_bytes(response.content)
        return True
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_icons.py -v`
Expected: PASS（8 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/icons.py client/tests/test_icons.py
git commit -m "feat(client): item database, IP calculation and icon cache"
```

---

### Task 9: WebSocket 客户端

**Files:**
- Create: `client/albion_aware/radar_client.py`
- Test: `client/tests/test_radar_client.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_radar_client.py
import json

from albion_aware.radar_client import next_delay, parse_frames


def test_parse_single_frame():
    raw = json.dumps({"code": "event", "dictionary": {"parameters": {"252": 29, "0": 7}}})
    frames = parse_frames(raw)
    assert frames[0]["code"] == "event"
    assert frames[0]["dictionary"]["parameters"]["0"] == 7


def test_parse_batch_frame():
    raw = json.dumps({"type": "batch", "messages": [
        {"code": "event", "dictionary": {"parameters": {"252": 29, "0": 1}}},
        {"code": "response", "dictionary": {"parameters": {"253": 41, "0": "TNL-001"}}},
    ]})
    frames = parse_frames(raw)
    assert len(frames) == 2
    assert frames[1]["code"] == "response"


def test_dictionary_json_string_is_decoded():
    inner = json.dumps({"parameters": {"252": 1, "0": 42}})
    raw = json.dumps({"code": "event", "dictionary": inner})
    frames = parse_frames(raw)
    assert frames[0]["dictionary"]["parameters"]["0"] == 42


def test_invalid_payloads_return_empty():
    assert parse_frames("not json") == []
    assert parse_frames(json.dumps([1, 2, 3])) == []
    assert parse_frames(json.dumps({"code": "event"})) == []


def test_next_delay_doubles_and_caps():
    assert next_delay(1.0, 30.0) == 2.0
    assert next_delay(4.0, 30.0) == 8.0
    assert next_delay(20.0, 30.0) == 30.0
    assert next_delay(30.0, 30.0) == 30.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_radar_client.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.radar_client'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/radar_client.py
"""连接 OpenRadar 的 WebSocket，拆分批次并处理指数退避重连。"""
import json
import threading


def next_delay(current: float, max_delay: float = 30.0) -> float:
    return min(current * 2, max_delay)


def parse_frames(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    if data.get("type") == "batch":
        messages = data.get("messages")
        if not isinstance(messages, list):
            return []
    else:
        messages = [data]

    frames: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        dictionary = message.get("dictionary")
        if isinstance(dictionary, str):
            try:
                dictionary = json.loads(dictionary)
            except json.JSONDecodeError:
                continue
        if not isinstance(dictionary, dict):
            continue
        frames.append({"code": message.get("code"), "dictionary": dictionary})
    return frames


class RadarClient:
    def __init__(self, url: str, on_frames=None, on_state=None, max_delay: float = 30.0):
        self.url = url
        self.max_delay = max_delay
        self._on_frames = on_frames or (lambda frames: None)
        self._on_state = on_state or (lambda state: None)
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="radar-client", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _handle(self, raw) -> None:
        frames = parse_frames(raw)
        if frames:
            self._on_frames(frames)

    def _run(self) -> None:
        import websocket
        delay = 1.0
        while not self._stopping.is_set():
            self._on_state("connecting")
            self._ws = websocket.WebSocketApp(
                self.url,
                on_message=lambda _ws, message: self._handle(message),
                on_open=lambda _ws: self._on_state("connected"),
                on_close=lambda _ws, *_args: self._on_state("disconnected"),
            )
            try:
                self._ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception:
                self._on_state("disconnected")
            if self._stopping.is_set():
                break
            self._stopping.wait(delay)
            delay = next_delay(delay, self.max_delay)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_radar_client.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/radar_client.py client/tests/test_radar_client.py
git commit -m "feat(client): websocket client with batching and backoff"
```

---

### Task 10: Win32 置顶、穿透与全局热键

**Files:**
- Create: `client/albion_aware/win32_ext.py`
- Test: `client/tests/test_win32_ext.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_win32_ext.py
import pytest

from albion_aware.win32_ext import MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse_hotkey


def test_function_keys():
    assert parse_hotkey("F10") == (0, 0x79)
    assert parse_hotkey("f8") == (0, 0x77)


def test_modifiers_are_combined():
    assert parse_hotkey("Ctrl+F10") == (MOD_CONTROL, 0x79)
    assert parse_hotkey("Alt+Shift+F9") == (MOD_ALT | MOD_SHIFT, 0x78)


def test_unknown_hotkey_raises():
    with pytest.raises(ValueError):
        parse_hotkey("F13")
    with pytest.raises(ValueError):
        parse_hotkey("Hyper+F5")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_win32_ext.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.win32_ext'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/win32_ext.py
"""Win32 窗口扩展样式与全局热键；非 Windows 平台下所有调用安全空转。"""
import ctypes
import sys
import threading
import time

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WM_HOTKEY = 0x0312

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

_KEY_CODES = {f"F{index}": 0x6F + index for index in range(1, 13)}
_KEY_CODES.update({
    "Insert": 0x2D, "Delete": 0x2E, "Home": 0x24, "End": 0x25,
    "PageUp": 0x21, "PageDown": 0x22, "Tab": 0x09, "Esc": 0x1B,
})
_MODIFIERS = {"Alt": MOD_ALT, "Ctrl": MOD_CONTROL, "Control": MOD_CONTROL,
              "Shift": MOD_SHIFT, "Win": MOD_WIN}


def parse_hotkey(text: str) -> tuple[int, int]:
    """把 "Ctrl+F10" 解析为 (修饰键位掩码, 虚拟键码)。不可识别时抛 ValueError。"""
    parts = [part.strip() for part in str(text or "").split("+") if part.strip()]
    if not parts:
        raise ValueError("empty hotkey")
    modifiers = 0
    for part in parts[:-1]:
        modifier = _MODIFIERS.get(part.capitalize() if part.capitalize() in _MODIFIERS else part)
        if modifier is None:
            raise ValueError(f"unknown modifier: {part}")
        modifiers |= modifier
    key = parts[-1]
    code = _KEY_CODES.get(key.upper() if key.upper().startswith("F") else key)
    if code is None:
        raise ValueError(f"unknown key: {key}")
    return modifiers, code


def _user32():
    return ctypes.windll.user32


def _with_style(hwnd: int, set_bits: int, clear_bits: int) -> None:
    if sys.platform != "win32":
        return
    style = _user32().GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style | set_bits) & ~clear_bits
    _user32().SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def make_noactivate(hwnd: int) -> None:
    """置顶、不抢焦点、不进 Alt+Tab。"""
    _with_style(hwnd, WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW, 0)


def set_click_through(hwnd: int, enabled: bool) -> None:
    if enabled:
        _with_style(hwnd, WS_EX_TRANSPARENT, 0)
    else:
        _with_style(hwnd, 0, WS_EX_TRANSPARENT)


class HotkeyListener(threading.Thread):
    """在后台线程用 RegisterHotKey + PeekMessage 监听全局热键。"""

    def __init__(self, bindings: dict[str, callable]):
        super().__init__(name="hotkey-listener", daemon=True)
        self._bindings = [(parse_hotkey(text), callback) for text, callback in bindings.items()]
        self._stopping = threading.Event()

    def stop(self) -> None:
        self._stopping.set()

    def run(self) -> None:
        if sys.platform != "win32":
            return
        user32 = _user32()
        registered = [index for index, ((mods, vk), _) in enumerate(self._bindings, start=1)
                      if user32.RegisterHotKey(None, index, mods, vk)]
        try:
            message = ctypes.wintypes.MSG()
            while not self._stopping.is_set():
                if user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                    if message.message == WM_HOTKEY:
                        index = int(message.wParam)
                        if 1 <= index <= len(self._bindings):
                            self._bindings[index - 1][1]()
                else:
                    time.sleep(0.05)
        finally:
            for index in registered:
                user32.UnregisterHotKey(None, index)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_win32_ext.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/win32_ext.py client/tests/test_win32_ext.py
git commit -m "feat(client): win32 overlay styles and global hotkeys"
```

---

### Task 11: 悬浮主窗

**Files:**
- Create: `client/albion_aware/overlay.py`
- Test: `client/tests/test_overlay.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_overlay.py
from albion_aware.overlay import format_ip, ip_color


def test_ip_color_thresholds():
    assert ip_color(None) == "#d6d6d6"
    assert ip_color(750) == "#d6d6d6"
    assert ip_color(800) == "#e8c04a"
    assert ip_color(1000) == "#e8c04a"
    assert ip_color(1001) == "#ff7a45"
    assert ip_color(1400) == "#ff7a45"


def test_format_ip():
    assert format_ip(None) == "-"
    assert format_ip(1250) == "1250"
    assert format_ip(900) == "900"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.overlay'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/overlay.py
"""68px 无边框置顶主窗：武器图标 + IP，行点击、闪烁、拖动、穿透。"""
import tkinter as tk

import albion_aware.win32_ext as win32

WIDTH = 68
ROW_H = 26
PAD = 4
BORDER = 2
BG = "#141414"
FLASH_ON = "#ff3b30"
FLASH_STEPS = 10
FLASH_INTERVAL_MS = 200
DRAG_MODIFIER = 0x0004  # Ctrl

IP_GREY = "#d6d6d6"
IP_YELLOW = "#e8c04a"
IP_ORANGE = "#ff7a45"
STATUS_ON = "#3fb950"
STATUS_OFF = "#6b6b6b"


def ip_color(item_power: int | None) -> str:
    if item_power is None:
        return IP_GREY
    if item_power > 1000:
        return IP_ORANGE
    if item_power >= 800:
        return IP_YELLOW
    return IP_GREY


def format_ip(item_power: int | None) -> str:
    return "-" if item_power is None else str(int(item_power))


class OverlayWindow:
    def __init__(self, i18n, icon_loader, on_row_click, on_more_click, on_drag_end):
        self.i18n = i18n
        self._icon_loader = icon_loader          # (Player) -> ImageTk.PhotoImage | None
        self._on_row_click = on_row_click
        self._on_more_click = on_more_click
        self._on_drag_end = on_drag_end

        self.root = tk.Tk()
        self.root.title(i18n.t("app.title"))
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)

        self.border = tk.Frame(self.root, bg=BG, padx=BORDER, pady=BORDER)
        self.border.pack(fill="both", expand=True)
        self.status = tk.Label(self.border, text="●", bg=BG, fg=STATUS_OFF,
                               font=("Segoe UI", 5), anchor="e")
        self.status.pack(fill="x")
        self.inner = tk.Frame(self.border, bg=BG)
        self.inner.pack(fill="both", expand=True)

        for widget in (self.border, self.inner):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)

        self._drag_origin = None
        self._flash_job = None
        self._flash_step = 0
        self._images = []
        self._click_through = False

        self.root.update_idletasks()
        self._apply_styles()

    # ---------- 位置与尺寸 ----------
    def place_at(self, x: int, y: int) -> None:
        self.root.geometry(f"+{int(x)}+{int(y)}")

    def reset_position(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.place_at(screen_w - WIDTH - 8, int(screen_h / 3))
        self._on_drag_end(self.root.winfo_x(), self.root.winfo_y())

    def _resize(self, row_count: int) -> None:
        height = PAD * 2 + max(row_count, 1) * ROW_H + 8  # +8 为顶部状态点
        geometry = self.root.winfo_geometry()
        position = geometry.split("+", 1)[1] if "+" in geometry else "0+0"
        self.root.geometry(f"{WIDTH}x{height}+{position}")

    # ---------- 渲染 ----------
    def render(self, view, ip_getter) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        self._images.clear()

        for player in view.rows:
            self._add_row(player, ip_getter)

        if view.hidden:
            more = tk.Label(self.inner, text=self.i18n.t("overlay.more", count=view.hidden),
                            bg=BG, fg=IP_GREY, font=("Segoe UI", 8), anchor="center")
            more.pack(fill="x", pady=(1, 1))
            more.bind("<Button-1>", lambda _event: self._on_more_click())

        self._resize(len(view.rows) + (1 if view.hidden else 0))

    def _add_row(self, player, ip_getter) -> None:
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

        power = ip_getter(player)
        text_label = tk.Label(row, bg=BG, text=format_ip(power), fg=ip_color(power),
                              font=("Segoe UI", 9, "bold"), anchor="e")
        text_label.pack(side="right", fill="x", expand=True)

        for widget in (row, icon_label, text_label):
            widget.bind("<Button-1>", lambda _event, p=player: self._on_row_click(p))

    def clear(self) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        self._images.clear()
        self._resize(1)

    # ---------- 闪烁 ----------
    def flash(self) -> None:
        if self._flash_job is not None:
            self.root.after_cancel(self._flash_job)
        self._flash_step = 0
        self._flash_tick()

    def _flash_tick(self) -> None:
        if self._flash_step >= FLASH_STEPS:
            self.border.configure(bg=BG)
            self._flash_job = None
            return
        self.border.configure(bg=FLASH_ON if self._flash_step % 2 == 0 else BG)
        self._flash_step += 1
        self._flash_job = self.root.after(FLASH_INTERVAL_MS, self._flash_tick)

    # ---------- 系统行为 ----------
    def _apply_styles(self) -> None:
        try:
            win32.make_noactivate(int(self.root.wm_frame(), 16))
        except Exception:
            pass

    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        try:
            win32.set_click_through(int(self.root.wm_frame(), 16), enabled)
        except Exception:
            pass

    @property
    def click_through(self) -> bool:
        return self._click_through

    def set_status(self, connected: bool) -> None:
        self.status.configure(fg=STATUS_ON if connected else STATUS_OFF)

    def toggle_visible(self) -> bool:
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            return True
        self.root.withdraw()
        return False

    def close(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        self.root.mainloop()

    # ---------- 拖动 ----------
    def _start_drag(self, event) -> None:
        if not (event.state & DRAG_MODIFIER):
            return
        self._drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event) -> None:
        if self._drag_origin is None:
            return
        offset_x, offset_y = self._drag_origin
        self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def _end_drag(self, _event) -> None:
        if self._drag_origin is None:
            return
        self._drag_origin = None
        self._on_drag_end(self.root.winfo_x(), self.root.winfo_y())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/overlay.py client/tests/test_overlay.py
git commit -m "feat(client): 68px always-on-top overlay window"
```

---

### Task 12: 详情面板

**Files:**
- Create: `client/albion_aware/detail_panel.py`
- Test: `client/tests/test_detail_panel.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_detail_panel.py
from albion_aware.detail_panel import equipment_entries, time_ago
from albion_aware.icons import ItemDatabase
from albion_aware.models import Player


def make_db(tmp_path):
    import json
    path = tmp_path / "items.json"
    items = [None, {"n": "T6_MAIN_SWORD", "p": 900}, {"n": "T6_BAG", "p": 900},
             {"n": "T6_POTION", "p": 0}, {"n": "T6_FOOD", "p": 0}]
    path.write_text(json.dumps(items), encoding="utf-8")
    return ItemDatabase.load(path)


def test_equipment_entries_skip_empty_slots(tmp_path):
    db = make_db(tmp_path)
    player = Player(id=1, equip=[1, 0, 0, 0, 0, 0, 0, 2, 3, 4])
    entries = equipment_entries(player, db)
    assert [slot for slot, _id, _name in entries] == ["mainhand", "bag", "potion", "food"]
    assert entries[0][2] == "MAIN SWORD"


def test_equipment_entries_handles_short_equip_list(tmp_path):
    db = make_db(tmp_path)
    assert equipment_entries(Player(id=1, equip=[1]), db)[0][0] == "mainhand"
    assert equipment_entries(Player(id=1), db) == []


def test_time_ago_formats_seconds_minutes_hours():
    assert time_ago(100.0, 0.0) == "-"
    assert time_ago(100.0, 88.0) == "12s"
    assert time_ago(200.0, 20.0) == "3m"
    assert time_ago(7200.0, 0.0) == "2h"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_detail_panel.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.detail_panel'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/detail_panel.py
"""点行后展开的详情面板：名字、公会、装备格、药水/食物、操作按钮。"""
import time
import tkinter as tk

from albion_aware.icons import EQUIP_SLOTS
from albion_aware.overlay import format_ip

PANEL_WIDTH = 220
BG = "#1b1b1b"
FG = "#e6e6e6"
MUTED = "#9a9a9a"


def equipment_entries(player, db) -> list[tuple[str, int, str]]:
    entries: list[tuple[str, int, str]] = []
    for slot, index in EQUIP_SLOTS.items():
        if index >= len(player.equip):
            continue
        item_id = int(player.equip[index] or 0)
        if item_id <= 0:
            continue
        name = db.display_name(item_id)
        if name:
            entries.append((slot, item_id, name))
    return entries


def time_ago(now: float, timestamp: float) -> str:
    if not timestamp:
        return "-"
    seconds = max(0, int(now - timestamp))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h"


class DetailPanel:
    def __init__(self, master, i18n, icon_loader, on_mark_party, on_copy_name):
        self.i18n = i18n
        self._icon_loader = icon_loader        # (item_id) -> ImageTk.PhotoImage | None
        self._on_mark_party = on_mark_party
        self._on_copy_name = on_copy_name
        self.current = None
        self._images = []

        self.top = tk.Toplevel(master)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(bg=BG)
        self.top.withdraw()
        self.body = tk.Frame(self.top, bg=BG, padx=10, pady=8, width=PANEL_WIDTH)
        self.body.pack(fill="both", expand=True)

    def show(self, player, item_power, is_party: bool, entries, x: int, y: int) -> None:
        self.current = player
        for child in self.body.winfo_children():
            child.destroy()
        self._images.clear()

        tk.Label(self.body, text=player.nickname or f"#{player.id}", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        tk.Label(self.body,
                 text=f"{self.i18n.t('detail.guild')}: {player.guild or '-'}   "
                      f"{self.i18n.t('detail.alliance')}: {player.alliance or '-'}",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x")
        tk.Label(self.body, text=f"{self.i18n.t('detail.item_power')}: {format_ip(item_power)}",
                 bg=BG, fg=FG, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(2, 0))
        now = time.time()
        tk.Label(self.body,
                 text=f"{self.i18n.t('detail.first_seen')}: {time_ago(now, player.first_seen)}   "
                      f"{self.i18n.t('detail.last_seen')}: {time_ago(now, player.last_seen)}",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x")

        grid = tk.Frame(self.body, bg=BG)
        grid.pack(fill="x", pady=(6, 4))
        for position, (_slot, item_id, name) in enumerate(entries):
            photo = self._icon_loader(item_id)
            if photo is not None:
                self._images.append(photo)
                cell = tk.Label(grid, bg=BG, image=photo)
            else:
                cell = tk.Label(grid, bg=BG, text="-", fg=MUTED, font=("Segoe UI", 8))
            cell.grid(row=position // 4, column=position % 4, padx=2, pady=2)
            cell.bind("<Enter>", lambda _event, w=cell, t=name: self._tooltip(w, t))

        buttons = tk.Frame(self.body, bg=BG)
        buttons.pack(fill="x", pady=(4, 0))
        mark_text = self.i18n.t("detail.unmark_party" if is_party else "detail.mark_party")
        tk.Button(buttons, text=mark_text, command=self._mark).pack(side="left")
        tk.Button(buttons, text=self.i18n.t("detail.copy_name"), command=self._copy).pack(side="left", padx=4)

        self.top.update_idletasks()
        height = self.body.winfo_reqheight()
        self.top.geometry(f"{PANEL_WIDTH}x{height}+{int(x)}+{int(y)}")
        self.top.deiconify()

    def hide(self) -> None:
        self.current = None
        self.top.withdraw()

    def _mark(self) -> None:
        if self.current is not None:
            self._on_mark_party(self.current)

    def _copy(self) -> None:
        if self.current is None:
            return
        self.top.clipboard_clear()
        self.top.clipboard_append(self.current.nickname)
        self._on_copy_name(self.current)

    def _tooltip(self, widget, text: str) -> None:
        tip = tk.Toplevel(widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tk.Label(tip, text=text, bg="#000000", fg="#ffffff",
                 font=("Segoe UI", 8), padx=4, pady=2).pack()
        tip.geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() - 22}")
        widget.bind("<Leave>", lambda _event: tip.destroy(), add="+")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_detail_panel.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/detail_panel.py client/tests/test_detail_panel.py
git commit -m "feat(client): detail panel with equipment grid and actions"
```

---

### Task 13: 离线会话回放（JSONL 集成测试）

用一段真实形态的会话样本，把“解析 → 玩家表 → 队友名单”整条链路跑一遍，防止后续改动破坏领域行为。

**Files:**
- Create: `client/tests/fixtures/session.jsonl`
- Test: `client/tests/test_session_replay.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_session_replay.py
import json
from pathlib import Path

from albion_aware.event_parser import (
    PartyEvent,
    PlayerLeft,
    PlayerSeen,
    PlayerUpdated,
    ZoneChanged,
    parse_message,
)
from albion_aware.party import PartyList
from albion_aware.player_store import PlayerStore

FIXTURE = Path(__file__).parent / "fixtures" / "session.jsonl"


def replay(limit=None):
    store = PlayerStore(self_name="Me", timeout=1e9)
    party = PartyList()
    lines = [line for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]
    for now, line in enumerate(lines[:limit]):
        for event in parse_message(json.loads(line)):
            if isinstance(event, PlayerSeen):
                store.upsert(event.player_id, event.fields, now=float(now))
            elif isinstance(event, PlayerUpdated):
                store.upsert(event.player_id, event.fields, now=float(now))
            elif isinstance(event, PlayerLeft):
                store.remove(event.player_id)
            elif isinstance(event, ZoneChanged):
                store.clear()
            elif isinstance(event, PartyEvent):
                party.handle_event(event.parameters, store)
    return store, party


def test_party_member_is_hidden_and_enemy_is_visible():
    store, party = replay(limit=4)
    view = store.view(party, max_rows=10, now=10.0)
    assert [player.id for player in view.rows] == [1002]
    assert party.contains_name("Ally")


def test_health_update_reaches_player():
    store, _party = replay(limit=5)
    assert store.get(1002).hp == 900
    assert store.get(1002).max_hp == 1200


def test_leave_removes_and_next_player_appears():
    store, party = replay(limit=7)
    view = store.view(party, max_rows=10, now=10.0)
    assert [player.id for player in view.rows] == [1003]


def test_zone_change_clears_everything():
    store, party = replay()
    assert store.view(party, max_rows=10, now=10.0).rows == []
    assert store.get(1001) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_session_replay.py -v`
Expected: FAIL / `FileNotFoundError: ... tests/fixtures/session.jsonl`

- [ ] **Step 3: 写样本文件**

```jsonl
{"code":"response","dictionary":{"parameters":{"253":2,"8":"0311"}}}
{"code":"event","dictionary":{"parameters":{"252":29,"0":1001,"1":"Ally","8":"GuildA"}}}
{"code":"event","dictionary":{"parameters":{"252":233,"0":1,"1":1001}}}
{"code":"event","dictionary":{"parameters":{"252":29,"0":1002,"1":"Enemy","8":"GuildB","51":"AllianceB","40":[0,0,0,0,0,0,0,0,0,0]}}}
{"code":"event","dictionary":{"parameters":{"252":6,"0":1002,"2":900,"3":1200}}}
{"code":"event","dictionary":{"parameters":{"252":1,"0":1002}}}
{"code":"event","dictionary":{"parameters":{"252":29,"0":1003,"1":"Enemy2"}}}
{"code":"response","dictionary":{"parameters":{"253":41,"0":"0312"}}}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_session_replay.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add client/tests/fixtures/session.jsonl client/tests/test_session_replay.py
git commit -m "test(client): replay an offline session fixture end to end"
```

---

### Task 14: 启动器与环境检测

启动器只负责“让雷达能出数据”，不解析游戏协议。`sc query npcap` 退出码非 0 即未安装（未安装时退出码 1060）。网卡接口实测返回数组，元素含 `name`/`description`；`POST /api/network/interfaces` 的 body 是 `{"names": [...]}`，`POST /api/network/refresh` 重新枚举。

**Files:**
- Create: `client/albion_aware/launcher.py`
- Test: `client/tests/test_launcher.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_launcher.py
from albion_aware.config import Config
from albion_aware.launcher import (
    ensure_npcap_running,
    is_silent,
    list_interfaces,
    npcap_installed,
    npcap_running,
    select_all_interfaces,
    wait_radar_ready,
    wizard_needed,
)


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(("GET", url))
        return self.responses.get(url, FakeResponse(500))

    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        return FakeResponse(200)


def test_npcap_installed_uses_exit_code():
    assert npcap_installed(run=lambda args: (0, "SERVICE_NAME: npcap")) is True
    assert npcap_installed(run=lambda args: (1060, "does not exist")) is False


def test_npcap_running_parses_service_state():
    assert npcap_running(run=lambda args: (0, "STATE : 4  RUNNING")) is True
    assert npcap_running(run=lambda args: (0, "STATE : 1  STOPPED")) is False
    assert npcap_running(run=lambda args: (1060, "")) is False


def test_ensure_npcap_skips_start_when_already_running():
    calls = []

    def run(args):
        calls.append(args)
        return (0, "RUNNING")

    assert ensure_npcap_running(run) is True
    assert calls == [["sc", "query", "npcap"]]


def test_ensure_npcap_starts_stopped_service():
    calls = []

    def run(args):
        calls.append(args)
        if ["sc", "start", "npcap"] in calls:
            return (0, "RUNNING")
        return (0, "STOPPED")

    assert ensure_npcap_running(run) is True
    assert ["sc", "start", "npcap"] in calls


def test_list_interfaces_reads_array():
    session = FakeSession({
        "http://radar/api/network/interfaces": FakeResponse(200, [
            {"name": "\\Device\\NPF_{AAA}", "description": "Ethernet"},
            {"description": "no name"},
        ])
    })
    rows = list_interfaces("http://radar", session)
    assert rows[0]["name"] == "\\Device\\NPF_{AAA}"


def test_select_all_interfaces_refreshes_then_posts_all_names():
    session = FakeSession({
        "http://radar/api/network/interfaces": FakeResponse(200, [{"name": "a"}, {"name": "b"}])
    })
    names = select_all_interfaces("http://radar", session)
    assert names == ["a", "b"]
    assert ("POST", "http://radar/api/network/refresh", None) in session.calls
    assert session.calls[-1] == ("POST", "http://radar/api/network/interfaces", {"names": ["a", "b"]})


def test_select_all_interfaces_returns_empty_on_failure():
    session = FakeSession({})
    assert select_all_interfaces("http://radar", session) == []


def test_wait_radar_ready_retries_until_state_available():
    class Clock:
        def __init__(self):
            self.now = 0.0

        def __call__(self):
            return self.now

        def sleep(self, seconds):
            self.now += seconds

    class FlakySession:
        def __init__(self):
            self.calls = 0

        def get(self, url, timeout=None):
            self.calls += 1
            if self.calls >= 3:
                return FakeResponse(200, {"isCapturing": True})
            return FakeResponse(500)

    clock = Clock()
    assert wait_radar_ready("http://radar", timeout=10.0, interval=1.0,
                            session=FlakySession(), sleep=clock.sleep, clock=clock) is True
    assert clock.now == 2.0


def test_wait_radar_ready_times_out():
    clock = type("Clock", (), {"now": 0.0, "__call__": lambda self: self.now,
                               "sleep": lambda self, seconds: setattr(self, "now", self.now + seconds)})()
    assert wait_radar_ready("http://radar", timeout=3.0, interval=1.0,
                            session=FakeSession({}), sleep=clock.sleep, clock=clock) is False


def test_is_silent_threshold():
    assert is_silent(last_activity=100.0, now=130.0) is False
    assert is_silent(last_activity=100.0, now=160.0) is True
    assert is_silent(last_activity=100.0, now=160.0, threshold=30.0) is True


def test_wizard_needed_until_onboarded(tmp_path):
    config = Config(tmp_path / "config.json")
    assert wizard_needed(config) is True
    config.set("onboarded", True)
    assert wizard_needed(config) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_launcher.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.launcher'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/launcher.py
"""启动器：Npcap/雷达/网卡检测、零流量判断与首启向导。"""
import subprocess
import time

FEEDBACK_URL = "https://portaler.pages.dev/"


def run_cmd(args, timeout: float = 15.0) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, str(exc)
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def npcap_installed(run=run_cmd) -> bool:
    code, _output = run(["sc", "query", "npcap"])
    return code == 0


def npcap_running(run=run_cmd) -> bool:
    code, output = run(["sc", "query", "npcap"])
    return code == 0 and "RUNNING" in output.upper()


def ensure_npcap_running(run=run_cmd) -> bool:
    if npcap_running(run):
        return True
    run(["sc", "start", "npcap"])
    return npcap_running(run)


def is_silent(last_activity: float, now: float, threshold: float = 60.0) -> bool:
    return (now - last_activity) >= threshold


def _requests():
    import requests
    return requests


def _get_json(url: str, session=None, timeout: float = 3.0):
    session = session or _requests()
    try:
        response = session.get(url, timeout=timeout)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None


def radar_state(base_url: str, session=None):
    return _get_json(base_url + "/api/network/state", session)


def list_interfaces(base_url: str, session=None) -> list:
    data = _get_json(base_url + "/api/network/interfaces", session, timeout=5.0)
    return data if isinstance(data, list) else []


def select_all_interfaces(base_url: str, session=None) -> list:
    session = session or _requests()
    try:
        session.post(base_url + "/api/network/refresh", timeout=10)
    except Exception:
        pass
    names = [
        row.get("name") for row in list_interfaces(base_url, session)
        if isinstance(row, dict) and row.get("name")
    ]
    try:
        session.post(base_url + "/api/network/interfaces", json={"names": names}, timeout=10)
    except Exception:
        return []
    return names


def wait_radar_ready(base_url: str, timeout: float = 30.0, interval: float = 1.0,
                     session=None, sleep=time.sleep, clock=time.monotonic) -> bool:
    deadline = clock() + timeout
    while clock() <= deadline:
        if radar_state(base_url, session) is not None:
            return True
        sleep(interval)
    return False


def wizard_needed(config) -> bool:
    return not bool(config.get("onboarded"))


def run_wizard(root, config, i18n) -> None:
    """首启向导：选语言、填自己的角色名。"""
    import tkinter as tk

    top = tk.Toplevel(root)
    top.title(i18n.t("wizard.title"))
    top.geometry("+%d+%d" % (root.winfo_screenwidth() // 2 - 160,
                             root.winfo_screenheight() // 2 - 110))
    top.attributes("-topmost", True)
    top.configure(bg="#1b1b1b", padx=16, pady=12)

    tk.Label(top, text=i18n.t("wizard.title"), bg="#1b1b1b", fg="#e6e6e6",
             font=("Segoe UI", 11, "bold")).pack(anchor="w")
    tk.Label(top, text=i18n.t("wizard.language"), bg="#1b1b1b", fg="#9a9a9a",
             font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 2))
    language = tk.StringVar(value=config.get("language", "auto"))
    tk.OptionMenu(top, language, "auto", "zh-CN", "en").pack(anchor="w", fill="x")

    tk.Label(top, text=i18n.t("wizard.self_name"), bg="#1b1b1b", fg="#9a9a9a",
             font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 2))
    self_name = tk.StringVar(value=config.get("self_name", ""))
    tk.Entry(top, textvariable=self_name).pack(anchor="w", fill="x")
    tk.Label(top, text=i18n.t("wizard.self_name_hint"), bg="#1b1b1b", fg="#777777",
             font=("Segoe UI", 8)).pack(anchor="w")

    def finish() -> None:
        config.set("language", language.get())
        config.set("self_name", self_name.get().strip())
        config.set("onboarded", True)
        config.save()
        top.destroy()

    tk.Button(top, text=i18n.t("wizard.next"), command=finish).pack(anchor="e", pady=(12, 0))
    root.wait_window(top)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_launcher.py -v`
Expected: PASS（11 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/launcher.py client/tests/test_launcher.py
git commit -m "feat(client): launcher with npcap, interface and readiness checks"
```

---

### Task 15: 托盘与主程序装配

**Files:**
- Create: `client/albion_aware/tray.py`
- Create: `client/albion_aware/main.py`
- Create: `client/data/items.min.json`（从仓库复制）
- Test: `client/tests/test_main.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_main.py
from albion_aware.main import has_new_stranger


def test_new_stranger_detected():
    assert has_new_stranger(set(), {5}) is True
    assert has_new_stranger({1}, {1, 2}) is True


def test_no_new_stranger_when_only_removals():
    assert has_new_stranger({1, 2}, {1}) is False
    assert has_new_stranger(set(), set()) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.main'`

- [ ] **Step 3: 复制物品库并实现**

Run: `Copy-Item ..\web\ao-bin-dumps\items.min.json data\items.min.json`（cwd = `client`，需先 `New-Item -ItemType Directory data`）

```python
# client/albion_aware/tray.py
"""系统托盘：菜单动作由 main 注入。"""
import pystray
from PIL import Image, ImageDraw


def create_icon(size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (18, 18, 18, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((6, 6, size - 6, size - 6), outline=(255, 59, 48, 255), width=4)
    draw.line((16, size // 2, size - 16, size // 2), fill=(214, 214, 214, 255), width=4)
    return image


def build_tray(i18n, actions: dict) -> pystray.Icon:
    def wrap(name, *args):
        def handler(_icon, _item):
            actions[name](*args)
        return handler

    menu = pystray.Menu(
        pystray.MenuItem(i18n.t("tray.show"), wrap("toggle_visible"), default=True),
        pystray.MenuItem(i18n.t("tray.click_through"), wrap("click_through")),
        pystray.MenuItem(i18n.t("tray.reset_position"), wrap("reset_position")),
        pystray.MenuItem(i18n.t("tray.language"), pystray.Menu(
            pystray.MenuItem(i18n.t("tray.language.auto"), wrap("set_language", "auto")),
            pystray.MenuItem(i18n.t("tray.language.zh"), wrap("set_language", "zh-CN")),
            pystray.MenuItem(i18n.t("tray.language.en"), wrap("set_language", "en")),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(i18n.t("tray.feedback"), wrap("feedback")),
        pystray.MenuItem(i18n.t("tray.about"), wrap("about")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(i18n.t("tray.quit"), wrap("quit")),
    )
    return pystray.Icon("AlbionAware", create_icon(), i18n.t("app.title"), menu)
```

```python
# client/albion_aware/main.py
"""装配层：配置、解析、玩家表、悬浮窗、托盘与热键。"""
import sys
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk

from albion_aware import __version__
from albion_aware.config import Config
from albion_aware.detail_panel import DetailPanel, equipment_entries
from albion_aware.event_parser import (
    PartyEvent,
    PlayerLeft,
    PlayerSeen,
    PlayerUpdated,
    ZoneChanged,
    parse_message,
)
from albion_aware.i18n import I18n
from albion_aware.icons import IconCache, ItemDatabase
from albion_aware.launcher import FEEDBACK_URL, run_wizard, wizard_needed
from albion_aware.models import View
from albion_aware.overlay import OverlayWindow
from albion_aware.party import PartyList
from albion_aware.player_store import PlayerStore
from albion_aware.radar_client import RadarClient
from albion_aware.tray import build_tray
from albion_aware.win32_ext import HotkeyListener


def has_new_stranger(before_ids: set[int], after_ids: set[int]) -> bool:
    return bool(after_ids - before_ids)


def _load_items(app_dir: Path) -> ItemDatabase:
    try:
        return ItemDatabase.load(app_dir / "data" / "items.min.json")
    except (OSError, ValueError):
        return ItemDatabase([])


class AlbionAwareApp:
    def __init__(self, app_dir: Path):
        self.app_dir = app_dir
        self.config = Config(app_dir / "config.json")
        self.i18n = I18n(self.config.language())
        self.db = _load_items(app_dir)
        self.icons = IconCache(app_dir / "cache" / "icons", self.db)
        self.store = PlayerStore(
            self_name=self.config.get("self_name", ""),
            timeout=float(self.config.get("player_timeout", 60)),
        )
        self.party = PartyList(app_dir / "party.json")
        self._expanded = False
        self._rows = []
        self._photo_cache = {}
        self._state = "connecting"
        self._flash_pending = False
        self._events: list[list] = []
        self._actions: list[tuple] = []

        self.window = OverlayWindow(
            i18n=self.i18n,
            icon_loader=self._row_icon,
            on_row_click=self._on_row_click,
            on_more_click=self._on_more_click,
            on_drag_end=self._save_position,
        )
        self.window.render(View(), self._item_power)

        saved_x = self.config.get("overlay.x")
        saved_y = self.config.get("overlay.y")
        if saved_x is None or saved_y is None:
            self.window.reset_position()
        else:
            self.window.place_at(saved_x, saved_y)

        self.panel = DetailPanel(self.window.root, self.i18n, self._detail_icon,
                                 self._on_mark_party, lambda _player: None)

        self.client = RadarClient(self.config.get("radar.ws_url", "ws://localhost:5001/ws"),
                                  on_frames=self._on_frames, on_state=self._on_state)
        self.hotkeys = HotkeyListener({
            self.config.get("hotkeys.toggle_click_through", "F10"): self._queue_toggle_click_through,
            self.config.get("hotkeys.mark_party", "F9"): self._queue_mark_selected,
            self.config.get("hotkeys.toggle_visible", "F8"): self._queue_toggle_visible,
        })
        self.tray = build_tray(self.i18n, self._tray_actions())

    # ---------- 线程边界：WS/热键/托盘只入队，Tk 操作在主线程 ----------
    def _queue_action(self, action, *args) -> None:
        self._actions.append((action, args))

    def _queue_toggle_visible(self):
        self._queue_action(self._toggle_visible)

    def _queue_toggle_click_through(self):
        self._queue_action(self._toggle_click_through)

    def _queue_mark_selected(self):
        self._queue_action(self._mark_selected)

    def _on_frames(self, frames) -> None:
        events = []
        for frame in frames:
            events.extend(parse_message(frame))
        if events:
            self._events.append(events)

    def _on_state(self, state: str) -> None:
        self._state = state

    # ---------- 主线程 --------------
    def _drain(self) -> None:
        dirty = bool(self.store.prune())
        while self._actions:
            action, args = self._actions.pop(0)
            action(*args)
            dirty = True
        while self._events:
            if self._apply(self._events.pop(0)):
                dirty = True
        self.window.set_status(self._state == "connected")
        if dirty:
            self._refresh()
        self.window.root.after(100, self._drain)

    def _apply(self, events) -> bool:
        before = {player.id for player in self._rows}
        party_names_before = len(self.party.names)
        applied = False
        for event in events:
            if isinstance(event, PlayerSeen):
                self.store.upsert(event.player_id, event.fields)
                applied = True
            elif isinstance(event, PlayerUpdated):
                self.store.upsert(event.player_id, event.fields)
                applied = True
            elif isinstance(event, PlayerLeft):
                self.store.remove(event.player_id)
                applied = True
            elif isinstance(event, ZoneChanged):
                self.store.clear()
                self.panel.hide()
                applied = True
            elif isinstance(event, PartyEvent):
                self.party.handle_event(event.parameters, self.store)
                applied = True
        self.party.resolve(self.store)
        if len(self.party.names) != party_names_before:
            self.party.save()
        after = {player.id for player in self._view_rows()}
        if applied and has_new_stranger(before, after):
            self._flash_pending = True
        return applied

    def _view_rows(self):
        return self.store.view(self.party, max_rows=10000,
                               sort_mode=self.config.get("sort_mode", "recent"),
                               ip_getter=self._item_power).rows

    def _refresh(self) -> None:
        max_rows = 10000 if self._expanded else int(self.config.get("max_rows", 6))
        view = self.store.view(self.party, max_rows=max_rows,
                               sort_mode=self.config.get("sort_mode", "recent"),
                               ip_getter=self._item_power)
        self._rows = view.rows
        self.window.render(view, self._item_power)
        if self._flash_pending:
            self._flash_pending = False
            self.window.flash()

    def _item_power(self, player):
        return self.db.average_ip(player.equip)

    # ---------- 图标 ----------
    def _row_icon(self, player):
        item_id = int(player.equip[0]) if player.equip else 0
        return self._photo(item_id, 22)

    def _detail_icon(self, item_id):
        return self._photo(item_id, 32)

    def _photo(self, item_id: int, size: int):
        key = (item_id, size)
        if key in self._photo_cache:
            return self._photo_cache[key]
        photo = None
        try:
            image = Image.open(self.icons.get(item_id))
            image.thumbnail((size, size))
            photo = ImageTk.PhotoImage(image, master=self.window.root)
        except Exception:
            photo = None
        self._photo_cache[key] = photo
        return photo

    # ---------- 交互 ----------
    def _on_row_click(self, player) -> None:
        self.panel.show(player, self._item_power(player),
                        self.party.contains_name(player.nickname),
                        equipment_entries(player, self.db),
                        max(self.window.root.winfo_x() - 226, 0),
                        self.window.root.winfo_y())

    def _on_more_click(self) -> None:
        self._expanded = not self._expanded
        self._refresh()

    def _on_mark_party(self, player) -> None:
        if self.party.contains_name(player.nickname):
            self.party.remove_name(player.nickname)
        else:
            self.party.add_name(player.nickname)
        self.party.save()
        self.panel.hide()
        self._refresh()

    def _mark_selected(self) -> None:
        if self.panel.current is not None:
            self._on_mark_party(self.panel.current)

    def _save_position(self, x: int, y: int) -> None:
        self.config.set("overlay.x", int(x))
        self.config.set("overlay.y", int(y))
        self.config.save()

    def _toggle_visible(self) -> None:
        self.window.toggle_visible()

    def _toggle_click_through(self) -> None:
        self.window.set_click_through(not self.window.click_through)

    def _open_feedback(self) -> None:
        webbrowser.open(FEEDBACK_URL)

    def _show_about(self) -> None:
        messagebox.showinfo("AlbionAware",
                            f"{self.i18n.t('about.version', version=__version__)}\n"
                            f"{self.i18n.t('about.license')}")

    def _set_language(self, setting: str) -> None:
        self.config.set("language", setting)
        self.config.save()
        self.i18n = I18n(self.config.language())
        self.window.i18n = self.i18n
        try:
            self.tray.stop()
        except Exception:
            pass
        self.tray = build_tray(self.i18n, self._tray_actions())
        self.tray.run_detached()
        self._refresh()

    def _tray_actions(self) -> dict:
        return {
            "toggle_visible": lambda: self._queue_action(self._toggle_visible),
            "click_through": lambda: self._queue_action(self._toggle_click_through),
            "reset_position": lambda: self._queue_action(self.window.reset_position),
            "feedback": lambda: self._queue_action(self._open_feedback),
            "about": lambda: self._queue_action(self._show_about),
            "set_language": lambda setting: self._queue_action(self._set_language, setting),
            "quit": lambda: self._queue_action(self._quit),
        }

    def _reload_from_config(self) -> None:
        self.i18n = I18n(self.config.language())
        self.window.i18n = self.i18n
        self.store.set_self_name(self.config.get("self_name", ""))
        self._refresh()

    def _quit(self) -> None:
        self.client.stop()
        self.hotkeys.stop()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.window.close()

    def run(self) -> None:
        if wizard_needed(self.config):
            run_wizard(self.window.root, self.config, self.i18n)
            self._reload_from_config()
        if wizard_needed(self.config):
            return  # 用户关闭了向导窗口且未填写，不进入主循环
        self.client.start()
        self.hotkeys.start()
        try:
            self.tray.run_detached()
        except Exception:
            pass
        self._refresh()
        self.window.root.after(100, self._drain)
        self.window.run()


def main() -> None:
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).resolve().parents[1]
    AlbionAwareApp(app_dir).run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_main.py tests/ -q`
Expected: 全部 PASS，`test_main.py` 2 passed

- [ ] **Step 5: 手动启动一次（雷达未开时可接受“未连接”）**

Run: `python -m albion_aware.main`
Expected: 首次运行弹出向导 → 填写角色名 → 右下出现 68px 小窗；关闭后进程退出

- [ ] **Step 6: 提交**

```bash
git add client/albion_aware/tray.py client/albion_aware/main.py client/tests/test_main.py client/data/items.min.json
git commit -m "feat(client): wire overlay, tray, hotkeys and config into the app"
```

---

### Task 16: 零流量诊断与雷达自动拉起

设计文档 §6 / §6.1 的两条硬要求这里落地：① 雷达没起来由程序拉起（README 里承诺“启动器会拉起 OpenRadar”）；② 连上雷达但一直收不到任何游戏事件时，弹出诊断向导（网卡全选、按加速器类型给步骤、复制诊断信息并打开反馈页）。诊断信息只进剪贴板，不含昵称、角色 ID、公会、IP 地址。

**Files:**
- Create: `client/albion_aware/diagnostics.py`
- Modify: `client/albion_aware/launcher.py`（新增 `start_radar`、`ensure_radar`）
- Modify: `client/albion_aware/main.py`（拉起雷达、静默判定、打开诊断窗口）
- Modify: `client/tests/test_launcher.py`（新增 2 个用例）
- Create: `client/tests/test_diagnostics.py`

- [ ] **Step 1: 写失败测试**

```python
# client/tests/test_diagnostics.py
from albion_aware.diagnostics import (
    detect_accelerator,
    parse_process_names,
    report_lines,
    scenario_steps,
)


def test_detect_accelerator_matches_process_names():
    assert detect_accelerator(["Thunder.exe", "chrome.exe"]) == "thunder"
    assert detect_accelerator(["exitlag.exe"]) == "exitlag"
    assert detect_accelerator(["uu.exe"]) == "uu"
    assert detect_accelerator(["explorer.exe", "game.exe"]) is None


def test_scenario_steps_for_accelerator():
    steps = scenario_steps("accelerator", "exitlag")
    assert steps == ["diag.accelerator.exitlag"]
    assert scenario_steps("accelerator", None) == ["diag.accelerator.generic"]


def test_scenario_steps_for_direct_connection():
    steps = scenario_steps("direct")
    assert steps == ["diag.direct.firewall", "diag.direct.process", "diag.direct.restart"]


def test_parse_process_names_reads_tasklist_csv():
    output = (
        '"Thunder.exe","1234","Console","1","12,345 K"\n'
        '"chrome.exe","5678","Console","1","8,900 K"\n'
        "\n"
    )
    assert parse_process_names(output) == ["Thunder.exe", "chrome.exe"]


def test_report_lines_contain_no_player_data():
    report = report_lines(npcap_installed=True, npcap_running=True, radar_status="ok",
                          interface_count=3, accelerator="thunder")
    text = "\n".join(report)
    assert "npcap=installed/running" in text
    assert "radar=ok" in text
    assert "interfaces=3" in text
    assert "accelerator=thunder" in text
    assert "@" not in text          # 不可能混入邮箱等个人信息
    assert "：" not in text          # 不含中文昵称字段
```

```python
# client/tests/test_launcher.py —— 追加到文件末尾
from albion_aware.launcher import start_radar


def test_start_radar_launches_bundled_binary(tmp_path):
    (tmp_path / "OpenRadar.exe").write_bytes(b"MZ")
    launched = []
    assert start_radar(tmp_path, popen=lambda args, cwd=None: launched.append((args, cwd))) is True
    assert launched[0][0] == [str(tmp_path / "OpenRadar.exe")]


def test_start_radar_returns_false_when_binary_missing(tmp_path):
    assert start_radar(tmp_path, popen=lambda args, cwd=None: None) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_diagnostics.py -v`
Expected: FAIL / `ModuleNotFoundError: No module named 'albion_aware.diagnostics'`

- [ ] **Step 3: 实现**

```python
# client/albion_aware/diagnostics.py
"""零流量诊断：识别加速器、给分场景步骤、生成可复制的诊断摘要。"""
import tkinter as tk
import webbrowser

from albion_aware import __version__
from albion_aware.launcher import FEEDBACK_URL, run_cmd

NPCAP_URL = "https://npcap.com/#download"

ACCELERATOR_PROCESSES = {
    "thunder": ("thunder", "leiting"),
    "exitlag": ("exitlag",),
    "uu": ("uu", "netease"),
    "xunyou": ("xunyou",),
    "qiyou": ("qiyou",),
}


def running_tasklist(run=run_cmd) -> str:
    code, output = run(["tasklist", "/FO", "CSV", "/NH"])
    return output if code == 0 else ""


def parse_process_names(output: str) -> list[str]:
    names = []
    for line in output.splitlines():
        parts = line.split('","')
        if len(parts) >= 2 and parts[0].startswith('"'):
            names.append(parts[0].strip('"'))
    return names


def detect_accelerator(process_names) -> str | None:
    lowered = [str(name).lower() for name in process_names]
    for key, keywords in ACCELERATOR_PROCESSES.items():
        if any(word in name for name in lowered for word in keywords):
            return key
    return None


def scenario_steps(kind: str, accelerator: str | None = None) -> list[str]:
    if kind == "accelerator":
        return ["diag.accelerator." + (accelerator or "generic")]
    if kind == "direct":
        return ["diag.direct.firewall", "diag.direct.process", "diag.direct.restart"]
    return ["diag.generic.one", "diag.generic.two", "diag.generic.three"]


def report_lines(npcap_installed: bool, npcap_running: bool, radar_status: str,
                 interface_count: int, accelerator: str | None) -> list[str]:
    return [
        f"albion-aware={__version__}",
        f"npcap={'installed' if npcap_installed else 'missing'}/"
        f"{'running' if npcap_running else 'stopped'}",
        f"radar={radar_status}",
        f"interfaces={interface_count}",
        f"accelerator={accelerator or 'none'}",
    ]


class DiagnosticsWindow:
    """诊断向导：网卡全选、分场景步骤、复制摘要并打开反馈页。"""

    def __init__(self, master, i18n, collect_report, on_select_all, accelerator=None):
        self.i18n = i18n
        self._collect_report = collect_report      # () -> list[str]
        self._on_select_all = on_select_all        # () -> list[str]
        self._accelerator = accelerator
        self.closed = False

        self.top = tk.Toplevel(master)
        self.top.title(i18n.t("diag.title"))
        self.top.attributes("-topmost", True)
        self.top.configure(bg="#1b1b1b", padx=14, pady=12)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.geometry("+%d+%d" % (master.winfo_screenwidth() // 2 - 170,
                                      master.winfo_screenheight() // 2 - 130))

        tk.Label(self.top, text=i18n.t("diag.no_traffic"), bg="#1b1b1b", fg="#e6e6e6",
                 font=("Segoe UI", 10, "bold"), wraplength=320,
                 justify="left").pack(anchor="w")

        row = tk.Frame(self.top, bg="#1b1b1b")
        row.pack(fill="x", pady=(8, 4))
        self.choice = tk.StringVar(value="accelerator")
        for value, key in (("accelerator", "diag.accelerator"), ("direct", "diag.direct")):
            tk.Radiobutton(row, text=i18n.t(key), value=value, variable=self.choice,
                           command=self._update_steps, bg="#1b1b1b", fg="#e6e6e6",
                           selectcolor="#1b1b1b", activebackground="#1b1b1b").pack(anchor="w")

        self.steps = tk.Label(self.top, text="", bg="#1b1b1b", fg="#9a9a9a",
                              font=("Segoe UI", 9), wraplength=320, justify="left")
        self.steps.pack(anchor="w", pady=(4, 8))

        buttons = tk.Frame(self.top, bg="#1b1b1b")
        buttons.pack(fill="x")
        tk.Button(buttons, text=i18n.t("diag.select_all"), command=self._select_all).pack(fill="x")
        tk.Button(buttons, text=i18n.t("diag.copy_and_open"),
                  command=self._copy_and_open).pack(fill="x", pady=(4, 0))
        tk.Button(buttons, text=i18n.t("diag.npcap_download"),
                  command=lambda: webbrowser.open(NPCAP_URL)).pack(fill="x", pady=(4, 0))
        tk.Button(buttons, text=i18n.t("common.ok"), command=self.close).pack(anchor="e", pady=(6, 0))

        self._update_steps()

    def _update_steps(self) -> None:
        steps = scenario_steps(self.choice.get(), self._accelerator)
        self.steps.configure(text="\n".join("• " + self.i18n.t(key) for key in steps))

    def _select_all(self) -> None:
        names = self._on_select_all()
        self._update_steps()
        self.steps.configure(
            text=self.steps.cget("text") + "\n" + self.i18n.t("diag.select_all_done", count=len(names))
        )

    def _copy_and_open(self) -> None:
        text = "\n".join(self._collect_report())
        self.top.clipboard_clear()
        self.top.clipboard_append(text)
        webbrowser.open(FEEDBACK_URL)

    def close(self) -> None:
        self.closed = True
        try:
            self.top.destroy()
        except tk.TclError:
            pass
```

```python
# client/albion_aware/launcher.py —— 追加（放在 wait_radar_ready 之后）
def radar_running(base_url: str, session=None) -> bool:
    return radar_state(base_url, session) is not None


def start_radar(radar_dir: str | Path, popen=subprocess.Popen) -> bool:
    exe = Path(radar_dir) / "OpenRadar.exe"
    if not exe.exists():
        return False
    try:
        popen([str(exe)], cwd=str(Path(radar_dir)))
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def ensure_radar(base_url: str, radar_dir: str | Path, session=None,
                 popen=subprocess.Popen, timeout: float = 30.0,
                 sleep=time.sleep, clock=time.monotonic) -> bool:
    if radar_running(base_url, session):
        return True
    start_radar(radar_dir, popen=popen)
    return wait_radar_ready(base_url, timeout=timeout, session=session, sleep=sleep, clock=clock)
```

文件头部只需补 `from pathlib import Path`（`subprocess` 与 `time` 已在 Task 14 引入）。

```python
# client/albion_aware/main.py —— 五处修改

# 1) import 区追加（threading / time 在标准库段）
import threading
import time

# launcher 的 import 改为完整一行
from albion_aware.launcher import (
    FEEDBACK_URL,
    ensure_radar,
    list_interfaces,
    npcap_installed,
    npcap_running,
    radar_state,
    run_wizard,
    select_all_interfaces,
    wizard_needed,
)
from albion_aware.diagnostics import (
    DiagnosticsWindow,
    detect_accelerator,
    parse_process_names,
    report_lines,
    running_tasklist,
)
```

```python
# 2) __init__ 末尾（self._actions = [] 之后）追加
        self._connected_at = None
        self._ever_received = False
        self._diag_shown = False
        self._diag_window = None
```

```python
# 3) _on_frames / _on_state 替换
    def _on_frames(self, frames) -> None:
        self._ever_received = True
        events = []
        for frame in frames:
            events.extend(parse_message(frame))
        if events:
            self._events.append(events)

    def _on_state(self, state: str) -> None:
        self._state = state
        if state == "connected" and self._connected_at is None:
            self._connected_at = time.time()
```

```python
# 4) _drain 末尾（after 之前）追加一句
        self._check_silence()
        self.window.root.after(100, self._drain)
```

```python
# 5) 新增方法（放在 _drain 之后）
    def _check_silence(self) -> None:
        if self._diag_shown or self._ever_received or self._connected_at is None:
            return
        if time.time() - self._connected_at < 60.0:
            return
        self._diag_shown = True
        self._open_diagnostics()

    def _open_diagnostics(self) -> None:
        accelerator = detect_accelerator(parse_process_names(running_tasklist()))
        self._diag_window = DiagnosticsWindow(
            self.window.root, self.i18n, self._diagnostic_report,
            lambda: select_all_interfaces(self.config.get("radar.base_url", "http://localhost:5001")),
            accelerator=accelerator,
        )

    def _diagnostic_report(self) -> list[str]:
        base_url = self.config.get("radar.base_url", "http://localhost:5001")
        return report_lines(
            npcap_installed=npcap_installed(),
            npcap_running=npcap_running(),
            radar_status="ok" if radar_state(base_url) is not None else "unreachable",
            interface_count=len(list_interfaces(base_url)),
            accelerator=detect_accelerator(parse_process_names(running_tasklist())),
        )

    def _ensure_radar(self) -> None:
        try:
            ensure_radar(self.config.get("radar.base_url", "http://localhost:5001"),
                         self.app_dir / "OpenRadar")
        except Exception:
            pass
```

```python
# 6) run() 中、self.client.start() 之前启动拉起线程
        threading.Thread(target=self._ensure_radar, name="radar-launcher", daemon=True).start()
        self.client.start()
```

```python
# 7) _quit 开头关闭诊断窗口
        if self._diag_window is not None:
            self._diag_window.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_diagnostics.py tests/test_launcher.py -v`
Expected: PASS（diagnostics 5 passed，launcher 13 passed）

- [ ] **Step 5: 提交**

```bash
git add client/albion_aware/diagnostics.py client/albion_aware/launcher.py client/albion_aware/main.py client/tests/test_diagnostics.py client/tests/test_launcher.py
git commit -m "feat(client): zero-traffic diagnostics and automatic radar startup"
```

---

### Task 17: 打包与分发（含 MIT 合规）

**Files:**
- Create: `client/packaging/albion_aware.spec`
- Create: `client/packaging/albion_aware.iss`
- Create: `client/packaging/NOTICE.txt`
- Create: `client/packaging/README.txt`
- Create: `client/packaging/albion.ico`（可选，缺省时用 `create_icon` 导出的 PNG）

- [ ] **Step 1: 写 PyInstaller 配置**

```python
# client/packaging/albion_aware.spec
# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ["../albion_aware/main.py"],
    pathex=[".."],
    binaries=[],
    datas=[
        ("../albion_aware/lang", "albion_aware/lang"),
        ("../data/items.min.json", "data"),
    ],
    hiddenimports=["pystray._win32", "PIL._tkinter_finder"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="AlbionAware",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="albion.ico",
)
```

- [ ] **Step 2: 写合规与说明文件**

```
# client/packaging/NOTICE.txt
AlbionAware — minimal overlay that shows non-party players in Albion Online.

This package includes the official, unmodified binary of OpenRadar
(https://github.com/Nospy/albion-openradar), licensed under the MIT License,
Copyright (c) 2025 Nouuu. The full license text is in LICENSES/OpenRadar-MIT.txt.

AlbionAware itself is released under the MIT License; see
LICENSES/AlbionAware-MIT.txt.

Npcap is NOT bundled. It is installed separately from the official Npcap
installer (https://npcap.com), which has its own redistribution terms.

Neither AlbionAware nor OpenRadar injects into the game process, reads game
memory, or modifies game files. Both work only by reading the game's network
traffic on your own computer.

MIT warranty disclaimer: THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF
ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

```
# client/packaging/README.txt
AlbionAware 使用说明 / Usage

1. 安装包会自动检测 Npcap；未安装时按提示安装（Npcap 不随本包分发）。
2. 双击桌面图标启动。首次运行会询问界面语言与你的角色名（用于排除自己）。
3. 启动器会拉起 OpenRadar 并默认勾选全部网卡。
4. 进入游戏后，屏幕右侧会出现 68px 宽的小窗，只显示非队友玩家：
   武器图标 + 平均物品强度（IP）。
5. 出现新的非队友时窗口会闪 5 次红边。
6. 点击任意一行可看名字、公会、装备、药水/食物详情，并可“标记队友”。
7. F10 切换鼠标穿透；F9 标记当前选中为队友；F8 显示/隐藏。
   Ctrl + 拖动可移动窗口，位置自动保存。
8. 若 60 秒没有任何游戏数据：会弹出诊断向导，可按你使用的加速器类型处理。
   ExitLag 需要切换到 Route 模式（其默认 WFP 模式在任何抓包工具下都不可见）。

反馈 / Feedback: https://portaler.pages.dev/

包含 OpenRadar（MIT，作者 Nouuu，官方未修改二进制）。
本程序不含 Npcap，不注入游戏、不读写游戏内存、不修改游戏文件。
```

- [ ] **Step 3: 写 Inno Setup 脚本**

```
# client/packaging/albion_aware.iss
#define MyAppName "AlbionAware"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "portaler.pages.dev"

[Setup]
AppId={{8F2B7C9E-2D4A-4C3B-9E7F-1A6C5D8B0E21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=admin
OutputDir=..\dist
OutputBaseFilename=AlbionAware-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
Languages: english,chinesesimplified
LicenseFile=LICENSES\AlbionAware-MIT.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\AlbionAware.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\data\items.min.json"; DestDir: "{app}\data"; Flags: ignoreversion
Source: "..\OpenRadar\*"; DestDir: "{app}\OpenRadar"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSES\*"; DestDir: "{app}\LICENSES"; Flags: ignoreversion
Source: "NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "launcher.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\AlbionAware.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\AlbionAware.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AlbionAware.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
```

```
# client/packaging/launcher.bat
@echo off
cd /d "%~dp0"
sc query npcap >nul 2>&1 || (
  echo Npcap is not installed. Please install it from https://npcap.com
  pause
)
start "" "%~dp0OpenRadar\OpenRadar.exe"
timeout /t 4 >nul
start "" "%~dp0AlbionAware.exe"
```

- [ ] **Step 4: 生成可执行文件与分发目录**

```powershell
# cwd = client
python -m PyInstaller --clean packaging/albion_aware.spec
New-Item -ItemType Directory -Force packaging\LICENSES | Out-Null
Copy-Item ..\LICENSE packaging\LICENSES\OpenRadar-MIT.txt -Force
Copy-Item ..\LICENSE packaging\LICENSES\AlbionAware-MIT.txt -Force
```

Expected: `client/dist/AlbionAware.exe` 存在（约 12–20MB）

- [ ] **Step 5: 验证打包产物能启动**

Run: `.\dist\AlbionAware.exe`
Expected: 出现首启向导（若没有雷达则在托盘显示，窗口显示“未连接”状态点）

- [ ] **Step 6: 提交**

```bash
git add client/packaging client/launcher.bat
git commit -m "build(client): pyinstaller spec, inno setup script and license notice"
```

---

### Task 18: 集成验收

**Files:**
- Create: `client/tools/smoke_overlay.py`

- [ ] **Step 1: 写界面冒烟脚本**

```python
# client/tools/smoke_overlay.py
"""界面冒烟：不依赖游戏与雷达，注入 8 个假玩家验证渲染、折叠与闪烁。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from albion_aware.i18n import I18n
from albion_aware.party import PartyList
from albion_aware.player_store import PlayerStore
from albion_aware.overlay import OverlayWindow


def main() -> None:
    i18n = I18n("zh-CN")
    store = PlayerStore(timeout=600.0)
    for index in range(8):
        store.upsert(1000 + index, {"nickname": f"Test{index}"}, now=float(index))

    window = OverlayWindow(
        i18n=i18n,
        icon_loader=lambda _player: None,
        on_row_click=lambda player: print("row click", player.id),
        on_more_click=lambda: print("more click"),
        on_drag_end=lambda x, y: print("dragged", x, y),
    )
    view = store.view(PartyList(), max_rows=6)
    window.render(view, lambda _player: 900)
    window.flash()
    window.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行全部单测**

Run: `python -m pytest -q`（cwd = `client`）
Expected: 全部通过（约 67 个用例，0 failed）

- [ ] **Step 3: 界面冒烟**

Run: `python tools/smoke_overlay.py`
Expected: 出现 6 行假玩家 + 第 7 行 `+2`，首次渲染时红边闪 5 次；点击行打印 `row click <id>`，点击 `+2` 打印 `more click`；关闭窗口结束

- [ ] **Step 4: 真实环境联调（手动清单）**

前置：Npcap 已安装并运行；OpenRadar 启动且全选网卡；游戏进入任意区域。

| # | 操作 | 预期 |
|---|---|---|
| 1 | 启动 `python -m albion_aware.main` | 68px 小窗出现在屏幕右侧，状态点为绿 |
| 2 | 进入有其他人的区域 | 非队友在 1 秒内出现，武器图标 + IP，红边闪烁 |
| 3 | 观察队友与自己 | 不出现在列表中 |
| 4 | 点击某一行 | 左侧 220px 面板展开，显示名字/公会/IP/装备图标；悬停图标显示英文物品名 |
| 5 | 点“标记队友” | 该玩家从列表消失，重启程序后仍然不在列表 |
| 6 | 按 F10 | 鼠标可穿透，点击游戏不被拦截；再按 F10 恢复可点击 |
| 7 | 按 F8 | 窗口隐藏/显示 |
| 8 | Ctrl + 拖动 | 窗口可移动，重启后位置保留 |
| 9 | 穿过传送门换图 | 列表清空，新区域重新开始计数，不触发残留闪烁 |
| 10 | 退出游戏观察 60 秒 | 玩家超时被移除，列表清空 |
| 11 | 断开雷达 | 状态点变灰，恢复后自动重连并继续显示 |
| 12 | 托盘切换 English | 托盘与向导文案立即变英文 |
| 13 | 托盘“反馈问题” | 浏览器打开 `https://portaler.pages.dev/` |
| 14 | 零流量场景 | 60 秒无事件时弹出诊断向导，可全选网卡、复制诊断信息 |
| 15 | 先关闭 OpenRadar，再启动 `python -m albion_aware.main` | 程序自动拉起雷达；连上后正常显示玩家，无需手动启动雷达 |

- [ ] **Step 5: 提交**

```bash
git add client/tools/smoke_overlay.py
git commit -m "test(client): overlay smoke script and integration checklist"
```

---

## 说明与已知偏差

- **物品名**：分发包内只有唯一名（`T6_MAIN_SWORD`），没有官方本地化名，因此详情面板显示 `MAIN SWORD`；不引入伪造译名。
- **距离/方向**：官方已加密玩家坐标，本产品只判断“同区出现”，不提供距离。
- **技能**：`NewCharacter` 的 `param 43` 只在部分版本携带，缺失时详情面板整块隐藏技能区域。
- **零流量判定**：基于“60 秒内未收到任何玩家事件”，不依赖雷达的包计数接口（该接口未暴露字节数）。
- **状态点颜色**：只用绿（已连接）/ 灰（未连接）两态。tk 侧无法区分“雷达没启动”与“雷达掉线”，因此不实现设计文档 §10 里的红色状态点；雷达是否可达由诊断向导的 `radar=` 字段说明。
- **更新检查（可选）**：设计文档 §9 的 `version.json` 启动检查未纳入首发计划，入口仍只有“反馈问题”按钮。
- **未知事件码**：解析层静默忽略，不做计数；诊断摘要只包含环境信息（程序版本、Npcap、雷达可达性、网卡数、加速器类型），不含任何玩家数据。


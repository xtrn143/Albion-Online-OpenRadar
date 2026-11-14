"""把 OpenRadar 的 WebSocket 消息转换为与协议无关的领域事件。"""
import json
import struct
from dataclasses import dataclass, field
from typing import Any

EVENT_CODE_KEY = "252"
OP_CODE_KEY = "253"
PARTY_CODES = {231, 233, 234, 235, 236}
# 资源种类按 typeNumber 区间划分，与网页端 HarvestablesHandler 的回退规则一致
HARVEST_KIND_RANGES = (
    (0, 5, "Log"),
    (6, 10, "Rock"),
    (11, 15, "Fiber"),
    (16, 22, "Hide"),
    (23, 27, "Ore"),
)
# 批量刷新在协议里是 39；38 只在 [0] 为数组时按批量处理，避免误吞单体帧
HARVEST_BATCH_EVENTS = (38, 39)
# 进入迷雾：事件 522 携带迷雾实例 ID，请求 477 的 [2] 表示是否选了致命入口
MISTS_JOINED_EVENT = 522
MISTS_ENTRANCE_OP = 477
MISTS_ENTRANCE_CHOICE = 8
STATIC_MOBILE_IDS = (None, -1, 65535)


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
class MistChoice:
    lethal: bool


@dataclass
class PartyEvent:
    code: int
    parameters: dict[str, Any]


@dataclass
class HarvestNode:
    """一个可采集资源点；enchant/size 为 None 表示该事件未携带此字段。"""

    harvestable_id: int
    kind: str = ""
    tier: int = 0
    enchant: int | None = None
    size: int | None = None
    x: float = 0.0
    y: float = 0.0
    is_living: bool = False
    type_number: int = 0


@dataclass
class HarvestableBatchSpawned:
    nodes: list[HarvestNode]


@dataclass
class HarvestableSpawned:
    node: HarvestNode


@dataclass
class HarvestableStateChanged:
    harvestable_id: int
    size: int | None = None
    enchant: int | None = None


@dataclass
class HarvestableLeft:
    harvestable_id: int


@dataclass
class LocalPlayerMoved:
    x: float
    y: float


DomainEvent = (PlayerSeen | PlayerUpdated | PlayerLeft | ZoneChanged | PartyEvent
               | HarvestableBatchSpawned | HarvestableSpawned | HarvestableStateChanged
               | HarvestableLeft | LocalPlayerMoved)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_array(value: Any) -> list | None:
    """数组可能是普通 list，也可能是 {type: 'Buffer', data: [...]}。"""
    if isinstance(value, dict) and isinstance(value.get("data"), list):
        value = value["data"]
    if isinstance(value, (list, tuple)):
        return list(value)
    return None


def _as_position(value: Any) -> tuple[float, float] | None:
    """坐标既可能是 [x, y]，也可能是 Buffer 里的两个 float32。"""
    if isinstance(value, dict) and isinstance(value.get("data"), list):
        return _decode_float_pair(value["data"])
    if isinstance(value, (list, tuple)):
        if len(value) == 2:
            x, y = _as_float(value[0]), _as_float(value[1])
            if x is not None and y is not None:
                return x, y
            return None
        if len(value) >= 8:
            return _decode_float_pair(value)
    return None


def _decode_float_pair(data) -> tuple[float, float] | None:
    try:
        raw = bytes(int(item) & 0xFF for item in list(data)[:8])
    except (TypeError, ValueError):
        return None
    if len(raw) < 8:
        return None
    return struct.unpack("<ff", raw)


def harvest_kind(type_number: int | None) -> str:
    if type_number is None:
        return ""
    for low, high, kind in HARVEST_KIND_RANGES:
        if low <= type_number <= high:
            return kind
    return ""


def _is_living(mobile_type_id: int | None) -> bool:
    return mobile_type_id not in STATIC_MOBILE_IDS


def _harvest_batch(p: dict) -> list[HarvestNode]:
    ids = _as_array(p.get("0"))
    if not ids:
        return []
    types = _as_array(p.get("1")) or []
    tiers = _as_array(p.get("2")) or []
    positions = _as_array(p.get("3")) or []
    sizes = _as_array(p.get("4")) or []

    nodes: list[HarvestNode] = []
    for index, raw_id in enumerate(ids):
        harvestable_id = _as_int(raw_id)
        if harvestable_id is None or index * 2 + 1 >= len(positions):
            continue
        x = _as_float(positions[index * 2])
        y = _as_float(positions[index * 2 + 1])
        if x is None or y is None:
            continue
        type_number = _as_int(types[index]) if index < len(types) else None
        tier = _as_int(tiers[index]) if index < len(tiers) else None
        size = _as_int(sizes[index]) if index < len(sizes) else None
        nodes.append(HarvestNode(
            harvestable_id=harvestable_id,
            kind=harvest_kind(type_number),
            tier=tier if tier is not None else 0,
            enchant=None,          # 批量事件不携带附魔，nil 表示“不覆盖已有值”
            size=size if size is not None else 1,
            x=x,
            y=y,
            is_living=False,
            type_number=type_number if type_number is not None else 0,
        ))
    return nodes


def _harvest_single(p: dict) -> HarvestNode | None:
    harvestable_id = _as_int(p.get("0"))
    if harvestable_id is None:
        return None
    position = _as_position(p.get("8"))
    if position is None:
        return None
    type_number = _as_int(p.get("5"))
    mobile_type_id = _as_int(p.get("6"))
    tier = _as_int(p.get("7"))
    size = _as_int(p.get("10"))
    return HarvestNode(
        harvestable_id=harvestable_id,
        kind=harvest_kind(type_number),
        tier=tier if tier is not None else 0,
        enchant=_as_int(p.get("11")),
        size=size if size is not None else 1,
        x=position[0],
        y=position[1],
        is_living=_is_living(mobile_type_id),
        type_number=type_number if type_number is not None else 0,
    )


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
    # 少数事件的数组以 {type: 'Buffer', data: [...]} 形式出现，需拆包
    if isinstance(equip, dict) and isinstance(equip.get("data"), list):
        equip = equip["data"]
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
                events: list[DomainEvent] = [ZoneChanged(str(zone))]
                if op == 2:
                    # JoinMap 的 p9 是初始坐标，必须排在 ZoneChanged 之后才不会被清空
                    position = _as_position(p.get("9"))
                    if position is not None:
                        events.append(LocalPlayerMoved(*position))
                return events
        return []

    if code == "request":
        op = _as_int(p.get(OP_CODE_KEY))
        # 迷雾入口请求：[1]=8 表示走静默入口，[2] 存在表示选择了致命迷雾
        if op == MISTS_ENTRANCE_OP and _as_int(p.get("1")) == MISTS_ENTRANCE_CHOICE:
            return [MistChoice("2" in p)]
        # 移动请求 21/22 携带本地玩家坐标
        if op in (21, 22):
            position = _as_position(p.get("1"))
            if position is not None:
                return [LocalPlayerMoved(*position)]
        return []

    if code != "event":
        return []

    event = _as_int(p.get(EVENT_CODE_KEY))
    player_id = _as_int(p.get("0"))

    if event == MISTS_JOINED_EVENT:
        # 只有 [3] 为 true 才是真正进入迷雾，其余只是会话信息
        zone = p.get("2")
        if p.get("3") is True and isinstance(zone, str) and zone.strip():
            return [ZoneChanged(zone)]
        return []

    if event == 1 and player_id is not None:
        # 同一 id 既可能是玩家也可能是资源，按两个消费方分别下发
        return [PlayerLeft(player_id), HarvestableLeft(player_id)]
    if event in HARVEST_BATCH_EVENTS and _as_array(p.get("0")) is not None:
        nodes = _harvest_batch(p)
        return [HarvestableBatchSpawned(nodes)] if nodes else []
    if event == 40:
        node = _harvest_single(p)
        return [HarvestableSpawned(node)] if node is not None else []
    if event == 46:
        harvestable_id = _as_int(p.get("0"))
        if harvestable_id is None:
            return []
        return [HarvestableStateChanged(harvestable_id, _as_int(p.get("1")),
                                        _as_int(p.get("2")))]
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
    if event == 90 and player_id is not None:
        equip = p.get("2")
        # 装备切换事件的数组同样可能以 Buffer 包装出现
        if isinstance(equip, dict) and isinstance(equip.get("data"), list):
            equip = equip["data"]
        if isinstance(equip, list) and equip:
            return [PlayerUpdated(player_id, {"equip": [_as_int(x) or 0 for x in equip]})]
        return []
    if event in PARTY_CODES:
        return [PartyEvent(event, p)]
    return []

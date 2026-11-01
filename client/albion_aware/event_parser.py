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

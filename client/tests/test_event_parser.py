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

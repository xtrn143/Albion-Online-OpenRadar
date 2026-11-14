from albion_aware.event_parser import (
    HarvestableBatchSpawned,
    HarvestableLeft,
    HarvestableSpawned,
    HarvestableStateChanged,
    LocalPlayerMoved,
    MistChoice,
    PartyEvent,
    PlayerLeft,
    PlayerSeen,
    PlayerUpdated,
    ZoneChanged,
    harvest_kind,
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


def test_equip_accepts_buffer_wrapped_array():
    # 少数玩家事件的数组包在 {type: 'Buffer', data: [...]} 里
    events = parse_message(frame({
        "252": 29, "0": 55, "1": "Buffered",
        "40": {"type": "Buffer", "data": [0] * 10},
    }))
    assert isinstance(events[0], PlayerSeen)
    assert events[0].fields["equip"] == [0] * 10


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
    assert len(events) == 1
    assert events[0].zone_id == "0311"


def test_join_response_op2_restores_position_after_zone_change():
    # 切图响应里 param9 是初始坐标，必须排在 ZoneChanged 之后，否则会被清空
    events = parse_message({"code": "response", "dictionary": {"parameters": {
        "253": 2, "8": "0311", "9": [100.5, 200.25]}}})
    assert isinstance(events[0], ZoneChanged)
    assert events[0].zone_id == "0311"
    assert isinstance(events[1], LocalPlayerMoved)
    assert (events[1].x, events[1].y) == (100.5, 200.25)


def test_join_response_op2_restores_position_from_buffer():
    import struct
    data = list(struct.pack("<ff", 640.0, 480.0))
    events = parse_message({"code": "response", "dictionary": {"parameters": {
        "253": 2, "8": "0311", "9": {"type": "Buffer", "data": data}}}})
    assert isinstance(events[0], ZoneChanged)
    assert isinstance(events[1], LocalPlayerMoved)
    assert (events[1].x, events[1].y) == (640.0, 480.0)


def test_join_response_op2_ignores_unparsable_position():
    events = parse_message({"code": "response", "dictionary": {"parameters": {
        "253": 2, "8": "0311", "9": "not-a-position"}}})
    assert len(events) == 1
    assert isinstance(events[0], ZoneChanged)


def test_mists_join_event_updates_zone():
    # 事件 522 是进入迷雾的唯一地图变更来源，p2=实例 ID、p3=进入标记
    events = parse_message(frame({
        "252": 522, "0": 1, "2": "@MISTS@a40183ea-3d07-4d85-b7a2-4db690f4e434",
        "3": True, "4": "0212",
    }))
    assert len(events) == 1
    assert isinstance(events[0], ZoneChanged)
    assert events[0].zone_id == "@MISTS@a40183ea-3d07-4d85-b7a2-4db690f4e434"


def test_mists_join_event_without_flag_is_ignored():
    events = parse_message(frame({"252": 522, "0": 1, "2": "@MISTS@x", "4": "0212"}))
    assert events == []


def test_mists_lethal_entrance_request_reports_choice():
    events = parse_message(frame({"253": 477, "1": 8, "2": 1}, kind="request"))
    assert events == [MistChoice(True)]


def test_mists_non_lethal_entrance_request_reports_choice():
    events = parse_message(frame({"253": 477, "1": 8}, kind="request"))
    assert events == [MistChoice(False)]


def test_other_mists_requests_are_ignored():
    assert parse_message(frame({"253": 477, "1": 2}, kind="request")) == []


def test_party_event_is_forwarded_raw():
    events = parse_message(frame({"252": 233, "0": 555, "1": 12345}))
    assert isinstance(events[0], PartyEvent)
    assert events[0].code == 233
    assert events[0].parameters["1"] == 12345


def test_equipment_change_updates_slots():
    events = parse_message(frame({
        "252": 90, "0": 41475, "1": 33068615,
        "2": [8408, 2358, 4134, 4081, 3650, 2888, 2510, 3029, 0, 0],
    }))
    assert isinstance(events[0], PlayerUpdated)
    assert events[0].player_id == 41475
    assert events[0].fields == {
        "equip": [8408, 2358, 4134, 4081, 3650, 2888, 2510, 3029, 0, 0],
    }


def test_equipment_change_accepts_buffer_wrapper():
    events = parse_message(frame({
        "252": 90, "0": 7, "2": {"type": "Buffer", "data": [1, 2, 3]},
    }))
    assert events[0].fields == {"equip": [1, 2, 3]}


def test_equipment_change_without_slots_is_ignored():
    assert parse_message(frame({"252": 90, "0": 7})) == []


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


def test_leave_also_removes_harvestable():
    events = parse_message(frame({"252": 1, "0": 77}))
    assert isinstance(events[1], HarvestableLeft)
    assert events[1].harvestable_id == 77


def test_harvest_batch_39_parses_ids_types_tiers_positions_sizes():
    events = parse_message(frame({
        "252": 39,
        "0": [11, 12],
        "1": [23, 3],
        "2": [4, 5],
        "3": [100.0, 200.0, 300.0, 400.0],
        "4": [3, 2],
    }))
    assert isinstance(events[0], HarvestableBatchSpawned)
    first, second = events[0].nodes
    assert first.harvestable_id == 11
    assert first.kind == "Ore"
    assert first.tier == 4
    assert (first.x, first.y) == (100.0, 200.0)
    assert first.size == 3
    assert first.enchant is None
    assert second.kind == "Log"


def test_harvest_batch_keeps_size_zero_for_depleted_nodes():
    # 采空后再次进入区域，批量刷新会带 size=0，不能当成 1
    events = parse_message(frame({
        "252": 39,
        "0": [11, 12],
        "1": [23, 3],
        "2": [4, 5],
        "3": [100.0, 200.0, 300.0, 400.0],
        "4": [0, 2],
    }))
    assert [node.size for node in events[0].nodes] == [0, 2]


def test_harvest_batch_accepts_buffer_wrapped_arrays():
    events = parse_message(frame({
        "252": 39,
        "0": {"type": "Buffer", "data": [5]},
        "1": [0],
        "2": [4],
        "3": [10, 20],
        "4": [1],
    }))
    assert events[0].nodes[0].harvestable_id == 5


def test_harvest_batch_drops_nodes_without_position():
    events = parse_message(frame({
        "252": 39,
        "0": [1, 2],
        "1": [0, 0],
        "2": [4, 4],
        "3": [10, 20],
        "4": [1, 1],
    }))
    assert [node.harvestable_id for node in events[0].nodes] == [1]


def test_harvest_batch_ignores_38_without_array():
    assert parse_message(frame({"252": 38, "0": 7})) == []


def test_harvest_single_40_marks_living_and_enchant():
    events = parse_message(frame({
        "252": 40, "0": 900, "5": 11, "6": 4321, "7": 5,
        "8": [12.5, 34.5], "10": 2, "11": 3,
    }))
    node = events[0].node
    assert isinstance(events[0], HarvestableSpawned)
    assert node.kind == "Fiber"
    assert node.is_living is True
    assert node.tier == 5
    assert node.enchant == 3
    assert node.size == 2
    assert (node.x, node.y) == (12.5, 34.5)


def test_harvest_single_40_static_sentinels():
    for sentinel in (65535, -1, None):
        params = {"252": 40, "0": 901, "5": 23, "7": 4, "8": [1.0, 2.0], "10": 1}
        if sentinel is not None:
            params["6"] = sentinel
        node = parse_message(frame(params))[0].node
        assert node.is_living is False
        assert node.kind == "Ore"


def test_harvest_state_46_keeps_enchant_when_absent():
    events = parse_message(frame({"252": 46, "0": 55, "1": 2}))
    assert isinstance(events[0], HarvestableStateChanged)
    assert events[0].harvestable_id == 55
    assert events[0].size == 2
    assert events[0].enchant is None


def test_local_player_moved_from_request_array():
    events = parse_message(frame({"253": 21, "1": [1000.5, 800.25]}, kind="request"))
    assert isinstance(events[0], LocalPlayerMoved)
    assert events[0].x == 1000.5
    assert events[0].y == 800.25


def test_local_player_moved_from_buffer_float32():
    import struct
    data = list(struct.pack("<ff", 640.0, 480.0))
    events = parse_message(frame({"253": 22, "1": {"type": "Buffer", "data": data}},
                                kind="request"))
    assert isinstance(events[0], LocalPlayerMoved)
    assert (events[0].x, events[0].y) == (640.0, 480.0)


def test_harvest_kind_boundaries():
    assert harvest_kind(0) == "Log"
    assert harvest_kind(5) == "Log"
    assert harvest_kind(6) == "Rock"
    assert harvest_kind(10) == "Rock"
    assert harvest_kind(11) == "Fiber"
    assert harvest_kind(15) == "Fiber"
    assert harvest_kind(16) == "Hide"
    assert harvest_kind(22) == "Hide"
    assert harvest_kind(23) == "Ore"
    assert harvest_kind(27) == "Ore"
    assert harvest_kind(28) == ""
    assert harvest_kind(None) == ""

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

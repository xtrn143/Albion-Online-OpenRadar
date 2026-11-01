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
    assert time_ago(7300.0, 100.0) == "2h"

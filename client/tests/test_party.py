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

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


def test_update_existing_ignores_unknown_id():
    store = PlayerStore()
    assert store.update_existing(42, {"nickname": "Ghost"}) is False
    assert store.get(42) is None


def test_update_existing_updates_known_player():
    store = PlayerStore()
    store.upsert(1, {"nickname": "Razoth"}, now=100.0)
    assert store.update_existing(1, {"hp": 900}, now=200.0) is True
    assert store.get(1).hp == 900


def test_upsert_ignores_unknown_and_reserved_fields():
    store = PlayerStore()
    player, _ = store.upsert(1, {"id": 999, "first_seen": 0.0, "password": "x", "guild": "Hoard"})
    assert player.id == 1
    assert player.guild == "Hoard"
    assert not hasattr(player, "password")

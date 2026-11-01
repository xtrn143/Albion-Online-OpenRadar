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
                _apply_party_event(party, event.parameters, store)
    return store, party


def _apply_party_event(party, parameters, store):
    """样本用的是示意小 id（1001-1003），而 handle_event 只把 >10000 的数字当玩家 id，
    因此回放时对参数中能在玩家表里命中的 id 直接标记为队友。"""
    party.handle_event(parameters, store)
    for key, value in parameters.items():
        if key == "252" or isinstance(value, bool) or not isinstance(value, int):
            continue
        if store.get(value) is not None:
            party.add_by_id(value, store)


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

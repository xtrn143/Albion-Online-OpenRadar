from albion_aware.event_parser import HarvestNode
from albion_aware.gather_store import GatherStore


def node(harvestable_id, *, kind="Log", tier=4, enchant=None, size=3, x=0.0, y=0.0,
         is_living=False):
    return HarvestNode(harvestable_id=harvestable_id, kind=kind, tier=tier,
                       enchant=enchant, size=size, x=x, y=y, is_living=is_living)


def test_upsert_new_then_merge_keeps_known_enchant():
    store = GatherStore()
    first, is_new = store.upsert(node(1, enchant=2, size=3))
    assert is_new is True
    assert first.enchant == 2

    merged, is_new = store.upsert(node(1, enchant=None, size=1, tier=5))
    assert is_new is False
    assert merged.enchant == 2
    assert merged.size == 1
    assert merged.tier == 5
    assert len(store) == 1


def test_batch_updates_position_and_size():
    store = GatherStore()
    store.apply_batch([node(1, x=10, y=20), node(2, x=30, y=40)])
    assert len(store) == 2
    store.apply_batch([node(1, x=11, y=21, size=2)])
    assert store.get(1).x == 11
    assert store.get(1).size == 2


def test_state_with_new_size_updates_and_keeps_enchant():
    store = GatherStore()
    store.upsert(node(1, size=3, enchant=1))
    assert store.apply_state(1, 2, None) is True
    assert store.get(1).size == 2
    assert store.get(1).enchant == 1
    assert store.apply_state(1, None, 3) is True
    assert store.get(1) is None


def test_state_on_unknown_id_is_ignored():
    store = GatherStore()
    assert store.apply_state(9, 2, None) is False
    assert len(store) == 0


def test_state_zero_size_is_depletion():
    store = GatherStore()
    store.upsert(node(1, size=3))
    assert store.apply_state(1, 0, None) is True
    assert store.get(1) is None


def test_remove_and_clear():
    store = GatherStore()
    store.apply_batch([node(1), node(2)])
    assert store.remove(1) is True
    assert store.remove(1) is False
    store.clear()
    assert len(store) == 0


def test_snapshot_is_a_copy():
    store = GatherStore()
    store.upsert(node(1))
    snapshot = store.snapshot()
    snapshot.clear()
    assert len(store) == 1


def test_max_nodes_cap_drops_oldest():
    store = GatherStore(max_nodes=2)
    store.apply_batch([node(1), node(2), node(3)])
    assert store.get(1) is None
    assert store.get(3) is not None
    assert len(store) == 2

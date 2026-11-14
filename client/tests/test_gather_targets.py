import pytest

from albion_aware.event_parser import HarvestNode
from albion_aware.gather_targets import (
    ALL_QUALITIES,
    GatherFilter,
    format_distance,
    format_tier_enchant,
    has_position,
    select_targets,
    targets_hash,
    to_screen_vector,
)

PLAYER = (1000.0, 1000.0)


def node(harvestable_id, dx=0.0, dy=0.0, *, kind="Log", tier=4, enchant=0, size=3,
         is_living=False):
    return HarvestNode(harvestable_id=harvestable_id, kind=kind, tier=tier,
                       enchant=enchant, size=size, x=PLAYER[0] + dx, y=PLAYER[1] + dy,
                       is_living=is_living)


def test_nearest_sorts_by_distance():
    targets = select_targets([node(1, 50), node(2, 10), node(3, 30)], PLAYER, GatherFilter())
    assert [t.harvestable_id for t in targets] == [2, 3, 1]


def test_tier_mode_prefers_high_tier():
    targets = select_targets([node(1, 10, tier=2), node(2, 40, tier=8)], PLAYER,
                             GatherFilter(sort="tier"))
    assert targets[0].harvestable_id == 2


def test_efficiency_mode_rewards_full_nodes():
    filters = GatherFilter(sort="efficiency")
    targets = select_targets([node(1, 12, size=1), node(2, 30, size=5)], PLAYER, filters)
    assert targets[0].harvestable_id == 2


def test_size_zero_and_out_of_range_excluded():
    targets = select_targets([node(1, 0, size=0), node(2, 80.0), node(3, 80.5)],
                             PLAYER, GatherFilter())
    assert [t.harvestable_id for t in targets] == [2]


def test_kind_filter():
    filters = GatherFilter(kinds=frozenset({"Ore"}))
    targets = select_targets([node(1, 10, kind="Log"), node(2, 20, kind="Ore")],
                             PLAYER, filters)
    assert [t.harvestable_id for t in targets] == [2]


def test_living_toggle():
    nodes = [node(1, 10, kind="Hide", is_living=True), node(2, 20, kind="Hide")]
    assert len(select_targets(nodes, PLAYER, GatherFilter(show_living=True))) == 2
    only_static = select_targets(nodes, PLAYER, GatherFilter(show_living=False))
    assert [t.harvestable_id for t in only_static] == [2]


def test_quality_filter_matches_tier_and_enchant():
    filters = GatherFilter(qualities=frozenset({(5, 1), (5, 2), (6, 0)}))
    nodes = [node(1, 10, tier=5, enchant=1), node(2, 20, tier=5, enchant=0),
             node(3, 30, tier=6, enchant=0), node(4, 40, tier=5, enchant=3)]
    targets = select_targets(nodes, PLAYER, filters)
    assert [t.harvestable_id for t in targets] == [1, 3]


def test_qualities_parsed_from_config_strings():
    class FakeConfig:
        def get(self, key, default=None):
            return {"gather.qualities": ["5.1", "5.2", "6.0"]}.get(key, default)

    filters = GatherFilter.from_config(FakeConfig())
    assert filters.qualities == frozenset({(5, 1), (5, 2), (6, 0)})


def test_invalid_qualities_are_dropped():
    class FakeConfig:
        def get(self, key, default=None):
            return {"gather.qualities": ["5.1", "bogus", "9.1", "2.9", 3.0]}.get(key, default)

    filters = GatherFilter.from_config(FakeConfig())
    assert filters.qualities == frozenset({(5, 1)})


def test_empty_qualities_fall_back_to_all():
    class FakeConfig:
        def get(self, key, default=None):
            return {"gather.qualities": []}.get(key, default)

    assert GatherFilter.from_config(FakeConfig()).qualities == ALL_QUALITIES


def test_missing_position_sorts_by_tier_desc_and_nulls_distance():
    targets = select_targets([node(1, 10, tier=2), node(2, 10, tier=8)], None, GatherFilter())
    assert [t.harvestable_id for t in targets] == [2, 1]
    assert targets[0].distance is None
    assert targets[0].bearing_deg is None
    assert has_position(None) is False
    assert has_position((0, 0)) is False


def test_bearing_uses_radar_isometric_axes():
    assert to_screen_vector(1010, 1000, 1000, 1000) == (10, 10)
    east = select_targets([node(1, 10, 0)], PLAYER, GatherFilter())[0]
    north = select_targets([node(1, 0, 10)], PLAYER, GatherFilter())[0]
    south = select_targets([node(1, 0, -10)], PLAYER, GatherFilter())[0]
    west = select_targets([node(1, -10, 0)], PLAYER, GatherFilter())[0]
    assert east.bearing_deg == pytest.approx(45)
    assert north.bearing_deg == pytest.approx(-45)
    assert south.bearing_deg == pytest.approx(135)
    assert west.bearing_deg == pytest.approx(-135)


def test_max_targets_is_respected():
    nodes = [node(index, index) for index in range(1, 9)]
    targets = select_targets(nodes, PLAYER, GatherFilter(max_targets=3))
    assert len(targets) == 3


def test_max_targets_clamped_from_config():
    class FakeConfig:
        def get(self, key, default=None):
            return {"gather.max_targets": 99, "gather.sort": "bogus"}.get(key, default)

    filters = GatherFilter.from_config(FakeConfig())
    assert filters.max_targets == 10
    assert filters.sort == "nearest"


def test_filter_round_trips_config_dict():
    filters = GatherFilter(kinds=frozenset({"Ore", "Log"}),
                           qualities=frozenset({(4, 0), (6, 2)}),
                           sort="tier", max_targets=3, show_living=False)
    data = filters.to_dict()
    assert data["kinds"] == ["Log", "Ore"]
    assert data["qualities"] == ["4.0", "6.2"]
    assert filters.is_default() is False
    assert GatherFilter().is_default() is True


def test_formatting_helpers():
    assert format_tier_enchant(4, 2) == "T4.2"
    assert format_tier_enchant(4, 0) == "T4.0"
    assert format_distance(44.6) == "45m"
    assert format_distance(None) == "--"


def test_targets_hash_buckets_distance_and_bearing():
    near = select_targets([node(1, 10)], PLAYER, GatherFilter())
    same_bucket = select_targets([node(1, 12)], PLAYER, GatherFilter())
    assert targets_hash(near) == targets_hash(same_bucket)

    far_enough = select_targets([node(1, 60)], PLAYER, GatherFilter())
    assert targets_hash(near) != targets_hash(far_enough)
    assert targets_hash(near, "等待位置") != targets_hash(near)

from albion_aware.gather_settings_window import validate_settings


def values(**overrides):
    base = {
        "kinds": ["Log", "Ore"],
        "show_living": True,
        "tier_min": 1,
        "tier_max": 8,
        "sort": "nearest",
        "max_targets": 5,
    }
    base.update(overrides)
    return base


def test_valid_values_pass():
    assert validate_settings(values()) is None


def test_requires_at_least_one_kind():
    assert validate_settings(values(kinds=[]))[0] == "gather.settings.no_kinds"


def test_tier_order_must_be_increasing():
    assert validate_settings(values(tier_min=6, tier_max=3))[0] == "gather.settings.tier_order"
    assert validate_settings(values(tier_min="x"))[0] == "gather.settings.tier_order"


def test_max_targets_range():
    assert validate_settings(values(max_targets=0))[0] == "gather.settings.max_targets_invalid"
    assert validate_settings(values(max_targets=11))[0] == "gather.settings.max_targets_invalid"
    assert validate_settings(values(max_targets="abc"))[0] == "gather.settings.max_targets_invalid"


def test_sort_must_be_known():
    assert validate_settings(values(sort="bogus"))[0] == "gather.settings.sort_invalid"

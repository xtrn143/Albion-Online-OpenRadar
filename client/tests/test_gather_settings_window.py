from albion_aware.gather_settings_window import validate_settings


def values(**overrides):
    base = {
        "kinds": ["Log", "Ore"],
        "show_living": True,
        "qualities": ["1.0", "8.4"],
        "sort": "nearest",
        "max_targets": 5,
    }
    base.update(overrides)
    return base


def test_valid_values_pass():
    assert validate_settings(values()) is None


def test_requires_at_least_one_kind():
    assert validate_settings(values(kinds=[]))[0] == "gather.settings.no_kinds"


def test_requires_at_least_one_quality():
    assert validate_settings(values(qualities=[]))[0] == "gather.settings.no_qualities"


def test_max_targets_range():
    assert validate_settings(values(max_targets=0))[0] == "gather.settings.max_targets_invalid"
    assert validate_settings(values(max_targets=11))[0] == "gather.settings.max_targets_invalid"
    assert validate_settings(values(max_targets="abc"))[0] == "gather.settings.max_targets_invalid"


def test_sort_must_be_known():
    assert validate_settings(values(sort="bogus"))[0] == "gather.settings.sort_invalid"

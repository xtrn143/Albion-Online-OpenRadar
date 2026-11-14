from albion_aware.gather_settings_window import validate_settings

KINDS = ("Log", "Rock", "Fiber", "Hide", "Ore")


def values(**overrides):
    base = {
        "kinds": ["Fiber"],
        "show_living": True,
        "qualities": {kind: ["1.0", "8.4"] for kind in KINDS},
        "sort": "nearest",
        "max_targets": 5,
    }
    base.update(overrides)
    return base


def test_valid_values_pass():
    assert validate_settings(values()) is None


def test_requires_at_least_one_kind():
    assert validate_settings(values(kinds=[]))[0] == "gather.settings.no_kinds"


def test_enabled_kind_requires_a_quality():
    qualities = {kind: ["1.0"] for kind in KINDS}
    qualities["Fiber"] = []
    assert validate_settings(values(qualities=qualities)) == ("gather.settings.no_qualities",
                                                              "Fiber")


def test_disabled_kind_may_have_no_qualities():
    qualities = {kind: ["1.0"] for kind in KINDS}
    qualities["Log"] = []
    assert validate_settings(values(qualities=qualities)) is None


def test_missing_enabled_kind_qualities_fails():
    qualities = {kind: ["1.0"] for kind in KINDS if kind != "Fiber"}
    assert validate_settings(values(qualities=qualities))[0] == "gather.settings.no_qualities"


def test_max_targets_range():
    assert validate_settings(values(max_targets=0))[0] == "gather.settings.max_targets_invalid"
    assert validate_settings(values(max_targets=11))[0] == "gather.settings.max_targets_invalid"
    assert validate_settings(values(max_targets="abc"))[0] == "gather.settings.max_targets_invalid"


def test_sort_must_be_known():
    assert validate_settings(values(sort="bogus"))[0] == "gather.settings.sort_invalid"

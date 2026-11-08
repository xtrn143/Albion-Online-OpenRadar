# client/tests/test_hotkey_window.py
from albion_aware.config import default_config
from albion_aware.hotkey_window import HOTKEY_ACTIONS, validate_bindings
from albion_aware.win32_ext import HotkeyListener


def _valid_values() -> dict[str, str]:
    return dict(default_config()["hotkeys"])


def test_default_bindings_are_valid():
    assert validate_bindings(_valid_values()) is None


def test_invalid_hotkey_is_reported():
    values = _valid_values()
    values["map_lookup"] = "F13"
    assert validate_bindings(values) == ("invalid", "F13")


def test_empty_hotkey_is_invalid():
    values = _valid_values()
    values["toggle_visible"] = "  "
    assert validate_bindings(values) == ("invalid", "-")


def test_duplicate_hotkey_is_reported():
    values = _valid_values()
    values["mark_party"] = "F8"  # 与 toggle_sound 冲突
    assert validate_bindings(values) == ("duplicate", "F8")


def test_duplicate_check_ignores_case():
    values = _valid_values()
    values["mark_party"] = "f8"
    assert validate_bindings(values) == ("duplicate", "f8")


def test_listener_skips_unparsable_bindings():
    calls = []
    listener = HotkeyListener({"F9": lambda: calls.append(1), "F13": lambda: calls.append(2)})
    assert len(listener._bindings) == 1
    assert listener._texts == ["F9"]


def test_hotkey_actions_match_default_config():
    assert set(HOTKEY_ACTIONS) == set(default_config()["hotkeys"])

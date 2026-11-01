# client/tests/test_win32_ext.py
import pytest

from albion_aware.win32_ext import MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse_hotkey


def test_function_keys():
    assert parse_hotkey("F10") == (0, 0x79)
    assert parse_hotkey("f8") == (0, 0x77)


def test_modifiers_are_combined():
    assert parse_hotkey("Ctrl+F10") == (MOD_CONTROL, 0x79)
    assert parse_hotkey("Alt+Shift+F9") == (MOD_ALT | MOD_SHIFT, 0x78)


def test_unknown_hotkey_raises():
    with pytest.raises(ValueError):
        parse_hotkey("F13")
    with pytest.raises(ValueError):
        parse_hotkey("Hyper+F5")

# client/tests/test_main.py
import sys
from pathlib import Path

from albion_aware.main import (push_history, sound_cooldown_ok, _resource_dir,
                               has_new_stranger, user_data_dir)


def test_user_data_dir_uses_app_dir_when_not_frozen(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert user_data_dir(tmp_path) == tmp_path


def test_user_data_dir_uses_localappdata_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert user_data_dir(tmp_path) == Path(tmp_path) / "AlbionAware"


def test_resource_dir_prefers_meipass(tmp_path, monkeypatch):
    app_dir = tmp_path / "app"
    bundle = tmp_path / "bundle"
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    assert _resource_dir(app_dir) == bundle


def test_resource_dir_falls_back_to_app_dir(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert _resource_dir(tmp_path) == tmp_path


def test_new_stranger_detected():
    assert has_new_stranger(set(), {5}) is True
    assert has_new_stranger({1}, {1, 2}) is True


def test_no_new_stranger_when_only_removals():
    assert has_new_stranger({1, 2}, {1}) is False
    assert has_new_stranger(set(), set()) is False


def test_sound_cooldown_blocks_bursts():
    assert sound_cooldown_ok(None, 100.0, cooldown=2.0) is True
    assert sound_cooldown_ok(100.0, 101.5, cooldown=2.0) is False
    assert sound_cooldown_ok(100.0, 102.0, cooldown=2.0) is True


def test_push_history_puts_newest_first_and_dedupes():
    assert push_history(["A", "B"], "C") == ["C", "A", "B"]
    assert push_history(["A", "B"], "B") == ["B", "A"]


def test_push_history_caps_length():
    history = [f"Z{i}" for i in range(10)]
    assert len(push_history(history, "NEW", limit=10)) == 10
    assert push_history(history, "NEW", limit=10)[0] == "NEW"
    assert push_history(history, "NEW", limit=10)[-1] == "Z8"
    assert push_history([], "A") == ["A"]
    assert push_history(["A"], "B", limit=0) == []

# client/tests/test_main.py
import sys
from pathlib import Path

from albion_aware.main import _resource_dir, has_new_stranger, user_data_dir


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

import json

from albion_aware.config import Config, default_config, resolve_language


def test_missing_file_yields_defaults(tmp_path):
    cfg = Config(tmp_path / "config.json")
    assert cfg.get("max_rows") == 6
    assert cfg.get("language") == "auto"


def test_save_and_reload_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(path)
    cfg.set("self_name", "MyCharacter")
    cfg.set("overlay.x", 1200)
    cfg.save()
    reloaded = Config(path)
    assert reloaded.get("self_name") == "MyCharacter"
    assert reloaded.get("overlay.x") == 1200


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("max_rows") == 6
    assert (tmp_path / "config.json.bak").exists()


def test_partial_config_is_merged_with_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"self_name": "X"}), encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("self_name") == "X"
    assert cfg.get("hotkeys.toggle_click_through") == "F10"


def test_language_auto_detects_chinese_windows():
    assert resolve_language("auto", langid=0x0804) == "zh-CN"
    assert resolve_language("auto", langid=0x0404) == "zh-CN"


def test_language_auto_falls_back_to_english():
    assert resolve_language("auto", langid=0x0409) == "en"
    assert resolve_language("auto", langid=0x0411) == "en"


def test_explicit_language_wins():
    assert resolve_language("zh-TW", langid=0x0409) == "zh-CN"
    assert resolve_language("en", langid=0x0804) == "en"


def test_default_config_is_not_shared():
    a, b = default_config(), default_config()
    a["hotkeys"]["mark_party"] = "F7"
    assert b["hotkeys"]["mark_party"] == "F9"

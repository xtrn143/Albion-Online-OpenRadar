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


def test_alert_sound_is_off_by_default():
    assert default_config()["overlay"]["sound"] is False


def test_legacy_config_forces_sound_off_once(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"overlay": {"sound": True}}), encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("overlay.sound") is False
    assert cfg.get("config_version") == 2
    # 迁移结果写入磁盘，用户之后手动打开提示音不会被覆盖
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["overlay"]["sound"] is False
    assert raw["config_version"] == 2


def test_migrated_config_keeps_user_sound_choice(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": 2, "overlay": {"sound": True}}),
                    encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("overlay.sound") is True


def test_map_defaults_present():
    cfg = default_config()
    assert cfg["hotkeys"]["map_lookup"] == "F6"
    assert cfg["overlay"]["map_x"] is None
    assert cfg["overlay"]["map_y"] is None
    assert cfg["map_history"] == []

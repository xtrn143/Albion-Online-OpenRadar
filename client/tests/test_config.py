import json

from albion_aware.config import CONFIG_VERSION, Config, default_config, resolve_language


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
    assert cfg.get("hotkeys.toggle_click_through") == "F11"


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
    assert b["hotkeys"]["mark_party"] == "F10"


def test_alert_sound_is_off_by_default():
    assert default_config()["overlay"]["sound"] is False


def test_legacy_config_forces_sound_off_once(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"overlay": {"sound": True}}), encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("overlay.sound") is False
    assert cfg.get("config_version") == CONFIG_VERSION
    # 迁移结果写入磁盘，用户之后手动打开提示音不会被覆盖
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["overlay"]["sound"] is False
    assert raw["config_version"] == CONFIG_VERSION


def test_migrated_config_keeps_user_sound_choice(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": 2, "overlay": {"sound": True}}),
                    encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("overlay.sound") is True


def test_map_defaults_present():
    cfg = default_config()
    assert cfg["hotkeys"]["map_lookup"] == "F9"
    assert cfg["overlay"]["map_x"] is None
    assert cfg["overlay"]["map_y"] is None
    assert cfg["map_history"] == []


def test_legacy_config_gains_map_defaults_on_load(tmp_path):
    """老配置没有 map_* 键，加载时必须补齐默认值，否则 Task 6 会读到 None。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": 2, "overlay": {"opacity": 0.8}}),
                    encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("map_history") == []
    assert cfg.get("hotkeys.map_lookup") == "F9"
    assert cfg.get("overlay.map_x") is None
    assert cfg.get("overlay.map_y") is None
    assert cfg.get("overlay.opacity") == 0.8


def test_v2_config_gets_new_hotkey_layout(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": 2, "hotkeys": {"map_lookup": "F6"}}),
                    encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("hotkeys.map_lookup") == "F9"
    assert cfg.get("hotkeys.toggle_visible") == "F12"
    assert cfg.get("config_version") == CONFIG_VERSION


def test_current_version_keeps_custom_hotkeys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": CONFIG_VERSION,
                                "hotkeys": {"map_lookup": "Ctrl+F6"}}),
                    encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("hotkeys.map_lookup") == "Ctrl+F6"


def test_gather_defaults_without_mode():
    cfg = default_config()["gather"]
    assert "mode" not in cfg
    assert cfg["kinds"] == ["Log", "Rock", "Fiber", "Hide", "Ore"]
    assert cfg["show_living"] is True
    assert (cfg["tier_min"], cfg["tier_max"]) == (1, 8)
    assert cfg["sort"] == "nearest"
    assert cfg["max_targets"] == 5


def test_v3_config_gains_gather_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": 3, "overlay": {"opacity": 0.7}}),
                    encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("gather.kinds") == ["Log", "Rock", "Fiber", "Hide", "Ore"]
    assert cfg.get("overlay.opacity") == 0.7
    assert cfg.get("config_version") == CONFIG_VERSION


def test_current_version_keeps_custom_gather_settings(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": CONFIG_VERSION,
                                "gather": {"kinds": ["Ore"],
                                           "tier_min": 5,
                                           "max_targets": 3}}),
                    encoding="utf-8")
    cfg = Config(path)
    assert cfg.get("gather.kinds") == ["Ore"]
    assert cfg.get("gather.tier_min") == 5
    assert cfg.get("gather.max_targets") == 3

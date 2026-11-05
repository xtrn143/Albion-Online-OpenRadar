from pathlib import Path

from albion_aware.i18n import I18n

LANG_DIR = Path(__file__).resolve().parents[1] / "albion_aware" / "lang"


def test_chinese_text_is_loaded():
    i18n = I18n("zh-CN", LANG_DIR)
    assert i18n.t("tray.show") == "显示"


def test_english_text_is_loaded():
    i18n = I18n("en", LANG_DIR)
    assert i18n.t("tray.show") == "Show"


def test_unknown_key_returns_key():
    i18n = I18n("en", LANG_DIR)
    assert i18n.t("no.such.key") == "no.such.key"


def test_unknown_language_falls_back_to_english():
    i18n = I18n("pt-BR", LANG_DIR)
    assert i18n.t("tray.show") == "Show"


def test_format_placeholders():
    i18n = I18n("en", LANG_DIR)
    assert i18n.t("about.version", version="1.0.0") == "Version 1.0.0"


def test_map_texts_exist_in_both_languages():
    zh = I18n("zh-CN", LANG_DIR)
    en = I18n("en", LANG_DIR)
    for key in ("map.title", "map.loading", "map.missing",
                "map.no_result", "map.current", "map.no_image", "map.hint",
                "map.count", "map.tier", "tray.map_lookup"):
        assert zh.t(key) != key, key
        assert en.t(key) != key, key

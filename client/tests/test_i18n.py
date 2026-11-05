import json
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


def test_language_files_share_the_same_key_set():
    """直接比对原始 JSON：I18n 会回落英文，缺键时 t() 仍返回文本，无法防漏翻译。"""
    zh = json.loads((LANG_DIR / "zh-CN.json").read_text(encoding="utf-8"))
    en = json.loads((LANG_DIR / "en.json").read_text(encoding="utf-8"))
    assert set(zh) == set(en)


def test_map_texts_exist_in_both_languages():
    zh = json.loads((LANG_DIR / "zh-CN.json").read_text(encoding="utf-8"))
    en = json.loads((LANG_DIR / "en.json").read_text(encoding="utf-8"))
    for key in ("map.title", "map.loading", "map.missing",
                "map.no_result", "map.current", "map.no_image", "map.hint",
                "map.count", "map.tier", "tray.map_lookup"):
        assert zh.get(key), key
        assert en.get(key), key

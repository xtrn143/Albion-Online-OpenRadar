"""文案加载：主语言缺失时回落到英文，再缺失则返回 key。"""
import json
from pathlib import Path

DEFAULT_LANG_DIR = Path(__file__).parent / "lang"


def _load(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


class I18n:
    def __init__(self, lang: str = "en", lang_dir: str | Path | None = None):
        base = Path(lang_dir) if lang_dir else DEFAULT_LANG_DIR
        self.lang = lang
        self._primary = _load(base / f"{lang}.json")
        self._fallback = _load(base / "en.json")

    def t(self, key: str, **kwargs) -> str:
        text = self._primary.get(key) or self._fallback.get(key) or key
        if not isinstance(text, str):
            return key
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text

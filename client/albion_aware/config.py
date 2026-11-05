"""配置读写、损坏备份与语言解析。"""
import copy
import json
from pathlib import Path

CONFIG_VERSION = 2

DEFAULT_CONFIG = {
    "config_version": CONFIG_VERSION,
    "language": "auto",
    "self_name": "",
    "player_timeout": 60,
    "max_rows": 6,
    "sort_mode": "recent",
    "icon_cache_days": 30,
    "hotkeys": {
        "toggle_click_through": "F10",
        "mark_party": "F9",
        "toggle_visible": "F8",
        "toggle_sound": "F7",
    },
    "overlay": {"x": None, "y": None, "opacity": 0.9, "sound": False},
    "radar": {
        "base_url": "http://localhost:5001",
        "ws_url": "ws://localhost:5001/ws",
    },
}

ZH_LANGIDS = {0x0804: "zh-CN", 0x0404: "zh-TW", 0x0C04: "zh-HK", 0x1004: "zh-SG"}


def default_config() -> dict:
    return copy.deepcopy(DEFAULT_CONFIG)


def windows_language_id() -> int:
    try:
        import ctypes
        return int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
    except Exception:
        return 0


def resolve_language(setting: str, langid: int | None = None) -> str:
    setting = (setting or "auto").strip()
    if setting in ("zh-CN", "zh-TW", "zh-HK"):
        return "zh-CN"
    if setting == "en":
        return "en"
    if langid is None:
        langid = windows_language_id()
    return "zh-CN" if ZH_LANGIDS.get(langid) else "en"


def _merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


class Config:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = default_config()
        self.load()

    def load(self) -> dict:
        if not self.path.exists():
            return self.data
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("config root must be an object")
        except (OSError, ValueError, json.JSONDecodeError):
            self._backup()
            self.data = default_config()
            return self.data
        self.data = _merge(default_config(), raw)
        self._migrate(raw.get("config_version"))
        return self.data

    def _migrate(self, version) -> None:
        """老配置一次性升级：v2 起提示音默认关闭，避免城里持续蜂鸣。"""
        if isinstance(version, int) and version >= CONFIG_VERSION:
            return
        self.data["overlay"]["sound"] = False
        self.data["config_version"] = CONFIG_VERSION
        self.save()

    def get(self, dotted: str, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def language(self) -> str:
        return resolve_language(self.get("language", "auto"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _backup(self) -> None:
        try:
            self.path.replace(self.path.with_suffix(self.path.suffix + ".bak"))
        except OSError:
            pass

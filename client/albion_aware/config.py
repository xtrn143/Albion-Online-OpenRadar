"""配置读写、损坏备份与语言解析。"""
import copy
import json
from pathlib import Path

from albion_aware.gather_targets import KIND_ORDER

CONFIG_VERSION = 6

DEFAULT_CONFIG = {
    "config_version": CONFIG_VERSION,
    "language": "auto",
    "self_name": "",
    "player_timeout": 60,
    "max_rows": 6,
    "sort_mode": "recent",
    "icon_cache_days": 30,
    "hotkeys": {
        "toggle_sound": "F8",
        "map_lookup": "F9",
        "toggle_visible": "F12",
        "mark_party": "F10",
        "toggle_click_through": "F11",
    },
    "overlay": {"x": None, "y": None, "opacity": 0.9, "sound": False,
                "map_x": None, "map_y": None},
    "map_history": [],
    "gather": {
        "kinds": ["Log", "Rock", "Fiber", "Hide", "Ore"],
        "show_living": True,
        "qualities": {kind: [f"{tier}.{enchant}" for tier in range(1, 9)
                             for enchant in range(0, 5)]
                      for kind in KIND_ORDER},
        "sort": "nearest",
        "max_targets": 5,
    },
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


def _tier_value(value, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(1, min(8, parsed))


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
        """老配置一次性升级：v2 起提示音默认关闭；v3 起换用新的默认热键布局；
        v5 起把层级区间展开为 40 项品质集合；v6 起品质按资源种类独立保存。"""
        if isinstance(version, int) and version >= CONFIG_VERSION:
            return
        legacy = version if isinstance(version, int) else 0
        if legacy < 2:
            # 避免城里持续蜂鸣
            self.data["overlay"]["sound"] = False
        if legacy < 3:
            self.data["hotkeys"] = copy.deepcopy(DEFAULT_CONFIG["hotkeys"])
        if legacy < 5:
            self._migrate_qualities()
        if legacy < 6:
            self._migrate_qualities_by_kind()
        self.data["config_version"] = CONFIG_VERSION
        self.save()

    def _migrate_qualities(self) -> None:
        """v4 及更早：把 tier_min~tier_max 展开为 [tier]×[0..4]，再删掉旧键。"""
        gather = self.data.get("gather")
        if not isinstance(gather, dict):
            return
        if "tier_min" not in gather and "tier_max" not in gather:
            return
        low = _tier_value(gather.get("tier_min"), 1)
        high = _tier_value(gather.get("tier_max"), 8)
        if low > high:
            low, high = high, low
        gather["qualities"] = [f"{tier}.{enchant}"
                               for tier in range(low, high + 1)
                               for enchant in range(0, 5)]
        gather.pop("tier_min", None)
        gather.pop("tier_max", None)

    def _migrate_qualities_by_kind(self) -> None:
        """v5 扁平数组 → 按种类字典；已启用种类沿用旧值，其余填默认。"""
        gather = self.data.get("gather")
        if not isinstance(gather, dict):
            return
        raw = gather.get("qualities")
        if not isinstance(raw, (list, tuple)):
            return
        defaults = DEFAULT_CONFIG["gather"]["qualities"]
        enabled = gather.get("kinds")
        enabled = set(enabled) if isinstance(enabled, list) else set(KIND_ORDER)
        gather["qualities"] = {
            kind: list(raw) if kind in enabled else list(defaults[kind])
            for kind in KIND_ORDER
        }

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

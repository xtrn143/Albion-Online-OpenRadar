# client/albion_aware/party.py
"""队友名单：昵称为主键，支持自动事件与手动标记，落盘到 party.json。"""
import json
import os
from pathlib import Path


def _normalize(name) -> str:
    return (name or "").strip().lower()


class PartyList:
    def __init__(self, path: str | Path | None = None):
        self._names: set[str] = set()
        self._pending_ids: set[int] = set()
        self.path = Path(path) if path else None
        if self.path is not None:
            self._load()

    @property
    def names(self) -> set[str]:
        return set(self._names)

    def contains_name(self, name) -> bool:
        key = _normalize(name)
        return bool(key) and key in self._names

    def add_name(self, name) -> None:
        key = _normalize(name)
        if key:
            self._names.add(key)

    def remove_name(self, name) -> None:
        self._names.discard(_normalize(name))

    def add_by_id(self, player_id: int, store) -> None:
        player = store.get(player_id)
        if player is not None and player.nickname:
            self.add_name(player.nickname)
        else:
            self._pending_ids.add(player_id)

    def resolve(self, store) -> None:
        for player_id in list(self._pending_ids):
            player = store.get(player_id)
            if player is not None and player.nickname:
                self.add_name(player.nickname)
                self._pending_ids.discard(player_id)

    def handle_event(self, parameters: dict, store) -> None:
        known = store.known_names()
        for key, value in parameters.items():
            if key == "252":
                continue
            if isinstance(value, int) and not isinstance(value, bool) and value > 10000:
                self.add_by_id(value, store)
            elif isinstance(value, str) and _normalize(value) in known:
                self.add_name(value)

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        names = raw.get("names") if isinstance(raw, dict) else None
        if isinstance(names, list):
            for name in names:
                self.add_name(name)

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"names": sorted(self._names)}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

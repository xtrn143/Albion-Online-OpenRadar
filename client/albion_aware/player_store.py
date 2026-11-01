"""玩家表：唯一事实来源，负责增删改、超时清理与展示过滤。"""
import time
from dataclasses import fields as _dataclass_fields

from albion_aware.models import Player, View

_RESERVED = {"id", "first_seen", "last_seen"}


class PlayerStore:
    def __init__(self, self_name: str = "", timeout: float = 60.0, clock=time.time):
        self._players: dict[int, Player] = {}
        self._self_name = (self_name or "").strip().lower()
        self.timeout = timeout
        self._clock = clock

    def set_self_name(self, name: str) -> None:
        self._self_name = (name or "").strip().lower()

    def get(self, player_id: int) -> Player | None:
        return self._players.get(player_id)

    def upsert(self, player_id: int, fields: dict, now: float | None = None) -> tuple[Player, bool]:
        now = self._clock() if now is None else now
        player = self._players.get(player_id)
        is_new = player is None
        if is_new:
            player = Player(id=player_id, first_seen=now)
            self._players[player_id] = player
        allowed = {f.name for f in _dataclass_fields(Player)} - _RESERVED
        for key, value in fields.items():
            if key in allowed and value is not None:
                setattr(player, key, value)
        player.last_seen = now
        return player, is_new

    def touch(self, player_id: int, now: float | None = None) -> None:
        now = self._clock() if now is None else now
        player = self._players.get(player_id)
        if player is not None:
            player.last_seen = now

    def remove(self, player_id: int) -> bool:
        return self._players.pop(player_id, None) is not None

    def clear(self) -> None:
        self._players.clear()

    def prune(self, now: float | None = None) -> list[int]:
        now = self._clock() if now is None else now
        stale = [pid for pid, p in self._players.items() if now - p.last_seen > self.timeout]
        for pid in stale:
            del self._players[pid]
        return stale

    def is_self(self, player: Player) -> bool:
        if not self._self_name:
            return False
        return player.nickname.strip().lower() == self._self_name

    def known_names(self) -> dict[str, int]:
        """小写昵称 → 玩家 id，供队友事件的名称匹配使用。"""
        return {p.nickname.strip().lower(): p.id for p in self._players.values() if p.nickname}

    def view(self, party, max_rows: int = 6, sort_mode: str = "recent",
             ip_getter=None, now: float | None = None) -> View:
        if now is not None:
            self.prune(now)
        rows = [
            p for p in self._players.values()
            if not self.is_self(p) and not party.contains_name(p.nickname)
        ]
        if sort_mode == "ip" and ip_getter is not None:
            rows.sort(key=lambda p: (-(ip_getter(p) if ip_getter(p) is not None else -1), -p.first_seen))
        else:
            rows.sort(key=lambda p: -p.first_seen)
        shown = rows[:max_rows]
        return View(rows=shown, hidden=max(len(rows) - len(shown), 0))

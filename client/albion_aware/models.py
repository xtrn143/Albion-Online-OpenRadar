from dataclasses import dataclass, field


@dataclass
class Player:
    """一个玩家在协议里的可观测状态，字段一律就地更新，不重建对象。"""

    id: int
    nickname: str = ""
    guid: str = ""
    guild: str = ""
    alliance: str = ""
    faction: int = 0
    equip: list[int] = field(default_factory=list)
    spells: list[str] = field(default_factory=list)
    hp: int = 0
    max_hp: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0


@dataclass
class View:
    """一次界面刷新所需的玩家快照；hidden 为被折叠的行数。"""

    rows: list[Player] = field(default_factory=list)
    hidden: int = 0

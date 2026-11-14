"""采集目标的筛选、打分与屏幕空间方位（纯逻辑，不依赖 tkinter）。"""
import math
from dataclasses import dataclass, field

MAX_RANGE = 80.0
KIND_ORDER = ("Log", "Rock", "Fiber", "Hide", "Ore")
SORT_MODES = ("nearest", "tier", "efficiency")
DEFAULT_SORT = "nearest"
DEFAULT_MAX_TARGETS = 5

# 权重顺序：距离、层级、附魔、剩余层数（与雷达网页端一致）
MODE_WEIGHTS = {
    "nearest": (0.60, 0.20, 0.10, 0.10),
    "tier": (0.15, 0.35, 0.35, 0.15),
    "efficiency": (0.25, 0.25, 0.15, 0.35),
}


ALL_QUALITIES = frozenset(
    (tier, enchant) for tier in range(1, 9) for enchant in range(0, 5)
)


@dataclass(frozen=True)
class GatherFilter:
    kinds: frozenset[str] = frozenset(KIND_ORDER)
    show_living: bool = True
    qualities: dict[str, frozenset[tuple[int, int]]] = field(
        default_factory=lambda: {kind: ALL_QUALITIES for kind in KIND_ORDER})
    sort: str = DEFAULT_SORT
    max_targets: int = DEFAULT_MAX_TARGETS

    @classmethod
    def from_config(cls, config) -> "GatherFilter":
        raw_kinds = config.get("gather.kinds", list(KIND_ORDER)) or []
        kinds = frozenset(kind for kind in raw_kinds if kind in KIND_ORDER) or frozenset(KIND_ORDER)
        sort = config.get("gather.sort", DEFAULT_SORT)
        return cls(
            kinds=kinds,
            show_living=bool(config.get("gather.show_living", True)),
            qualities=qualities_from_config(config.get("gather.qualities")),
            sort=sort if sort in SORT_MODES else DEFAULT_SORT,
            max_targets=_clamp_int(config.get("gather.max_targets", DEFAULT_MAX_TARGETS),
                                   1, 10, DEFAULT_MAX_TARGETS),
        )

    def to_dict(self) -> dict:
        return {
            "kinds": [kind for kind in KIND_ORDER if kind in self.kinds],
            "show_living": self.show_living,
            "qualities": {kind: [f"{tier}.{enchant}" for tier, enchant
                                 in sorted(self.qualities.get(kind, ALL_QUALITIES))]
                          for kind in KIND_ORDER},
            "sort": self.sort,
            "max_targets": self.max_targets,
        }

    def is_default(self) -> bool:
        return self == GatherFilter()


def parse_quality(value) -> tuple[int, int] | None:
    """把 "5.1" 解析成 (5, 1)；非法值返回 None。"""
    if not isinstance(value, str) or "." not in value:
        return None
    tier_text, enchant_text = value.split(".", 1)
    try:
        tier, enchant = int(tier_text), int(enchant_text)
    except ValueError:
        return None
    if 1 <= tier <= 8 and 0 <= enchant <= 4:
        return (tier, enchant)
    return None


def _quality_set(raw, empty_falls_back: bool = True) -> frozenset[tuple[int, int]]:
    """解析单个种类的品质列表；非法元素丢弃，为空时按调用方语义决定是否回退全选。"""
    if not isinstance(raw, (list, tuple)):
        return ALL_QUALITIES
    parsed = {quality for quality in (parse_quality(item) for item in raw) if quality}
    if parsed:
        return frozenset(parsed)
    return ALL_QUALITIES if empty_falls_back else frozenset()


def qualities_from_config(raw) -> dict[str, frozenset[tuple[int, int]]]:
    """列表按旧格式应用到全部种类；字典按键解析，缺失/非法回退全选，空选保留为空。"""
    if isinstance(raw, dict):
        return {kind: _quality_set(raw.get(kind), empty_falls_back=False)
                for kind in KIND_ORDER}
    if isinstance(raw, (list, tuple)):
        shared = _quality_set(raw)
        return {kind: shared for kind in KIND_ORDER}
    return {kind: ALL_QUALITIES for kind in KIND_ORDER}


@dataclass(frozen=True)
class GatherTarget:
    harvestable_id: int
    kind: str
    tier: int
    enchant: int
    size: int
    x: float
    y: float
    is_living: bool
    distance: float | None
    bearing_deg: float | None
    score: float = 0.0


def _clamp_int(value, low: int, high: int, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, parsed))


def has_position(player_pos) -> bool:
    if player_pos is None:
        return False
    x, y = player_pos
    return not (x == 0 and y == 0)


def to_screen_vector(x: float, y: float, px: float, py: float) -> tuple[float, float]:
    """与雷达一致：X 轴先取反，再做等距 -45° 旋转（比例无关的方向）。"""
    dx, dy = x - px, y - py
    return (dx + dy, dx - dy)


def distance_to(x: float, y: float, px: float, py: float) -> float:
    return math.hypot(x - px, y - py)


def bearing_of(x: float, y: float, px: float, py: float) -> float:
    sx, sy = to_screen_vector(x, y, px, py)
    return math.degrees(math.atan2(sy, sx))


def select_targets(nodes, player_pos, filters: GatherFilter) -> list[GatherTarget]:
    positioned = has_position(player_pos)
    px, py = player_pos if positioned else (0.0, 0.0)

    candidates = []
    max_size = 1
    for node in nodes:
        size = node.size
        if size is None or size <= 0:
            continue
        if node.kind not in filters.kinds:
            continue
        if node.is_living and not filters.show_living:
            continue
        if (node.tier, node.enchant or 0) not in filters.qualities.get(
                node.kind, ALL_QUALITIES):
            continue

        distance = None
        bearing = None
        if positioned:
            distance = distance_to(node.x, node.y, px, py)
            if distance > MAX_RANGE:
                continue
            bearing = bearing_of(node.x, node.y, px, py)

        max_size = max(max_size, size)
        candidates.append((node, distance, bearing))

    weights = MODE_WEIGHTS.get(filters.sort, MODE_WEIGHTS[DEFAULT_SORT])
    targets = []
    for node, distance, bearing in candidates:
        proximity = 0.0 if distance is None else 1 - distance / MAX_RANGE
        score = (weights[0] * proximity
                 + weights[1] * ((node.tier or 0) / 8)
                 + weights[2] * ((node.enchant or 0) / 4)
                 + weights[3] * (node.size / max_size))
        targets.append(GatherTarget(
            harvestable_id=node.harvestable_id,
            kind=node.kind,
            tier=node.tier,
            enchant=node.enchant or 0,
            size=node.size,
            x=node.x,
            y=node.y,
            is_living=node.is_living,
            distance=distance,
            bearing_deg=bearing,
            score=score,
        ))

    if not positioned:
        # 没有自身坐标时只按层级/附魔给出稳定顺序
        targets.sort(key=lambda t: (-t.tier, -t.enchant, t.harvestable_id))
    else:
        targets.sort(key=lambda t: (-t.score,
                                    t.distance if t.distance is not None else 0.0,
                                    t.harvestable_id))
    return targets[:filters.max_targets]


def format_tier_enchant(tier: int, enchant: int) -> str:
    return f"T{int(tier)}.{int(enchant or 0)}"


def format_distance(distance: float | None) -> str:
    if distance is None:
        return "--"
    return f"{int(round(distance))}m"


def targets_hash(targets, status: str = "") -> str:
    """距离按 5m、方位按 15° 分桶，静止时避免反复重建控件。"""
    parts = [status]
    for target in targets:
        distance = "" if target.distance is None else int(target.distance // 5)
        bearing = "" if target.bearing_deg is None else int(target.bearing_deg // 15)
        parts.append(":".join(str(item) for item in (
            target.harvestable_id, target.kind, target.tier, target.enchant,
            target.size, distance, bearing,
        )))
    return "|".join(parts)

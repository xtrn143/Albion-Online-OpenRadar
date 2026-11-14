"""采集资源表：保留当前区域内的资源点，供采集模式筛选与排序。"""
from albion_aware.event_parser import HarvestNode

MAX_NODES = 4000


class GatherStore:
    """资源点不会被周期性上报，因此不做时间淘汰；只在切区、离开与采空时删除。"""

    def __init__(self, max_nodes: int = MAX_NODES):
        self._nodes: dict[int, HarvestNode] = {}
        self.max_nodes = max_nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def get(self, harvestable_id: int) -> HarvestNode | None:
        return self._nodes.get(harvestable_id)

    def snapshot(self) -> list[HarvestNode]:
        return list(self._nodes.values())

    def upsert(self, node: HarvestNode) -> tuple[HarvestNode, bool]:
        existing = self._nodes.get(node.harvestable_id)
        if existing is None:
            self._nodes[node.harvestable_id] = node
            self._trim()
            return node, True
        # 批量事件不带附魔，None 表示“保留已知值”而不是清空
        if node.kind:
            existing.kind = node.kind
        if node.tier:
            existing.tier = node.tier
        if node.enchant is not None:
            existing.enchant = node.enchant
        if node.size is not None:
            existing.size = node.size
        if node.type_number:
            existing.type_number = node.type_number
        existing.x, existing.y = node.x, node.y
        existing.is_living = node.is_living
        return existing, False

    def apply_batch(self, nodes) -> bool:
        changed = False
        for node in nodes:
            _node, _is_new = self.upsert(node)
            changed = True
        return changed

    def apply_state(self, harvestable_id: int, size: int | None,
                    enchant: int | None) -> bool:
        """size 缺失或为 0 视为采空；附魔缺失时保留旧值。"""
        node = self._nodes.get(harvestable_id)
        if node is None:
            return False
        if size is None or size <= 0:
            del self._nodes[harvestable_id]
            return True
        node.size = size
        if enchant is not None:
            node.enchant = enchant
        return True

    def remove(self, harvestable_id: int) -> bool:
        return self._nodes.pop(harvestable_id, None) is not None

    def clear(self) -> None:
        self._nodes.clear()

    def _trim(self) -> None:
        if self.max_nodes <= 0:
            return
        while len(self._nodes) > self.max_nodes:
            self._nodes.pop(next(iter(self._nodes)))

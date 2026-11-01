"""物品库、平均物品强度、武器图标下载与本地缓存。"""
import json
import re
import urllib.parse
from pathlib import Path

from PIL import Image, ImageDraw

# 官方渲染服务：按唯一名获取物品图标
RENDER_URL = "https://render.albiononline.com/v1/item/{name}.png?size={size}"
# 层级前缀（T6_）与附魔后缀（@3）
_TIER = re.compile(r"^T\d+_")
_ENCHANT = re.compile(r"@\d+$")

# 详情面板槽位 -> 装备数组下标
EQUIP_SLOTS = {
    "mainhand": 0,
    "offhand": 1,
    "head": 2,
    "chest": 3,
    "shoes": 4,
    "cape": 5,
    "mount": 6,
    "bag": 7,
    "potion": 8,
    "food": 9,
}
# 参与平均 IP 的战斗槽：主手、副手、头、衣、鞋、药水
COMBAT_SLOTS = (0, 1, 2, 3, 4, 8)


class ItemDatabase:
    def __init__(self, items: list):
        # 数组下标即物品 id，只保留带唯一名的字典条目
        self._items = {
            index: entry
            for index, entry in enumerate(items)
            if isinstance(entry, dict) and entry.get("n")
        }

    @classmethod
    def load(cls, path: str | Path) -> "ItemDatabase":
        # 容忍缺文件 / 坏数据：返回空库而不是抛异常
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = []
        return cls(raw if isinstance(raw, list) else [])

    def get(self, item_id: int) -> dict | None:
        return self._items.get(int(item_id))

    def unique_name(self, item_id: int) -> str | None:
        item = self.get(item_id)
        return item.get("n") if item else None

    def display_name(self, item_id: int) -> str | None:
        unique = self.unique_name(item_id)
        if not unique:
            return None
        # 去掉 T? 前缀与 @n 附魔后缀，下划线转空格
        base = _ENCHANT.sub("", _TIER.sub("", unique))
        return base.replace("_", " ")

    def average_ip(self, equip: list[int]) -> int | None:
        total = valid = 0
        for index in COMBAT_SLOTS:
            if index >= len(equip):
                continue
            item = self.get(equip[index])
            power = int(item.get("p") or 0) if item else 0
            if power > 0:
                total += power
                valid += 1
        # 没有有效物品时返回 None
        return round(total / valid) if valid else None


class IconCache:
    def __init__(self, cache_dir: str | Path, db: ItemDatabase, fetch=None, size: int = 60):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db = db
        self.size = size
        # fetch 可注入（测试用），默认走 requests
        self._fetch = fetch or self._http_fetch

    def get(self, item_id: int) -> Path:
        unique = self.db.unique_name(item_id)
        if not unique:
            return self.placeholder("unknown")
        dest = self.cache_dir / f"{urllib.parse.quote(unique, safe='')}.png"
        if dest.exists():
            return dest
        url = RENDER_URL.format(name=urllib.parse.quote(unique, safe=''), size=self.size)
        if self._fetch(url, dest) and dest.exists():
            return dest
        return self.placeholder(self._category(item_id))

    def placeholder(self, category: str = "unknown") -> Path:
        # 占位图按类别着色，同一类别复用同一文件
        dest = self.cache_dir / f"_placeholder_{category or 'unknown'}.png"
        if dest.exists():
            return dest
        colors = {
            "weapons": (150, 150, 165),
            "armor": (120, 135, 155),
            "consumable": (145, 120, 95),
        }
        color = colors.get(category, (105, 105, 110))
        image = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((4, 4, self.size - 4, self.size - 4), radius=6, fill=color + (215,))
        image.save(dest, format="PNG")
        return dest

    def _category(self, item_id: int) -> str:
        item = self.db.get(item_id)
        return str(item.get("cat") or "unknown") if item else "unknown"

    @staticmethod
    def _http_fetch(url: str, dest: Path) -> bool:
        # 默认下载实现；测试通过注入 fetch 避免真实网络请求
        import requests
        try:
            response = requests.get(url, timeout=5)
        except requests.RequestException:
            return False
        if response.status_code != 200 or not response.content:
            return False
        dest.write_bytes(response.content)
        return True

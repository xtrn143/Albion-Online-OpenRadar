"""物品库、平均物品强度、武器图标下载与本地缓存。"""
import json
import re
import urllib.parse
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 官方渲染服务：按唯一名获取物品图标。
# 注意：不要加 ?size= 查询参数——实测该参数会让服务端返回 502，无查询串才稳定返回 PNG。
RENDER_URL = "https://render.albiononline.com/v1/item/{name}.png"
# 层级前缀（T6_）与附魔后缀（@3）
_TIER = re.compile(r"^T\d+_")
_ENCHANT = re.compile(r"@(\d+)$")

# 附魔等级角标配色：1 绿、2 蓝、3 紫、4 橙
ENCHANT_COLORS = {
    1: (86, 190, 92),
    2: (72, 145, 235),
    3: (168, 100, 222),
    4: (236, 168, 58),
}


def enchant_level(unique: str | None) -> int:
    """从唯一名解析附魔等级，如 T6_MAIN_SWORD@3 -> 3。"""
    match = _ENCHANT.search(unique or "")
    return int(match.group(1)) if match else 0


@lru_cache(maxsize=32)
def _font(px: int):
    for name in ("arialbd.ttf", "segoeuib.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_enchant_badge(image: Image.Image, level: int) -> Image.Image:
    """在图标右下角画附魔等级角标；官方图该位置本来就是留空的。"""
    if level <= 0:
        return image
    image = image.convert("RGBA")
    side = min(image.width, image.height)
    size = max(int(round(side * 0.46)), 7)
    x0, y0 = image.width - size, image.height - size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    color = ENCHANT_COLORS.get(level, (200, 200, 200))
    draw.rounded_rectangle((x0, y0, image.width - 1, image.height - 1),
                           radius=max(size // 4, 2), fill=color + (240,))
    font = _font(max(int(round(size * 0.7)), 7))
    text = str(level)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text((x0 + (size - (right - left)) / 2 - left,
               y0 + (size - (bottom - top)) / 2 - top),
              text, font=font, fill=(255, 255, 255, 255))
    return Image.alpha_composite(image, overlay)



def _slug(unique: str) -> str:
    """缓存文件名与 URL 片段；@ 是附魔分隔符，必须原样保留。

    渲染服务对 ``%40`` 编码会返回 502，因此只转义真正需要转义的字符。
    """
    return urllib.parse.quote(unique, safe='@')

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
    def __init__(self, cache_dir: str | Path, db: ItemDatabase, fetch=None,
                 size: int = 60, bundled: str | Path | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db = db
        self.size = size
        # 随包分发的离线图标目录（只读，命中后再走用户缓存或下载）
        self.bundled = Path(bundled) if bundled else None
        # fetch 可注入（测试用），默认走 requests
        self._fetch = fetch or self._http_fetch

    def _locate(self, unique: str) -> Path | None:
        name = f"{_slug(unique)}.png"
        if self.bundled is not None:
            candidate = self.bundled / name
            if candidate.exists():
                return candidate
        dest = self.cache_dir / name
        return dest if dest.exists() else None

    def get(self, item_id: int) -> Path:
        unique = self.db.unique_name(item_id)
        if not unique:
            return self.placeholder("unknown")
        found = self._locate(unique)
        if found is not None:
            return found
        dest = self.cache_dir / f"{_slug(unique)}.png"
        url = RENDER_URL.format(name=_slug(unique))
        if self._fetch(url, dest) and dest.exists():
            return dest
        return self.placeholder(self._category(item_id))

    def path_for(self, item_id: int) -> Path | None:
        """本机可用的图标路径；没有返回 None（不触发下载）。"""
        unique = self.db.unique_name(item_id)
        if not unique:
            return None
        return self._locate(unique)

    def placeholder_for(self, item_id: int) -> Path:
        """按物品类别返回占位图路径（必要时生成）。"""
        return self.placeholder(self._category(item_id))

    def placeholder(self, category: str = "unknown") -> Path:
        # 占位图按类别着色，同一类别复用同一文件
        dest = self.cache_dir / f"_placeholder_{category or 'unknown'}.png"
        if dest.exists():
            return dest
        # 键与 ao-bin-dumps 的 cat 字段一致（复数是官方写法）
        colors = {
            "weapons": (150, 150, 165),
            "offhands": (140, 145, 160),
            "armors": (120, 135, 155),
            "head": (125, 130, 150),
            "shoes": (115, 125, 145),
            "capes": (135, 120, 140),
            "consumables": (145, 120, 95),
            "mounts": (120, 140, 120),
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
            response = requests.get(url, timeout=10)
        except requests.RequestException:
            return False
        if response.status_code != 200 or not response.content:
            return False
        dest.write_bytes(response.content)
        return True

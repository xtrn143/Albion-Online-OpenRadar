import json

from PIL import Image

from albion_aware.icons import (COMBAT_SLOTS, EQUIP_SLOTS, IconCache, ItemDatabase,
                               draw_enchant_badge, enchant_level)


def make_db(tmp_path):
    path = tmp_path / "items.json"
    items = [None, {"n": "T6_MAIN_SWORD", "p": 900, "cat": "weapons", "t": "weapon"}]
    for index in range(2, 12):
        items.append({"n": f"ITEM_{index}", "p": 900, "cat": "armor", "t": "equipmentitem"})
    path.write_text(json.dumps(items), encoding="utf-8")
    return ItemDatabase.load(path)


def test_lookup_unique_and_display_name(tmp_path):
    db = make_db(tmp_path)
    assert db.unique_name(1) == "T6_MAIN_SWORD"
    assert db.display_name(1) == "MAIN SWORD"
    assert db.unique_name(0) is None


def test_display_name_strips_enchant_suffix(tmp_path):
    db = make_db(tmp_path)
    db._items[1] = {"n": "T6_MAIN_SWORD@3", "p": 1200}
    assert db.display_name(1) == "MAIN SWORD"


def test_bundled_icon_is_used_before_cache_and_network(tmp_path):
    db = make_db(tmp_path)
    bundled = tmp_path / "icons"
    bundled.mkdir()
    (bundled / "T6_MAIN_SWORD.png").write_bytes(b"fake-png")
    calls = []

    def fetch(url, dest):
        calls.append(url)
        return False

    cache = IconCache(tmp_path / "cache", db, fetch=fetch, bundled=bundled)
    assert cache.get(1) == bundled / "T6_MAIN_SWORD.png"
    assert cache.path_for(1) == bundled / "T6_MAIN_SWORD.png"
    assert calls == []


def test_bundled_miss_falls_back_to_download(tmp_path):
    db = make_db(tmp_path)
    bundled = tmp_path / "icons"
    bundled.mkdir()
    seen = {}

    def fetch(url, dest):
        seen["url"] = url
        dest.write_bytes(b"fake-png")
        return True

    cache = IconCache(tmp_path / "cache", db, fetch=fetch, bundled=bundled)
    assert cache.path_for(1) is None
    assert cache.get(1) == tmp_path / "cache" / "T6_MAIN_SWORD.png"
    assert seen["url"].endswith("T6_MAIN_SWORD.png")


def test_enchant_level_parsed_from_unique_name():
    assert enchant_level("T6_MAIN_SWORD@3") == 3
    assert enchant_level("T4_MAIN_SWORD") == 0
    assert enchant_level(None) == 0


def test_badge_draws_in_lower_corner_without_resizing():
    image = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    result = draw_enchant_badge(image, 3)
    assert result.size == (48, 48)
    assert result.getpixel((44, 44))[3] > 0
    assert result.getpixel((4, 4))[3] == 0
    assert draw_enchant_badge(image, 0) is image


def test_slot_mapping_follows_game_protocol_order():
    assert EQUIP_SLOTS["mainhand"] == 0
    assert EQUIP_SLOTS["offhand"] == 1
    assert EQUIP_SLOTS["head"] == 2
    assert EQUIP_SLOTS["chest"] == 3
    assert EQUIP_SLOTS["shoes"] == 4
    assert EQUIP_SLOTS["bag"] == 5
    assert EQUIP_SLOTS["cape"] == 6
    assert EQUIP_SLOTS["mount"] == 7
    assert EQUIP_SLOTS["potion"] == 8
    assert EQUIP_SLOTS["food"] == 9
    assert COMBAT_SLOTS == (0, 1, 2, 3, 4, 6)


def combat_db(tmp_path):
    path = tmp_path / "combat.json"
    items = [
        None,
        {"n": "T8_2H_SWORD", "p": 1000, "h2": True, "t": "weapon", "cat": "weapons"},
        {"n": "T8_HEAD", "p": 800, "t": "equipmentitem", "cat": "head"},
        {"n": "T8_ARMOR", "p": 800, "t": "equipmentitem", "cat": "armors"},
        {"n": "T8_SHOES", "p": 800, "t": "equipmentitem", "cat": "shoes"},
        {"n": "T8_CAPE", "p": 800, "t": "equipmentitem", "cat": "capes"},
        {"n": "T8_TOOL", "p": 500, "h2": True, "t": "weapon", "cat": "gathering"},
    ]
    path.write_text(json.dumps(items), encoding="utf-8")
    return ItemDatabase.load(path)


def test_average_ip_counts_six_slots_and_two_handed_weapon_twice(tmp_path):
    db = combat_db(tmp_path)
    # 主手双手武器占主手+副手两个槽
    equip = [1, 0, 2, 3, 4, 0, 5, 0, 0, 0]
    assert db.average_ip(equip) == round((1000 + 1000 + 800 + 800 + 800 + 800) / 6)


def test_average_ip_treats_empty_slots_as_zero(tmp_path):
    db = combat_db(tmp_path)
    # 只有头衣鞋：其余三个槽记 0，而不是只除以 3
    equip = [0, 0, 2, 3, 4]
    assert db.average_ip(equip) == 400


def test_average_ip_does_not_double_count_gathering_tool(tmp_path):
    db = combat_db(tmp_path)
    assert db.average_ip([6]) == round(500 / 6)


def test_average_ip_returns_none_without_valid_items(tmp_path):
    db = make_db(tmp_path)
    assert db.average_ip([0, 0]) is None
    assert db.average_ip([]) is None


def test_icon_is_downloaded_once(tmp_path):
    db = make_db(tmp_path)
    calls = []

    def fetch(url, dest):
        calls.append(url)
        dest.write_bytes(b"fake-png")
        return True

    cache = IconCache(tmp_path / "cache", db, fetch=fetch)
    first = cache.get(1)
    second = cache.get(1)
    assert first == second
    assert len(calls) == 1
    assert first.read_bytes() == b"fake-png"


def test_icon_url_has_no_size_query(tmp_path):
    db = make_db(tmp_path)
    calls = []

    def fetch(url, dest):
        calls.append(url)
        dest.write_bytes(b"fake-png")
        return True

    IconCache(tmp_path / "cache", db, fetch=fetch).get(1)
    # 渲染服务对 ?size= 参数会返回 502，必须用纯路径
    assert calls[0].endswith(".png")
    assert "size=" not in calls[0]


def test_enchanted_item_keeps_at_sign_in_url(tmp_path):
    db = make_db(tmp_path)
    db._items[1] = {"n": "T6_MAIN_SWORD@3", "p": 1200, "cat": "weapons"}
    calls = []

    def fetch(url, dest):
        calls.append(url)
        dest.write_bytes(b"fake-png")
        return True

    IconCache(tmp_path / "cache", db, fetch=fetch).get(1)
    # 附魔符号 @ 不能被编码成 %40，否则渲染服务返回 502
    assert "@3" in calls[0]
    assert "%40" not in calls[0]


def test_path_for_does_not_trigger_download(tmp_path):
    db = make_db(tmp_path)
    calls = []

    def fetch(url, dest):
        calls.append(url)
        return False

    cache = IconCache(tmp_path / "cache", db, fetch=fetch)
    assert cache.path_for(1) is None
    assert calls == []


def test_path_for_returns_cached_file_and_placeholder_exists(tmp_path):
    db = make_db(tmp_path)
    cache = IconCache(tmp_path / "cache", db, fetch=lambda url, dest: dest.write_bytes(b"png") or True)
    cached = cache.get(1)
    assert cache.path_for(1) == cached
    assert cache.placeholder_for(0).exists()


def test_failed_download_uses_placeholder(tmp_path):
    db = make_db(tmp_path)
    cache = IconCache(tmp_path / "cache", db, fetch=lambda url, dest: False)
    path = cache.get(1)
    assert path.exists()
    assert path.name.startswith("_placeholder_")


def test_unknown_item_uses_placeholder(tmp_path):
    db = make_db(tmp_path)
    cache = IconCache(tmp_path / "cache", db, fetch=lambda url, dest: False)
    assert cache.get(0).name.startswith("_placeholder_")

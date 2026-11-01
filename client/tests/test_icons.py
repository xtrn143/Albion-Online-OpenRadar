import json

from albion_aware.icons import COMBAT_SLOTS, EQUIP_SLOTS, IconCache, ItemDatabase


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


def test_slot_mapping_covers_all_detail_panel_slots():
    assert EQUIP_SLOTS["mainhand"] == 0
    assert EQUIP_SLOTS["bag"] == 7
    assert EQUIP_SLOTS["potion"] == 8
    assert EQUIP_SLOTS["food"] == 9
    assert COMBAT_SLOTS == (0, 1, 2, 3, 4, 8)


def test_average_ip_only_uses_combat_slots(tmp_path):
    db = make_db(tmp_path)
    equip = [1, 1, 1, 1, 1, 99, 99, 99, 2, 99]
    assert db.average_ip(equip) == 900


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

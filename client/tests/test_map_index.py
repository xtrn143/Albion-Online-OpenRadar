from albion_aware.map_index import (
    AvalonMapIndex,
    build_index_records,
    compact,
    is_roads_zone,
    key3,
    make_entry,
    parts_of,
    tokenize,
)


def _entry(name, tier=6, icons=(), zone_ids=()):
    return make_entry(name, tier, icons, f"{name} T{tier}.webp", zone_ids)


def _index():
    return AvalonMapIndex([
        _entry("Hetitos-Iuaerom", 6, (("GOLD", 0),), ("TNL-225",)),
        _entry("Hetitos-Ouanerom", 8, (), ("TNL-226",)),
        _entry("Secent-Qi-Odesom", 4, (("BLUE", 0),), ("TNL-377",)),
        _entry("Cases-Ugumlos", 6, (), ("TNL-100",)),
    ])


def test_fold_treats_capital_i_and_l_as_same():
    assert compact("HET LUA") == "HETIUA"
    assert compact("HET-LUA") == "HETIUA"
    assert key3("Hetitos-Iuaerom") == "HETIUA"


def test_key3_uses_first_three_letters_of_each_part():
    assert key3("Hetitos-Iuaerom") == "HETIUA"
    assert key3("Secent-Qi-Odesom") == "SECQIODE"
    assert parts_of("Secent-Qi-Odesom") == ("SECENT", "QI", "ODESOM")


def test_tokenize_keeps_tokens_and_compact_form():
    assert tokenize("SEC QI ODE") == (["SEC", "QI", "ODE"], "SECQIODE")


def test_is_roads_zone_accepts_only_tnl_ids():
    assert is_roads_zone("TNL-241") is True
    assert is_roads_zone("tnl-241") is True
    assert is_roads_zone("5001") is False
    assert is_roads_zone(None) is False


def test_three_letter_habit_hits_exactly_one_map():
    hits = _index().query("HET LUA")
    assert hits[0].entry.name == "Hetitos-Iuaerom"
    assert len(hits) == 1


def test_compact_habit_without_separator_hits():
    hits = _index().query("HETLUA")
    assert hits[0].entry.name == "Hetitos-Iuaerom"


def test_three_part_habit_hits():
    hits = _index().query("SEC QI ODE")
    assert hits[0].entry.name == "Secent-Qi-Odesom"


def test_three_part_compact_hits():
    hits = _index().query("SECQIODE")
    assert hits[0].entry.name == "Secent-Qi-Odesom"


def test_full_name_is_ranked_first():
    hits = _index().query("hetitos-iuaerom")
    assert hits[0].entry.name == "Hetitos-Iuaerom"


def test_typo_falls_back_to_fuzzy():
    hits = _index().query("HETLUB")
    assert hits and hits[0].entry.name == "Hetitos-Iuaerom"


def test_current_zone_is_boosted_to_top():
    hits = _index().query("HET", current_zone="TNL-226")
    assert hits[0].entry.name == "Hetitos-Ouanerom"
    assert hits[0].is_current is True


def test_gold_beats_tier_when_scores_tie():
    hits = _index().query("HET")
    # 两者基础分相同：含金箱的 T6 排在 T8 之前
    assert hits[0].entry.name == "Hetitos-Iuaerom"


def test_limit_is_respected():
    hits = _index().query("", limit=2)
    assert len(hits) == 2


def test_empty_query_puts_current_zone_first():
    hits = _index().query("", current_zone="TNL-100")
    assert hits[0].entry.name == "Cases-Ugumlos"
    assert hits[0].is_current is True


def test_no_match_returns_empty_list():
    assert _index().query("ZZZ") == []


def test_build_index_records_merges_zone_and_gallery():
    zones = {
        "TNL-001": {"name": "Hetitos-Iuaerom", "tier": 6},
        "TNL-002": {"name": "Secent-Qi-Odesom", "tier": 4},
    }
    gallery = [
        {"name": "Hetitos-IUaerom", "tier": 6,
         "icons": [{"alt": "GOLD"}, {"alt": "HIRE"}],
         "img": "img/Hetitos-Iuaerom T6.png"},
    ]
    records = build_index_records(zones, gallery)
    by_name = {record["name"]: record for record in records}
    assert by_name["Hetitos-Iuaerom"]["imgFile"] == "Hetitos-Iuaerom T6.webp"
    assert by_name["Hetitos-Iuaerom"]["zoneIds"] == ["TNL-001"]
    assert by_name["Hetitos-Iuaerom"]["icons"] == [
        {"alt": "GOLD", "badge": 0}, {"alt": "HIDE", "badge": 0}]
    assert by_name["Secent-Qi-Odesom"]["imgFile"] == ""

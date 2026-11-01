from albion_aware.models import Player, View


def test_player_defaults_are_empty():
    player = Player(id=42)
    assert player.nickname == ""
    assert player.equip == []
    assert player.first_seen == 0.0


def test_players_do_not_share_mutable_defaults():
    a, b = Player(id=1), Player(id=2)
    a.equip.append(999)
    a.spells.append("Whirlwind")
    assert b.equip == []
    assert b.spells == []


def test_view_holds_rows_and_hidden_count():
    view = View(rows=[Player(id=1), Player(id=2)], hidden=3)
    assert len(view.rows) == 2
    assert view.hidden == 3

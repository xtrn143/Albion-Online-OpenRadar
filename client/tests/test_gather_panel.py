import math

from albion_aware.gather_panel import (ARROW, BG, FG, MUTED, PANEL_WIDTH, arrow_points,
                                       kind_badge_image, panel_origin)


def test_arrow_points_tip_follows_angle():
    east = arrow_points(0)
    assert len(east) == 6
    assert east[0] > 6 and abs(east[1] - 6) < 0.001

    south = arrow_points(90)
    assert abs(south[0] - 6) < 0.001 and south[1] > 6


def test_arrow_points_never_nan():
    for angle in (None, 0, 45, -135, 359.5):
        assert all(math.isfinite(value) for value in arrow_points(angle))


def test_arrow_points_stay_inside_canvas():
    for angle in range(0, 360, 15):
        values = arrow_points(angle)
        assert all(0 <= value <= 12 for value in values)


def test_tk_colors_are_hex_strings():
    # tkinter 不支持 (r, g, b) 元组，传元组会在 create_polygon 时抛 TclError
    for color in (BG, FG, MUTED, ARROW):
        assert isinstance(color, str) and len(color) == 7 and color.startswith("#")


def test_kind_badge_image_size_and_alpha():
    image = kind_badge_image("Ore")
    assert image.size == (10, 10)
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((5, 5))[3] > 0


def test_panel_origin_prefers_left_side():
    assert panel_origin(300, 200, screen_width=1920) == (300 - PANEL_WIDTH - 8, 200)


def test_panel_origin_flips_right_near_left_edge():
    assert panel_origin(20, 100, screen_width=1920) == (20 + 102 + 8, 100)


def test_panel_origin_clamps_to_screen():
    x, y = panel_origin(1900, 100, screen_width=1920)
    assert 0 <= x <= 1920 - PANEL_WIDTH
    assert y == 100

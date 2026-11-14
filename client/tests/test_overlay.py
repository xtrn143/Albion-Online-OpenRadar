import math
import tkinter as tk
from tkinter import font as tkfont

import pytest

from albion_aware.gather_targets import GatherTarget
from albion_aware.models import View
from albion_aware.overlay import (ARROW_SIZE, GLOW_LAYERS, GLOW_STEP, PAD, ROW_H, TOP_H,
                                  WIDTH, OverlayWindow, arrow_points, filter_icon,
                                  format_ip, ip_color, map_icon, sound_icon)


class _FakeRoot:
    def __init__(self):
        self.geometries = []

    def geometry(self, value):
        self.geometries.append(value)


def test_resize_keeps_negative_position():
    window = OverlayWindow.__new__(OverlayWindow)
    window.root = _FakeRoot()
    window._pos = None
    window.place_at(-120, 300)
    assert window._pos == (-120, 300)
    window._resize(6)
    glow = GLOW_LAYERS * GLOW_STEP * 2
    assert window.root.geometries[-1] == f"{WIDTH}x{PAD * 2 + 6 * ROW_H + TOP_H + glow}+-120+300"


def test_ip_color_thresholds():
    assert ip_color(None) == "#d6d6d6"
    assert ip_color(750) == "#d6d6d6"
    assert ip_color(800) == "#e8c04a"
    assert ip_color(1000) == "#e8c04a"
    assert ip_color(1001) == "#ff7a45"
    assert ip_color(1400) == "#ff7a45"


def test_format_ip():
    assert format_ip(None) == "-"
    assert format_ip(1250) == "1250"
    assert format_ip(900) == "900"


class _Event:
    def __init__(self, x_root, y_root):
        self.x_root = x_root
        self.y_root = y_root


class _DragRoot:
    def __init__(self, x=0, y=0):
        self.x, self.y = x, y
        self.geometries = []
        self.attributes_calls = []

    def geometry(self, value):
        self.geometries.append(value)

    def winfo_x(self):
        return self.x

    def winfo_y(self):
        return self.y

    def attributes(self, *args):
        self.attributes_calls.append(args)


def _drag_window(clicks=None, drags=None):
    window = OverlayWindow.__new__(OverlayWindow)
    window.root = _DragRoot()
    window._pos = (0, 0)
    window._press_origin = None
    window._dragging = False
    window._on_row_click = (lambda player: clicks.append(player)) if clicks is not None else (lambda player: None)
    window._on_drag_end = (lambda x, y: drags.append((x, y))) if drags is not None else (lambda x, y: None)
    return window


def test_drag_moves_window_and_skips_click():
    clicks, drags = [], []
    window = _drag_window(clicks, drags)
    window._start_drag(_Event(10, 20), "p1")
    window._drag(_Event(14, 40))
    window._end_drag(_Event(14, 40), "p1")
    assert window.root.geometries == ["+4+20"]
    assert window._pos == (4, 20)
    assert clicks == []
    assert drags == [(4, 20)]


def test_short_press_opens_detail_without_moving():
    clicks, drags = [], []
    window = _drag_window(clicks, drags)
    window._start_drag(_Event(10, 20), "p1")
    window._end_drag(_Event(11, 21), "p1")
    assert clicks == ["p1"]
    assert window.root.geometries == []
    assert drags == []


def test_set_opacity_applies_alpha():
    window = _drag_window()
    window.set_opacity(0.9)
    assert window.root.attributes_calls == [("-alpha", 0.9)]


class _FakeFrame:
    def __init__(self):
        self.bg = None

    def configure(self, **kwargs):
        self.bg = kwargs.get("bg")


def test_glow_paints_every_layer():
    window = OverlayWindow.__new__(OverlayWindow)
    window._glow = [_FakeFrame() for _ in range(6)]
    window.border = _FakeFrame()
    window._paint_glow(("#ff4b3e", "#e0331f", "#b52616", "#83200f", "#4e170b", "#261210"))
    assert [frame.bg for frame in window._glow] == ["#ff4b3e", "#e0331f", "#b52616", "#83200f", "#4e170b", "#261210"]
    assert window.border.bg == "#261210"


def test_sound_icon_marks_muted_state_with_red_slash():
    on = sound_icon(True)
    off = sound_icon(False)
    assert on.size == off.size == (12, 12)
    assert on.getpixel((1, 1))[3] == 0

    def has_red(image):
        return any(r > 180 and g < 110 and a > 0 for r, g, b, a in image.getdata())

    assert has_red(off) is True
    assert has_red(on) is False


class _FakeLabel:
    def __init__(self):
        self.kwargs = {}
        self.packed = 0
        self.forgotten = 0

    def configure(self, **kwargs):
        self.kwargs.update(kwargs)

    def pack(self, **kwargs):
        self.packed += 1

    def pack_forget(self):
        self.forgotten += 1


def test_set_sound_swaps_icon_and_exposes_state():
    window = OverlayWindow.__new__(OverlayWindow)
    window._sound_on = False
    window.sound_icon = _FakeLabel()
    window._sound_images = {True: "on-image", False: "off-image"}
    window.set_sound(True)
    assert window.sound_on is True
    assert window.sound_icon.kwargs["image"] == "on-image"
    window.set_sound(False)
    assert window.sound_on is False
    assert window.sound_icon.kwargs["image"] == "off-image"


def test_click_through_warning_icon_shows_only_when_enabled():
    window = OverlayWindow.__new__(OverlayWindow)
    window._click_through = False
    window.click_icon = _FakeLabel()
    window.set_click_through(True)
    assert window.click_icon.packed == 1
    window.set_click_through(False)
    assert window.click_icon.forgotten == 1


def test_map_icon_highlights_in_gold():
    normal = map_icon(False)
    hot = map_icon(True)
    assert normal.size == hot.size == (12, 12)
    assert normal.getpixel((1, 1))[3] == 0

    def has_gold(image):
        return any(r > 180 and g > 140 and b < 120 and a > 0 for r, g, b, a in image.getdata())

    assert has_gold(hot) is True
    assert has_gold(normal) is False


def test_flash_map_icon_swaps_image_then_cools():
    window = OverlayWindow.__new__(OverlayWindow)
    window.root = _AfterRoot()
    window.map_icon = _FakeLabel()
    window._map_images = {False: "off-image", True: "hot-image"}
    window._map_job = None
    window.flash_map_icon(5000)
    assert window.map_icon.kwargs["image"] == "hot-image"
    assert window.root.jobs["last"][0] == 5000
    window.root.jobs["last"][1]()
    assert window.map_icon.kwargs["image"] == "off-image"


class _AfterRoot:
    def __init__(self):
        self.jobs = {}

    def after(self, ms, callback):
        self.jobs["last"] = (ms, callback)
        return "job-1"

    def after_cancel(self, job):
        self.jobs.setdefault("cancelled", []).append(job)


def test_flash_map_icon_cancels_previous_job():
    window = OverlayWindow.__new__(OverlayWindow)
    window.root = _AfterRoot()
    window.map_icon = _FakeLabel()
    window._map_images = {False: "off-image", True: "hot-image"}
    window._map_job = "old-job"
    window.flash_map_icon(5000)
    assert window.root.jobs["cancelled"] == ["old-job"]
    assert window._map_job == "job-1"


def test_cool_map_resets_job_and_image():
    window = OverlayWindow.__new__(OverlayWindow)
    window.map_icon = _FakeLabel()
    window._map_images = {False: "off-image", True: "hot-image"}
    window._map_job = "job-1"
    window._cool_map()
    assert window._map_job is None
    assert window.map_icon.kwargs["image"] == "off-image"


def test_map_click_invokes_callback_and_breaks():
    window = OverlayWindow.__new__(OverlayWindow)
    calls = []
    window._on_map_click = lambda: calls.append("click")
    assert window._map_click() == "break"
    assert calls == ["click"]
    window._on_map_click = None
    assert window._map_click() == "break"


def _has_color(image, predicate):
    return any(predicate(r, g, b, a) for r, g, b, a in image.getdata())


def test_filter_icon_turns_gold_when_active():
    active = filter_icon(True)
    normal = filter_icon(False)
    assert active.size == normal.size == (12, 12)
    gold = lambda r, g, b, a: r > 180 and g > 140 and b < 120 and a > 0  # noqa: E731
    assert _has_color(active, gold) is True
    assert _has_color(normal, gold) is False


def test_set_filter_active_swaps_icon():
    window = OverlayWindow.__new__(OverlayWindow)
    window._filter_active = False
    window.filter_icon = _FakeLabel()
    window._filter_images = {True: "active-image", False: "normal-image"}
    window.set_filter_active(True)
    assert window.filter_active is True
    assert window.filter_icon.kwargs["image"] == "active-image"


def test_position_prefers_recorded_pos_over_winfo():
    window = OverlayWindow.__new__(OverlayWindow)
    window.root = _DragRoot(x=500, y=600)
    window._pos = (10, 20)
    assert window.position == (10, 20)
    window._pos = None
    assert window.position == (500, 600)


def test_filter_click_invokes_callback_and_breaks():
    window = OverlayWindow.__new__(OverlayWindow)
    calls = []
    window._on_filter_click = lambda: calls.append("filter")
    assert window._filter_click() == "break"
    assert calls == ["filter"]


class _ResourceInner:
    def winfo_children(self):
        return []


def _resource_window():
    window = OverlayWindow.__new__(OverlayWindow)
    window.root = _DragRoot()
    window._pos = None
    window.inner = _ResourceInner()
    window._resources_hash = None
    window._images = []
    window._drawn = []
    window._add_resource_row = lambda target: window._drawn.append(target.harvestable_id)
    return window


def _target(harvestable_id=1, distance=23.0, bearing_deg=45.0):
    return GatherTarget(harvestable_id=harvestable_id, kind="Log", tier=6, enchant=2, size=3,
                        x=0.0, y=0.0, is_living=False, distance=distance,
                        bearing_deg=bearing_deg)


def test_render_resources_resizes_to_target_count():
    window = _resource_window()
    window.place_at(10, 20)
    window.render_resources([_target(1), _target(2), _target(3)])
    glow = GLOW_LAYERS * GLOW_STEP * 2
    assert window.root.geometries[-1] == f"{WIDTH}x{PAD * 2 + 3 * ROW_H + TOP_H + glow}+10+20"
    assert window._drawn == [1, 2, 3]


def test_render_resources_skips_unchanged_batch():
    window = _resource_window()
    targets = [_target(1)]
    window.render_resources(targets)
    window.render_resources(targets)
    assert window._drawn == [1]


def test_render_resources_keeps_one_row_when_empty():
    window = _resource_window()
    window.render_resources([])
    glow = GLOW_LAYERS * GLOW_STEP * 2
    assert window.root.geometries[-1] == f"{WIDTH}x{PAD * 2 + ROW_H + TOP_H + glow}+0+0"


def test_render_players_resets_resource_cache():
    window = _resource_window()
    targets = [_target(1)]
    window.render_resources(targets)
    window.render_resources(targets)
    assert window._drawn == [1]
    window.render(View(), lambda _player: None)
    window.render_resources(targets)
    assert window._drawn == [1, 1]


def test_arrow_points_tip_follows_angle():
    east = arrow_points(0)
    assert len(east) == 6
    assert east[0] > ARROW_SIZE / 2
    assert abs(east[1] - ARROW_SIZE / 2) < 0.001
    south = arrow_points(90)
    assert abs(south[0] - ARROW_SIZE / 2) < 0.001
    assert south[1] > ARROW_SIZE / 2


def test_arrow_points_stay_inside_canvas():
    for angle in list(range(0, 360, 15)) + [None, -135, 359.5]:
        assert all(math.isfinite(value) for value in arrow_points(angle))
        assert all(0 <= value <= ARROW_SIZE for value in arrow_points(angle))


def test_short_kind_falls_back_to_upper_prefix():
    window = OverlayWindow.__new__(OverlayWindow)

    class _I18n:
        def t(self, key):
            return {"gather.short.Log": "木"}.get(key, key)

    window.i18n = _I18n()
    assert window._short_kind("Log") == "木"
    assert window._short_kind("Ore") == "OR"
    assert window._short_kind("") == "--"


def test_resource_row_text_fits_content_width():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    try:
        bold = tkfont.Font(family="Segoe UI", size=8, weight="bold")
        normal = tkfont.Font(family="Segoe UI", size=8)
        small = tkfont.Font(family="Segoe UI", size=7)
        content = WIDTH - GLOW_LAYERS * GLOW_STEP * 2 - 2 * 2 - PAD * 2
        for short in ("木", "石", "LG", "RK"):
            used = (bold.measure(short) + 1 + normal.measure("T8.4")
                    + small.measure("80m") + ARROW_SIZE)
            assert used <= content, (short, used, content)
    finally:
        root.destroy()

from albion_aware.overlay import GLOW_LAYERS, GLOW_STEP, PAD, ROW_H, WIDTH, OverlayWindow, format_ip, ip_color


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
    assert window.root.geometries[-1] == f"{WIDTH}x{PAD * 2 + 6 * ROW_H + 8 + glow}+-120+300"


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

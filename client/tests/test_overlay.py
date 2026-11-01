from albion_aware.overlay import PAD, ROW_H, WIDTH, OverlayWindow, format_ip, ip_color


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
    assert window.root.geometries[-1] == f"{WIDTH}x{PAD * 2 + 6 * ROW_H + 8}+-120+300"


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

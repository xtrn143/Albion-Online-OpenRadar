from albion_aware.map_window import MapWindow, fit_scale, move_selection, next_zoom


def test_fit_scale_letterboxes_wide_image():
    assert fit_scale(720, 400, 1546, 1068) == 400 / 1068


def test_fit_scale_never_upscales():
    assert fit_scale(2000, 2000, 400, 300) == 1.0


def test_fit_scale_handles_empty_image():
    assert fit_scale(720, 400, 0, 0) == 1.0


def test_next_zoom_clamps_to_range():
    zoom = 1.0
    for _ in range(10):
        zoom = next_zoom(zoom, 1)
    assert zoom == 2.0
    for _ in range(20):
        zoom = next_zoom(zoom, -1)
    assert zoom == 0.5


def test_move_selection_stays_inside_list():
    assert move_selection(0, -1, 3) == 0
    assert move_selection(0, 1, 3) == 1
    assert move_selection(2, 1, 3) == 2
    assert move_selection(0, 1, 0) == 0


def test_escape_closes_window():
    window = MapWindow.__new__(MapWindow)
    window._closed = False

    def close():
        window._closed = True

    window.close = close
    assert window._on_escape() == "break"
    assert window._closed is True


def test_tab_completes_first_hit():
    class _Entry:
        value = ""

        def get(self):
            return self.value

        def delete(self, *_args):
            self.value = ""

        def insert(self, _index, text):
            self.value = text

        def icursor(self, *_args):
            pass

    class _Hit:
        class entry:
            name = "Hetitos-Iuaerom"

    window = MapWindow.__new__(MapWindow)
    window.entry = _Entry()
    window._hits = [_Hit]
    window._refresh = lambda text: None
    assert window._on_tab() == "break"
    assert window.entry.value == "Hetitos-Iuaerom"

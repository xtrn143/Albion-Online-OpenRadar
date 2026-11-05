from albion_aware.map_window import (
    MapWindow,
    fit_scale,
    map_image_path,
    move_selection,
    next_zoom,
)


class _Top:
    def winfo_exists(self):
        return 1

    def destroy(self):
        pass


class _Entry:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


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


def test_configure_replays_pending_status():
    window = MapWindow.__new__(MapWindow)
    window._pil = None
    window._status_text = "loading"
    calls = []
    window._status = lambda text: calls.append(text)
    window._on_configure()
    assert calls == ["loading"]


def test_configure_redraws_visible_image():
    window = MapWindow.__new__(MapWindow)
    window._pil = object()
    calls = []
    window._redraw = lambda: calls.append("redraw")
    window._on_configure()
    assert calls == ["redraw"]


def test_map_image_path_points_into_maps_dir(tmp_path):
    assert map_image_path(tmp_path, "Hetitos-Iuaerom T6.webp") == (
        tmp_path / "maps" / "Hetitos-Iuaerom T6.webp")


def test_query_ignores_unchanged_text():
    window = MapWindow.__new__(MapWindow)
    window.top = _Top()
    window.entry = _Entry("HET")
    window._last_query = None
    calls = []

    def refresh(text):
        calls.append(text)
        window._last_query = text

    window._refresh = refresh
    window._on_query()
    window._on_query()
    assert calls == ["HET"]


def test_destroy_marks_window_closed():
    window = MapWindow.__new__(MapWindow)
    window._closed = False
    window.top = _Top()
    window._on_position_changed = None
    window.destroy()
    assert window._closed is True
    assert window.is_open is False


def test_set_zone_updates_zone_and_keeps_entry_text():
    window = MapWindow.__new__(MapWindow)
    window._closed = False
    window._zone = None
    window.top = _Top()
    window.entry = _Entry("HET")
    calls = []
    window._refresh = lambda text: calls.append(text)
    window.set_zone("TNL-225")
    assert window._zone == "TNL-225"
    assert calls == ["HET"]
    window.set_zone(None)
    assert window._zone is None

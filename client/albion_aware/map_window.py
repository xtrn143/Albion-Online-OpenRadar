"""阿瓦隆查图窗：搜索、候选列表、地图缩放与拖动。"""
from __future__ import annotations

import tkinter as tk
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageTk

BG = "#141414"
BG_ALT = "#1b1b1b"
FG = "#e6e6e6"
SUB = "#9a9a9a"
GOLD = "#e8c04a"
SELECT_BG = "#2a2a2a"
ZOOM_MIN = 0.5
ZOOM_MAX = 2.0
ROW_H = 22
MAX_ROWS = 8
ICON_SIZE = 7
ICON_COLORS = {
    "GOLD": "#e8c04a", "BLUE": "#4a9be8", "GREEN": "#3fb950",
    "DUNGEON": "#b06ae0", "LOGS": "#c08a4a", "ORE": "#9aa0a6",
    "ROCK": "#7a7a7a", "COTTON": "#e6e6e6", "HIDE": "#c46a4a",
}
CACHE_LIMIT = 5
MAPS_SUBDIR = "maps"


def map_image_path(data_dir, img_file) -> Path:
    return Path(data_dir) / MAPS_SUBDIR / Path(img_file).name


def fit_scale(canvas_w, canvas_h, image_w, image_h) -> float:
    if image_w <= 0 or image_h <= 0:
        return 1.0
    return min(canvas_w / image_w, canvas_h / image_h, 1.0)


def next_zoom(zoom: float, direction: int) -> float:
    step = 1.2 if direction > 0 else 1 / 1.2
    return max(ZOOM_MIN, min(ZOOM_MAX, zoom * step))


def move_selection(index: int, delta: int, count: int) -> int:
    if count <= 0:
        return 0
    return max(0, min(count - 1, index + delta))


class MapWindow:
    def __init__(self, master, i18n, index=None, data_dir=None, history=(),
                 on_position_changed=None, on_selected=None):
        self.i18n = i18n
        self._index = index
        self._data_dir = Path(data_dir) if data_dir else None
        self._history = list(history)[:10]
        self._on_position_changed = on_position_changed
        self._on_selected = on_selected

        self._hits = []
        self._selected = 0
        self._row_frames = []
        self._images = OrderedDict()
        self._pil = None
        self._photo = None
        self._fit = 1.0
        self._zoom = 1.0
        self._offset = [0.0, 0.0]
        self._drag = None
        self._zone = None
        self._closed = True
        self._state = "loading"  # loading / ready / missing
        self._last_query = None
        self._last_canvas = (None, None)
        self._status_text = ""

        self.top = tk.Toplevel(master)
        self.top.title(i18n.t("map.title"))
        self.top.attributes("-topmost", True)
        self.top.configure(bg=BG, padx=10, pady=8)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.geometry("720x560")
        self.top.bind("<Escape>", lambda _event: self._on_escape())
        self.top.withdraw()

        bar = tk.Frame(self.top, bg=BG)
        bar.pack(fill="x")
        self.count = tk.Label(bar, text="", bg=BG, fg=SUB, font=("Segoe UI", 9))
        self.count.pack(side="right")
        tk.Button(bar, text="×", command=self.close, bg=BG, fg=SUB, bd=0,
                  activebackground=BG, activeforeground=FG,
                  font=("Segoe UI", 11)).pack(side="right", padx=(4, 0))
        self.entry = tk.Entry(bar, bg=BG_ALT, fg=FG, insertbackground=FG,
                              relief="flat", font=("Segoe UI", 12))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry.bind("<KeyRelease>", self._on_query)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Up>", lambda _event: self._move(-1))
        self.entry.bind("<Down>", lambda _event: self._move(1))
        self.entry.bind("<Tab>", self._on_tab)
        self.entry.bind("<Escape>", lambda _event: self._on_escape())

        self.rows = tk.Frame(self.top, bg=BG)
        self.rows.pack(fill="x", pady=(6, 6))

        self.canvas = tk.Canvas(self.top, bg="#0f0f0f", highlightthickness=0, height=380)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", lambda _event: self._reset_view())
        self.canvas.bind("<Configure>", self._on_configure)

        tk.Label(self.top, text=i18n.t("map.hint"), bg=BG, fg=SUB,
                 font=("Segoe UI", 8), anchor="w").pack(fill="x", pady=(4, 0))
        self._status(i18n.t("map.loading"))

    @property
    def alive(self) -> bool:
        try:
            return bool(self.top.winfo_exists())
        except tk.TclError:
            return False

    @property
    def is_open(self) -> bool:
        return not self._closed

    def place_at(self, x, y) -> None:
        self.top.geometry(f"+{int(x)}+{int(y)}")

    def set_index(self, index) -> None:
        self._index = index
        self._state = "ready" if index is not None else "missing"
        if self._closed or not self.alive:
            return
        if index is None:
            self._hits = []
            self._render_rows([])
            self.count.configure(text="")
            self._status(self.i18n.t("map.missing"))
            return
        text = self.entry.get()
        if text and self._zone and text.strip().upper() == str(self._zone).upper():
            entry = index.by_zone(self._zone)
            if entry is not None:
                text = entry.name
                self.entry.delete(0, "end")
                self.entry.insert(0, text)
        self._refresh(text)

    def open(self, current_zone=None, prefill=None) -> None:
        self._closed = False
        self._zone = current_zone
        self.top.deiconify()
        self.top.lift()
        self.top.attributes("-topmost", True)
        text = prefill or ""
        if not text and current_zone and self._index is not None:
            entry = self._index.by_zone(current_zone)
            text = entry.name if entry else current_zone
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self._zoom = 1.0
        self._offset = [0.0, 0.0]
        self._refresh(text)
        self.entry.focus_force()
        self.entry.select_range(0, "end")
        self.entry.icursor("end")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._save_position()
        try:
            self.top.withdraw()
        except tk.TclError:
            pass

    def destroy(self) -> None:
        self._closed = True
        try:
            self.top.destroy()
        except tk.TclError:
            pass

    # ---------- 搜索与候选 ----------
    def _on_query(self, _event=None) -> None:
        if not self.alive:
            return
        text = self.entry.get()
        if text == self._last_query:
            return
        self._refresh(text)

    def _refresh(self, text: str) -> None:
        if not self.alive:
            return
        self._last_query = text
        if self._index is None:
            self._hits = []
            self._render_rows([])
            self.count.configure(text="")
            self._status(self.i18n.t("map.loading") if self._state == "loading"
                         else self.i18n.t("map.missing"))
            return
        self._hits = self._index.query(text, current_zone=self._zone,
                                       history=self._history, limit=MAX_ROWS)
        self._selected = 0
        self._render_rows(self._hits)
        self.count.configure(text=self.i18n.t("map.count", count=len(self._hits))
                             if text.strip() else "")
        # 只有唯一命中才自动出图；多候选时保持列表，避免边打字边闪图
        if len(self._hits) == 1:
            self._select(self._hits[0].entry, remember=False)
        elif not self._hits:
            self._pil = None
            self._status(self.i18n.t("map.no_result") if text.strip() else "")
        else:
            self._pil = None
            self._status("")

    def _make_row(self) -> dict:
        row = tk.Frame(self.rows, bg=BG, height=ROW_H)
        row.pack_propagate(False)
        name = tk.Label(row, bg=BG, fg=FG, anchor="w", font=("Segoe UI", 9))
        name.pack(side="left")
        tier = tk.Label(row, bg=BG, fg=SUB, font=("Segoe UI", 8))
        tier.pack(side="left", padx=(6, 0))
        current = tk.Label(row, bg=BG, fg=GOLD, font=("Segoe UI", 8))
        current.pack(side="left", padx=(4, 0))
        dots = [tk.Frame(row, width=ICON_SIZE, height=ICON_SIZE) for _ in range(6)]
        for widget in (row, name, tier, current):
            widget.bind("<Button-1>", lambda _event, frame=row: self._on_row_click(frame))
        return {"row": row, "name": name, "tier": tier, "current": current, "dots": dots}

    def _on_row_click(self, frame) -> None:
        for position, widgets in enumerate(self._row_frames):
            if widgets["row"] is frame:
                if position < len(self._hits):
                    self._select(self._hits[position].entry)
                return

    def _render_rows(self, hits) -> None:
        while len(self._row_frames) < len(hits):
            self._row_frames.append(self._make_row())
        for position, widgets in enumerate(self._row_frames):
            row = widgets["row"]
            if position >= len(hits):
                row.pack_forget()
                continue
            hit = hits[position]
            row.pack(fill="x")
            row.configure(bg=BG)
            widgets["name"].configure(
                text=hit.entry.name,
                font=("Segoe UI", 9, "bold" if hit.is_current else "normal"))
            widgets["tier"].configure(
                text=self.i18n.t("map.tier", tier=hit.entry.tier) if hit.entry.tier else "")
            widgets["current"].configure(
                text=self.i18n.t("map.current") if hit.is_current else "")
            for dot in widgets["dots"]:
                dot.pack_forget()
            for dot, (alt, _badge) in zip(widgets["dots"], hit.entry.icons[:6]):
                dot.configure(bg=ICON_COLORS.get(alt, SUB))
                dot.pack(side="left", padx=(2, 0), pady=7)
        self._highlight(0)

    def _highlight(self, index: int) -> None:
        for position, widgets in enumerate(self._row_frames):
            color = SELECT_BG if position == index and position < len(self._hits) else BG
            widgets["row"].configure(bg=color)
            for key in ("name", "tier", "current"):
                widgets[key].configure(bg=color)

    def _move(self, delta: int) -> str:
        if not self._hits:
            return "break"
        self._selected = move_selection(self._selected, delta, len(self._hits))
        self._highlight(self._selected)
        self._select(self._hits[self._selected].entry, remember=False)
        return "break"

    def _on_enter(self, _event=None) -> str:
        if self._hits:
            self._select(self._hits[self._selected].entry)
            self.canvas.focus_set()
        return "break"

    def _on_tab(self, _event=None) -> str:
        if self._hits:
            self.entry.delete(0, "end")
            self.entry.insert(0, self._hits[0].entry.name)
            self.entry.icursor("end")
            self._refresh(self.entry.get())
        return "break"

    def _on_escape(self) -> str:
        self.close()
        return "break"

    # ---------- 地图显示 ----------
    def _select(self, entry, remember=True) -> None:
        image = self._image(entry)
        self._zoom = 1.0
        self._offset = [0.0, 0.0]
        if image is None:
            self._pil = None
            self._status(self.i18n.t("map.no_image"))
        else:
            self._pil = image
            self._status_text = ""
            self._redraw()
        if remember:
            self._history = ([entry.name]
                             + [name for name in self._history if name != entry.name])[:10]
            if self._on_selected is not None:
                self._on_selected(entry.name)

    def _image(self, entry):
        if self._data_dir is None or not entry.img_file:
            return None
        key = entry.img_file
        if key in self._images:
            self._images.move_to_end(key)
            return self._images[key]
        try:
            image = Image.open(map_image_path(self._data_dir, key))
            image.load()
        except (OSError, ValueError):
            return None
        self._images[key] = image
        while len(self._images) > CACHE_LIMIT:
            self._images.popitem(last=False)
        return image

    def _canvas_size(self):
        return max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)

    def _redraw(self) -> None:
        if not self.alive:
            return
        self.canvas.delete("all")
        self._photo = None
        if self._pil is None:
            return
        self._status_text = ""
        width, height = self._canvas_size()
        self._fit = fit_scale(width, height, self._pil.width, self._pil.height)
        scale = self._fit * self._zoom
        size = (max(int(self._pil.width * scale), 1), max(int(self._pil.height * scale), 1))
        image = self._pil.resize(size, Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(image, master=self.top)
        self.canvas.create_image(width / 2 + self._offset[0],
                                 height / 2 + self._offset[1],
                                 image=self._photo, anchor="center", tags="map")

    def _place(self) -> None:
        if self._pil is None:
            return
        width, height = self._canvas_size()
        self.canvas.coords("map", width / 2 + self._offset[0],
                           height / 2 + self._offset[1])

    def _on_configure(self, event=None) -> None:
        """窗口首次映射后 canvas 才有真实尺寸，此时补画一次。"""
        size = (getattr(event, "width", None), getattr(event, "height", None))
        if size != (None, None):
            if size == self._last_canvas:
                return
            self._last_canvas = size
        if self._pil is not None:
            self._redraw()
        elif getattr(self, "_status_text", ""):
            self._status(self._status_text)

    def _status(self, text: str) -> None:
        self._status_text = text
        self.canvas.delete("all")
        self._photo = None
        if text:
            width, _height = self._canvas_size()
            self.canvas.create_text(width / 2, 120, text=text, fill=SUB,
                                    font=("Segoe UI", 10), tags="status")

    def _on_wheel(self, event) -> str:
        if self._pil is None:
            return "break"
        previous = self._zoom
        self._zoom = next_zoom(previous, 1 if getattr(event, "delta", 0) > 0 else -1)
        if self._zoom == previous:
            return "break"
        width, height = self._canvas_size()
        old_scale = self._fit * previous
        new_scale = self._fit * self._zoom
        if old_scale <= 0:
            return "break"
        left = width / 2 - self._pil.width * old_scale / 2 + self._offset[0]
        top = height / 2 - self._pil.height * old_scale / 2 + self._offset[1]
        image_x = (event.x - left) / old_scale
        image_y = (event.y - top) / old_scale
        self._offset[0] = (event.x - image_x * new_scale
                           - (width / 2 - self._pil.width * new_scale / 2))
        self._offset[1] = (event.y - image_y * new_scale
                           - (height / 2 - self._pil.height * new_scale / 2))
        self._redraw()
        return "break"

    def _on_press(self, event) -> None:
        self._drag = (event.x, event.y, self._offset[0], self._offset[1])

    def _on_drag(self, event) -> None:
        if self._drag is None:
            return
        start_x, start_y, offset_x, offset_y = self._drag
        self._offset[0] = offset_x + event.x - start_x
        self._offset[1] = offset_y + event.y - start_y
        self._place()

    def _on_release(self, _event=None) -> None:
        self._drag = None

    def _reset_view(self) -> None:
        self._drag = None
        self._zoom = 1.0
        self._offset = [0.0, 0.0]
        self._redraw()

    def _save_position(self) -> None:
        if self._on_position_changed is None:
            return
        try:
            self._on_position_changed(self.top.winfo_x(), self.top.winfo_y())
        except tk.TclError:
            pass

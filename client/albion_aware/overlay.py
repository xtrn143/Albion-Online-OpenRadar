"""窄条置顶主窗：武器图标 + IP，行点击、闪烁、拖动、穿透。"""
import tkinter as tk

import albion_aware.win32_ext as win32

WIDTH = 78
ROW_H = 36
ICON_SIZE = 32
PAD = 4
BORDER = 2
BG = "#141414"
FLASH_ON = "#ff3b30"
FLASH_STEPS = 10
FLASH_INTERVAL_MS = 200
DRAG_MODIFIER = 0x0004  # Ctrl

IP_GREY = "#d6d6d6"
IP_YELLOW = "#e8c04a"
IP_ORANGE = "#ff7a45"
STATUS_ON = "#3fb950"
STATUS_OFF = "#6b6b6b"


def ip_color(item_power: int | None) -> str:
    if item_power is None:
        return IP_GREY
    if item_power > 1000:
        return IP_ORANGE
    if item_power >= 800:
        return IP_YELLOW
    return IP_GREY


def format_ip(item_power: int | None) -> str:
    return "-" if item_power is None else str(int(item_power))


class OverlayWindow:
    def __init__(self, i18n, icon_loader, on_row_click, on_more_click, on_drag_end):
        self.i18n = i18n
        self._icon_loader = icon_loader          # (Player) -> ImageTk.PhotoImage | None
        self._on_row_click = on_row_click
        self._on_more_click = on_more_click
        self._on_drag_end = on_drag_end

        self.root = tk.Tk()
        self.root.title(i18n.t("app.title"))
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)

        self.border = tk.Frame(self.root, bg=BG, padx=BORDER, pady=BORDER)
        self.border.pack(fill="both", expand=True)
        self.status = tk.Label(self.border, text="●", bg=BG, fg=STATUS_OFF,
                               font=("Segoe UI", 5), anchor="e")
        self.status.pack(fill="x")
        self.inner = tk.Frame(self.border, bg=BG)
        self.inner.pack(fill="both", expand=True)

        for widget in (self.border, self.inner):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)

        self._pos = None
        self._drag_origin = None
        self._flash_job = None
        self._flash_step = 0
        self._images = []
        self._click_through = False

        self.root.update_idletasks()
        self._apply_styles()

    # ---------- 位置与尺寸 ----------
    def place_at(self, x: int, y: int) -> None:
        self._pos = (int(x), int(y))
        self.root.geometry(f"+{int(x)}+{int(y)}")

    def reset_position(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.place_at(screen_w - WIDTH - 8, int(screen_h / 3))
        self._on_drag_end(*self._pos)

    def _resize(self, row_count: int) -> None:
        height = PAD * 2 + max(row_count, 1) * ROW_H + 8  # +8 为顶部状态点
        if self._pos is not None:
            x, y = self._pos
        else:
            x, y = self.root.winfo_x(), self.root.winfo_y()
        self.root.geometry(f"{WIDTH}x{height}+{x}+{y}")

    # ---------- 渲染 ----------
    def render(self, view, ip_getter) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        self._images.clear()

        for player in view.rows:
            self._add_row(player, ip_getter)

        if view.hidden:
            more = tk.Label(self.inner, text=self.i18n.t("overlay.more", count=view.hidden),
                            bg=BG, fg=IP_GREY, font=("Segoe UI", 8), anchor="center")
            more.pack(fill="x", pady=(1, 1))
            more.bind("<Button-1>", lambda _event: self._on_more_click())

        self._resize(len(view.rows) + (1 if view.hidden else 0))

    def _add_row(self, player, ip_getter) -> None:
        row = tk.Frame(self.inner, bg=BG, height=ROW_H)
        row.pack(fill="x", padx=PAD)
        row.pack_propagate(False)

        photo = self._icon_loader(player)
        if photo is not None:
            self._images.append(photo)
            icon_label = tk.Label(row, bg=BG, image=photo)
        else:
            icon_label = tk.Label(row, bg=BG, text="?", fg=IP_GREY, font=("Segoe UI", 9))
        icon_label.pack(side="left")

        power = ip_getter(player)
        text_label = tk.Label(row, bg=BG, text=format_ip(power), fg=ip_color(power),
                              font=("Segoe UI", 9, "bold"), anchor="e")
        text_label.pack(side="right", fill="x", expand=True)

        for widget in (row, icon_label, text_label):
            widget.bind("<Button-1>", lambda _event, p=player: self._on_row_click(p))

    def clear(self) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        self._images.clear()
        self._resize(1)

    # ---------- 闪烁 ----------
    def flash(self) -> None:
        if self._flash_job is not None:
            self.root.after_cancel(self._flash_job)
        self._flash_step = 0
        self._flash_tick()

    def _flash_tick(self) -> None:
        if self._flash_step >= FLASH_STEPS:
            self.border.configure(bg=BG)
            self._flash_job = None
            return
        self.border.configure(bg=FLASH_ON if self._flash_step % 2 == 0 else BG)
        self._flash_step += 1
        self._flash_job = self.root.after(FLASH_INTERVAL_MS, self._flash_tick)

    # ---------- 系统行为 ----------
    def _apply_styles(self) -> None:
        try:
            win32.make_noactivate(int(self.root.wm_frame(), 16))
        except Exception:
            pass

    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        try:
            win32.set_click_through(int(self.root.wm_frame(), 16), enabled)
        except Exception:
            pass

    @property
    def click_through(self) -> bool:
        return self._click_through

    def set_status(self, connected: bool) -> None:
        self.status.configure(fg=STATUS_ON if connected else STATUS_OFF)

    def toggle_visible(self) -> bool:
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            return True
        self.root.withdraw()
        return False

    def close(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        self.root.mainloop()

    # ---------- 拖动 ----------
    def _start_drag(self, event) -> None:
        if not (event.state & DRAG_MODIFIER):
            return
        self._drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event) -> None:
        if self._drag_origin is None:
            return
        offset_x, offset_y = self._drag_origin
        x, y = event.x_root - offset_x, event.y_root - offset_y
        self._pos = (int(x), int(y))
        self.root.geometry(f"+{x}+{y}")

    def _end_drag(self, _event) -> None:
        if self._drag_origin is None:
            return
        self._drag_origin = None
        self._on_drag_end(self.root.winfo_x(), self.root.winfo_y())

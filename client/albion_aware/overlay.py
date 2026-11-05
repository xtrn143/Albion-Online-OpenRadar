"""窄条置顶主窗：武器图标 + IP，行点击、闪烁、拖动、穿透。"""
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

import albion_aware.win32_ext as win32

WIDTH = 102             # 78 内容宽 + 6 层红光内外边距（每层左右各 2px）
ROW_H = 36
TOP_H = 16               # 顶部图标行（提示音 / 穿透 / 连接状态）
ICON_SIZE = 32
PAD = 4
BORDER = 2
GLOW_LAYERS = 6          # 由外向内递减的红光层数
GLOW_STEP = 2
BG = "#141414"
GLOW_LIT = ("#ff4b3e", "#e0331f", "#b52616", "#83200f", "#4e170b", "#261210")
GLOW_DIM = ("#1a0f0d", "#18100e", "#17100f", "#161010", "#151212", "#141414")
FLASH_STEPS = 6
FLASH_INTERVAL_MS = 150
ALERT_HOLD_MS = 5000     # 闪完后保持红光的时间
DRAG_THRESHOLD = 4      # 位移小于该像素仍视为点击

IP_GREY = "#d6d6d6"
IP_YELLOW = "#e8c04a"
IP_ORANGE = "#ff7a45"
STATUS_ON = "#3fb950"
STATUS_OFF = "#6b6b6b"
SOUND_ON = (230, 230, 230, 255)
SOUND_OFF = (107, 107, 107, 255)
SOUND_SLASH = (255, 75, 62, 255)
CLICK_WARN = "#e8c04a"


def sound_icon(on: bool) -> Image.Image:
    """12px 扬声器图标：开启时亮色+声波，关闭时灰色+红色斜杠。"""
    image = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = SOUND_ON if on else SOUND_OFF
    draw.polygon([(1, 4), (4, 4), (8, 1), (8, 10), (4, 7), (1, 7)], fill=color)
    if on:
        draw.line((9, 4, 11, 6), fill=color, width=1)
        draw.line((11, 6, 9, 8), fill=color, width=1)
    else:
        draw.line((2, 2, 10, 10), fill=SOUND_SLASH, width=2)
    return image


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
    def __init__(self, i18n, icon_loader, on_row_click, on_more_click, on_drag_end,
                 on_sound_click=None):
        self.i18n = i18n
        self._icon_loader = icon_loader          # (Player) -> ImageTk.PhotoImage | None
        self._on_row_click = on_row_click
        self._on_more_click = on_more_click
        self._on_drag_end = on_drag_end
        self._on_sound_click = on_sound_click

        self.root = tk.Tk()
        self.root.title(i18n.t("app.title"))
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)

        self._glow = []
        parent = self.root
        for _ in range(GLOW_LAYERS):
            layer = tk.Frame(parent, bg=BG, padx=GLOW_STEP, pady=GLOW_STEP)
            layer.pack(fill="both", expand=True)
            self._glow.append(layer)
            parent = layer

        self.border = tk.Frame(parent, bg=BG, padx=BORDER, pady=BORDER)
        self.border.pack(fill="both", expand=True)

        self.top_row = tk.Frame(self.border, bg=BG, height=TOP_H)
        self.top_row.pack(fill="x")
        self.top_row.pack_propagate(False)

        self._sound_images = {state: ImageTk.PhotoImage(sound_icon(state), master=self.root)
                              for state in (True, False)}
        self._sound_on = False
        self.sound_icon = tk.Label(self.top_row, bg=BG, bd=0,
                                   image=self._sound_images[False])
        self.sound_icon.pack(side="left", padx=(1, 0))
        self.sound_icon.bind("<Button-1>", self._toggle_sound_click)

        self.click_icon = tk.Label(self.top_row, text="!", bg=BG, fg=CLICK_WARN,
                                   font=("Segoe UI", 7, "bold"), bd=0)

        self.status = tk.Label(self.top_row, text="●", bg=BG, fg=STATUS_OFF,
                               font=("Segoe UI", 6), anchor="e", bd=0)
        self.status.pack(side="right", padx=(0, 1))

        self.inner = tk.Frame(self.border, bg=BG)
        self.inner.pack(fill="both", expand=True)

        for widget in (*self._glow, self.border, self.inner, self.top_row, self.click_icon,
                       self.status):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)

        self._pos = None
        self._press_origin = None
        self._dragging = False
        self._flash_job = None
        self._flash_step = 0
        self._images = []
        self._click_through = False
        self._opacity = 1.0
        self._paint_glow(GLOW_DIM)

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
        glow = GLOW_LAYERS * GLOW_STEP * 2
        height = PAD * 2 + max(row_count, 1) * ROW_H + TOP_H + glow  # 顶部图标行
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
            widget.bind("<ButtonPress-1>", lambda event, p=player: self._start_drag(event, p))
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", lambda event, p=player: self._end_drag(event, p))

    def clear(self) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        self._images.clear()
        self._resize(1)

    # ---------- 闪烁 ----------
    def _paint_glow(self, colors) -> None:
        for layer, color in zip(self._glow, colors):
            layer.configure(bg=color)
        self.border.configure(bg=colors[-1])

    def flash(self) -> None:
        if self._flash_job is not None:
            self.root.after_cancel(self._flash_job)
        self._flash_step = 0
        self._flash_tick()

    def _flash_tick(self) -> None:
        if self._flash_step >= FLASH_STEPS:
            self._flash_job = self.root.after(ALERT_HOLD_MS, self._glow_dim)
            return
        lit = self._flash_step % 2 == 0
        self._paint_glow(GLOW_LIT if lit else GLOW_DIM)
        self._flash_step += 1
        self._flash_job = self.root.after(FLASH_INTERVAL_MS, self._flash_tick)

    def _glow_dim(self) -> None:
        self._paint_glow(GLOW_DIM)
        self._flash_job = None
        self._flash_step = 0

    # ---------- 系统行为 ----------
    def _apply_styles(self) -> None:
        try:
            win32.make_noactivate(int(self.root.wm_frame(), 16))
        except Exception:
            pass

    def set_click_through(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled and not self._click_through:
            self.click_icon.pack(side="left", padx=(2, 0))
        elif not enabled and self._click_through:
            self.click_icon.pack_forget()
        self._click_through = enabled
        try:
            win32.set_click_through(int(self.root.wm_frame(), 16), enabled)
        except Exception:
            pass

    @property
    def click_through(self) -> bool:
        return self._click_through

    def set_sound(self, enabled: bool) -> None:
        self._sound_on = bool(enabled)
        self.sound_icon.configure(image=self._sound_images[self._sound_on])

    @property
    def sound_on(self) -> bool:
        return self._sound_on

    def _toggle_sound_click(self, _event=None):
        if self._on_sound_click is not None:
            self._on_sound_click()
        return "break"

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

    # ---------- 透明度 ----------
    def set_opacity(self, value: float) -> None:
        self._opacity = float(value)
        try:
            self.root.attributes("-alpha", self._opacity)
        except tk.TclError:
            pass

    # ---------- 拖动 ----------
    # 按住左键移动即拖动；按下后几乎没动就松开视为点击某一行
    def _start_drag(self, event, player=None) -> None:
        self._press_origin = (event.x_root, event.y_root,
                              self.root.winfo_x(), self.root.winfo_y(), player)
        self._dragging = False

    def _drag(self, event) -> None:
        if self._press_origin is None:
            return
        start_x, start_y, win_x, win_y, _player = self._press_origin
        dx, dy = event.x_root - start_x, event.y_root - start_y
        if not self._dragging:
            if abs(dx) + abs(dy) < DRAG_THRESHOLD:
                return
            self._dragging = True
        self._pos = (win_x + dx, win_y + dy)
        self.root.geometry(f"+{win_x + dx}+{win_y + dy}")

    def _end_drag(self, _event, player=None) -> None:
        if self._press_origin is None:
            return
        self._press_origin = None
        if self._dragging:
            self._dragging = False
            if self._pos is not None:
                self._on_drag_end(*self._pos)
        elif player is not None:
            self._on_row_click(player)

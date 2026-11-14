"""悬浮条左侧的采集面板：目标列表 + 距离 + 方向箭头。"""
import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from albion_aware.gather_targets import (KIND_ORDER, format_distance,
                                         format_tier_enchant, targets_hash)

PANEL_WIDTH = 184
ROW_H = 22
GAP = 8
BG = "#141414"
FG = "#e6e6e6"
MUTED = "#9a9a9a"
ARROW = "#e6e6e6"
KIND_COLORS = {
    "Log": (150, 105, 60),
    "Rock": (150, 150, 160),
    "Fiber": (95, 190, 120),
    "Hide": (170, 120, 90),
    "Ore": (100, 150, 200),
}


def kind_badge_image(kind: str, size: int = 10) -> Image.Image:
    color = KIND_COLORS.get(kind, (120, 120, 120))
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=2, fill=(*color, 255))
    return image


def arrow_points(angle_deg: float | None, size: int = 12) -> list[float]:
    """按屏幕空间角度生成箭头三角形顶点（Canvas 的 y 轴向下）。"""
    if angle_deg is None or not math.isfinite(angle_deg):
        angle_deg = 0.0
    rad = math.radians(angle_deg)
    center = size / 2
    length = size / 2 - 1
    tip = (center + length * math.cos(rad), center + length * math.sin(rad))
    back = (center - length * 0.6 * math.cos(rad), center - length * 0.6 * math.sin(rad))
    wing = length * 0.55
    wing_rad = rad + math.pi / 2
    left = (back[0] + wing * math.cos(wing_rad), back[1] + wing * math.sin(wing_rad))
    right = (back[0] - wing * math.cos(wing_rad), back[1] - wing * math.sin(wing_rad))
    return [tip[0], tip[1], left[0], left[1], right[0], right[1]]


def panel_origin(overlay_x: int, overlay_y: int, screen_width: int,
                 width: int = PANEL_WIDTH, gap: int = GAP,
                 overlay_width: int = 102) -> tuple[int, int]:
    """默认放在悬浮条左侧；贴屏幕左边时翻到右侧，并限制在屏幕内。"""
    x = int(overlay_x) - width - gap
    if x < 0:
        x = int(overlay_x) + overlay_width + gap
    x = max(0, min(x, max(0, int(screen_width) - width)))
    return (x, int(overlay_y))


class GatheringPanel:
    """采集模式下的目标小窗；不在采集模式时保持隐藏。"""

    def __init__(self, master, i18n):
        self.i18n = i18n
        self.top = tk.Toplevel(master)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(bg=BG)
        self.top.withdraw()

        self.body = tk.Frame(self.top, bg=BG, padx=8, pady=6)
        self.body.pack(fill="both", expand=True)

        self._badges = {kind: ImageTk.PhotoImage(kind_badge_image(kind), master=self.top)
                        for kind in KIND_ORDER}
        self._hash = None
        self._height = 0
        self._visible = False
        self._anchor = (0, 0)

    # ---------- 生命周期 ----------
    @property
    def is_open(self) -> bool:
        return self._visible

    def attach(self, overlay_x: int, overlay_y: int) -> None:
        self._anchor = (int(overlay_x), int(overlay_y))
        if self._visible:
            self._reposition()

    def show(self) -> None:
        self._visible = True
        self._reposition()
        try:
            self.top.deiconify()
        except tk.TclError:
            pass

    def hide(self) -> None:
        self._visible = False
        try:
            self.top.withdraw()
        except tk.TclError:
            pass

    def destroy(self) -> None:
        try:
            self.top.destroy()
        except tk.TclError:
            pass

    def set_i18n(self, i18n) -> None:
        self.i18n = i18n
        self._hash = None

    # ---------- 渲染 ----------
    def update(self, targets, status: str = "") -> None:
        key = targets_hash(targets, status)
        if key == self._hash:
            return
        self._hash = key
        self._render(targets, status)

    def _render(self, targets, status: str) -> None:
        for child in self.body.winfo_children():
            child.destroy()

        header = tk.Frame(self.body, bg=BG)
        header.pack(fill="x")
        tk.Label(header, text=self.i18n.t("gather.title"), bg=BG, fg=FG,
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(side="left")
        tk.Label(header, text=str(len(targets)), bg=BG, fg=MUTED,
                 font=("Segoe UI", 8), anchor="e").pack(side="right")

        if status:
            tk.Label(self.body, text=status, bg=BG, fg=MUTED, font=("Segoe UI", 8),
                     anchor="w", wraplength=PANEL_WIDTH - 16, justify="left").pack(
                         fill="x", pady=(2, 0))
        elif not targets:
            tk.Label(self.body, text=self.i18n.t("gather.empty"), bg=BG, fg=MUTED,
                     font=("Segoe UI", 8), anchor="w").pack(fill="x", pady=(2, 0))

        for target in targets:
            self._add_row(target)

        self.top.update_idletasks()
        self._height = self.body.winfo_reqheight()
        self._reposition()

    def _add_row(self, target) -> None:
        row = tk.Frame(self.body, bg=BG, height=ROW_H)
        row.pack(fill="x")
        row.pack_propagate(False)

        badge = self._badges.get(target.kind)
        if badge is not None:
            tk.Label(row, bg=BG, image=badge, bd=0).pack(side="left", padx=(0, 4))

        label = format_tier_enchant(target.tier, target.enchant)
        if target.kind:
            label += " " + self.i18n.t("gather.kind." + target.kind)
        tk.Label(row, text=label, bg=BG, fg=FG, font=("Segoe UI", 8),
                 anchor="w").pack(side="left")

        tk.Label(row, text=format_distance(target.distance), bg=BG, fg=MUTED,
                 font=("Segoe UI", 8), anchor="e").pack(side="right")

        canvas = tk.Canvas(row, width=12, height=12, bg=BG, bd=0,
                           highlightthickness=0)
        canvas.pack(side="right", padx=(2, 4))
        if target.bearing_deg is None:
            canvas.create_oval(4, 4, 8, 8, outline=MUTED, fill="")
        else:
            canvas.create_polygon(arrow_points(target.bearing_deg), fill=ARROW, outline="")

    def _reposition(self) -> None:
        x, y = panel_origin(self._anchor[0], self._anchor[1],
                            self.top.winfo_screenwidth())
        height = self._height or self.top.winfo_reqheight()
        try:
            self.top.geometry(f"{PANEL_WIDTH}x{height}+{x}+{y}")
        except tk.TclError:
            pass

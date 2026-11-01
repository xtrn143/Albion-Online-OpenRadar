# client/albion_aware/detail_panel.py
"""点行后展开的详情面板：名字、公会、装备格、药水/食物、操作按钮。"""
import time
import tkinter as tk

from albion_aware.icons import EQUIP_SLOTS
from albion_aware.overlay import format_ip

PANEL_WIDTH = 220
BG = "#1b1b1b"
FG = "#e6e6e6"
MUTED = "#9a9a9a"


def equipment_entries(player, db) -> list[tuple[str, int, str]]:
    entries: list[tuple[str, int, str]] = []
    for slot, index in EQUIP_SLOTS.items():
        if index >= len(player.equip):
            continue
        item_id = int(player.equip[index] or 0)
        if item_id <= 0:
            continue
        name = db.display_name(item_id)
        if name:
            entries.append((slot, item_id, name))
    return entries


def time_ago(now: float, timestamp: float) -> str:
    if not timestamp:
        return "-"
    seconds = max(0, int(now - timestamp))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h"


class DetailPanel:
    def __init__(self, master, i18n, icon_loader, on_mark_party, on_copy_name):
        self.i18n = i18n
        self._icon_loader = icon_loader        # (item_id) -> ImageTk.PhotoImage | None
        self._on_mark_party = on_mark_party
        self._on_copy_name = on_copy_name
        self.current = None
        self._images = []

        self.top = tk.Toplevel(master)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(bg=BG)
        self.top.withdraw()
        self.body = tk.Frame(self.top, bg=BG, padx=10, pady=8, width=PANEL_WIDTH)
        self.body.pack(fill="both", expand=True)

    def show(self, player, item_power, is_party: bool, entries, x: int, y: int) -> None:
        self.current = player
        for child in self.body.winfo_children():
            child.destroy()
        self._images.clear()

        tk.Label(self.body, text=player.nickname or f"#{player.id}", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        tk.Label(self.body,
                 text=f"{self.i18n.t('detail.guild')}: {player.guild or '-'}   "
                      f"{self.i18n.t('detail.alliance')}: {player.alliance or '-'}",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x")
        tk.Label(self.body, text=f"{self.i18n.t('detail.item_power')}: {format_ip(item_power)}",
                 bg=BG, fg=FG, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(2, 0))
        now = time.time()
        tk.Label(self.body,
                 text=f"{self.i18n.t('detail.first_seen')}: {time_ago(now, player.first_seen)}   "
                      f"{self.i18n.t('detail.last_seen')}: {time_ago(now, player.last_seen)}",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x")

        grid = tk.Frame(self.body, bg=BG)
        grid.pack(fill="x", pady=(6, 4))
        for position, (_slot, item_id, name) in enumerate(entries):
            photo = self._icon_loader(item_id)
            if photo is not None:
                self._images.append(photo)
                cell = tk.Label(grid, bg=BG, image=photo)
            else:
                cell = tk.Label(grid, bg=BG, text="-", fg=MUTED, font=("Segoe UI", 8))
            cell.grid(row=position // 4, column=position % 4, padx=2, pady=2)
            cell.bind("<Enter>", lambda _event, w=cell, t=name: self._tooltip(w, t))

        buttons = tk.Frame(self.body, bg=BG)
        buttons.pack(fill="x", pady=(4, 0))
        mark_text = self.i18n.t("detail.unmark_party" if is_party else "detail.mark_party")
        tk.Button(buttons, text=mark_text, command=self._mark).pack(side="left")
        tk.Button(buttons, text=self.i18n.t("detail.copy_name"), command=self._copy).pack(side="left", padx=4)

        self.top.update_idletasks()
        height = self.body.winfo_reqheight()
        self.top.geometry(f"{PANEL_WIDTH}x{height}+{int(x)}+{int(y)}")
        self.top.deiconify()

    def hide(self) -> None:
        self.current = None
        self.top.withdraw()

    def _mark(self) -> None:
        if self.current is not None:
            self._on_mark_party(self.current)

    def _copy(self) -> None:
        if self.current is None:
            return
        self.top.clipboard_clear()
        self.top.clipboard_append(self.current.nickname)
        self._on_copy_name(self.current)

    def _tooltip(self, widget, text: str) -> None:
        tip = tk.Toplevel(widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tk.Label(tip, text=text, bg="#000000", fg="#ffffff",
                 font=("Segoe UI", 8), padx=4, pady=2).pack()
        tip.geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() - 22}")
        widget.bind("<Leave>", lambda _event: tip.destroy(), add="+")

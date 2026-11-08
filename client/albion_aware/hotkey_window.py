# client/albion_aware/hotkey_window.py
"""热键设置窗口：逐个编辑动作的全局热键，保存前校验格式与重复。"""
import tkinter as tk

from albion_aware.config import DEFAULT_CONFIG
from albion_aware.win32_ext import parse_hotkey

HOTKEY_ACTIONS = (
    "toggle_sound",
    "map_lookup",
    "toggle_visible",
    "mark_party",
    "toggle_click_through",
)


def validate_bindings(values: dict[str, str]) -> tuple[str, str] | None:
    """校验一组热键，返回 (错误类型, 出错的键值)；全部合法返回 None。"""
    seen = set()
    for action in HOTKEY_ACTIONS:
        text = str(values.get(action, "")).strip()
        try:
            parsed = parse_hotkey(text)
        except ValueError:
            return ("invalid", text or "-")
        if parsed in seen:
            return ("duplicate", text)
        seen.add(parsed)
    return None


class HotkeyWindow:
    """托盘菜单打开的快捷键设置框。"""

    def __init__(self, master, i18n, values: dict[str, str], on_save):
        self.i18n = i18n
        self._on_save = on_save
        self.closed = False

        self.top = tk.Toplevel(master)
        self.top.title(i18n.t("hotkeys.title"))
        self.top.attributes("-topmost", True)
        self.top.configure(bg="#1b1b1b", padx=14, pady=12)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.geometry("+%d+%d" % (master.winfo_screenwidth() // 2 - 190,
                                      master.winfo_screenheight() // 2 - 170))

        self.entries: dict[str, tk.Entry] = {}
        for action in HOTKEY_ACTIONS:
            row = tk.Frame(self.top, bg="#1b1b1b")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=i18n.t("hotkeys.action." + action), width=18, anchor="w",
                     bg="#1b1b1b", fg="#e6e6e6", font=("Segoe UI", 9)).pack(side="left")
            entry = tk.Entry(row, width=12)
            entry.insert(0, str(values.get(action) or DEFAULT_CONFIG["hotkeys"][action]))
            entry.pack(side="right")
            self.entries[action] = entry

        tk.Label(self.top, text=i18n.t("hotkeys.hint"), bg="#1b1b1b", fg="#9a9a9a",
                 font=("Segoe UI", 8), wraplength=380, justify="left").pack(
                     anchor="w", pady=(8, 2))

        self._error = tk.StringVar(value="")
        tk.Label(self.top, textvariable=self._error, bg="#1b1b1b", fg="#ff6b6b",
                 font=("Segoe UI", 9), wraplength=380, justify="left").pack(anchor="w")

        buttons = tk.Frame(self.top, bg="#1b1b1b")
        buttons.pack(fill="x", pady=(8, 0))
        tk.Button(buttons, text=i18n.t("hotkeys.reset"), command=self._reset).pack(side="left")
        tk.Button(buttons, text=i18n.t("hotkeys.cancel"), command=self.close).pack(side="right")
        tk.Button(buttons, text=i18n.t("hotkeys.save"), command=self._save).pack(side="right")

    def _values(self) -> dict[str, str]:
        return {action: entry.get().strip() for action, entry in self.entries.items()}

    def _save(self) -> None:
        values = self._values()
        problem = validate_bindings(values)
        if problem:
            kind, key = problem
            self._error.set(self.i18n.t(f"hotkeys.{kind}", key=key))
            return
        self._on_save(values)
        self.close()

    def _reset(self) -> None:
        for action, entry in self.entries.items():
            entry.delete(0, "end")
            entry.insert(0, DEFAULT_CONFIG["hotkeys"][action])
        self._error.set("")

    def close(self) -> None:
        self.closed = True
        try:
            self.top.destroy()
        except tk.TclError:
            pass

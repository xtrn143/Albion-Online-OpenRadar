"""采集筛选设置窗：资源种类、活体开关、层级范围、排序与数量。"""
import tkinter as tk

from albion_aware.config import DEFAULT_CONFIG
from albion_aware.gather_targets import (DEFAULT_MAX_TARGETS, DEFAULT_SORT, KIND_ORDER,
                                         SORT_MODES)

BG = "#1b1b1b"
FG = "#e6e6e6"
MUTED = "#9a9a9a"


def validate_settings(values: dict) -> tuple[str, str] | None:
    """返回 (错误 key, 出错内容)；全部合法返回 None。"""
    if not values.get("kinds"):
        return ("gather.settings.no_kinds", "")
    tier_min = _as_int(values.get("tier_min"))
    tier_max = _as_int(values.get("tier_max"))
    if tier_min is None or tier_max is None or tier_min > tier_max:
        return ("gather.settings.tier_order", "")
    max_targets = _as_int(values.get("max_targets"))
    if max_targets is None or not 1 <= max_targets <= 10:
        return ("gather.settings.max_targets_invalid", str(values.get("max_targets")))
    if values.get("sort") not in SORT_MODES:
        return ("gather.settings.sort_invalid", "")
    return None


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


class GatherSettingsWindow:
    """顶栏漏斗图标打开的设置框。"""

    def __init__(self, master, i18n, values: dict, on_save):
        self.i18n = i18n
        self._on_save = on_save
        self.closed = False

        self.top = tk.Toplevel(master)
        self.top.title(i18n.t("gather.settings.title"))
        self.top.attributes("-topmost", True)
        self.top.configure(bg=BG, padx=14, pady=12)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.geometry("+%d+%d" % (master.winfo_screenwidth() // 2 - 170,
                                      master.winfo_screenheight() // 2 - 150))

        tk.Label(self.top, text=i18n.t("gather.settings.title"), bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")

        tk.Label(self.top, text=i18n.t("gather.settings.kinds"), bg=BG, fg=MUTED,
                 font=("Segoe UI", 8), anchor="w").pack(fill="x", pady=(8, 2))
        kinds_row = tk.Frame(self.top, bg=BG)
        kinds_row.pack(fill="x")
        selected = set(values.get("kinds") or KIND_ORDER)
        self.kind_vars: dict[str, tk.BooleanVar] = {}
        for kind in KIND_ORDER:
            var = tk.BooleanVar(value=kind in selected)
            self.kind_vars[kind] = var
            tk.Checkbutton(kinds_row, text=i18n.t("gather.kind." + kind), variable=var,
                           bg=BG, fg=FG, selectcolor="#2a2a2a", activebackground=BG,
                           activeforeground=FG, font=("Segoe UI", 8),
                           highlightthickness=0).pack(side="left", padx=(0, 6))

        self.living_var = tk.BooleanVar(value=bool(values.get("show_living", True)))
        tk.Checkbutton(self.top, text=i18n.t("gather.settings.living"),
                       variable=self.living_var, bg=BG, fg=FG, selectcolor="#2a2a2a",
                       activebackground=BG, activeforeground=FG, font=("Segoe UI", 9),
                       highlightthickness=0).pack(anchor="w", pady=(6, 2))

        tier_row = tk.Frame(self.top, bg=BG)
        tier_row.pack(fill="x", pady=2)
        tk.Label(tier_row, text=i18n.t("gather.settings.tier"), bg=BG, fg=FG,
                 font=("Segoe UI", 9), anchor="w").pack(side="left")
        self.tier_min = tk.Spinbox(tier_row, from_=1, to=8, width=4)
        self.tier_min.delete(0, "end")
        self.tier_min.insert(0, str(values.get("tier_min", 1)))
        self.tier_min.pack(side="left", padx=(6, 4))
        tk.Label(tier_row, text="~", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.tier_max = tk.Spinbox(tier_row, from_=1, to=8, width=4)
        self.tier_max.delete(0, "end")
        self.tier_max.insert(0, str(values.get("tier_max", 8)))
        self.tier_max.pack(side="left", padx=(4, 0))

        sort_row = tk.Frame(self.top, bg=BG)
        sort_row.pack(fill="x", pady=(6, 2))
        tk.Label(sort_row, text=i18n.t("gather.settings.sort"), bg=BG, fg=FG,
                 font=("Segoe UI", 9), anchor="w").pack(side="left")
        self.sort_var = tk.StringVar(value=values.get("sort", DEFAULT_SORT))
        for mode in SORT_MODES:
            tk.Radiobutton(sort_row, text=i18n.t("gather.settings.sort." + mode),
                           variable=self.sort_var, value=mode, bg=BG, fg=FG,
                           selectcolor="#2a2a2a", activebackground=BG, activeforeground=FG,
                           font=("Segoe UI", 8), highlightthickness=0).pack(side="left",
                                                                           padx=(6, 0))

        max_row = tk.Frame(self.top, bg=BG)
        max_row.pack(fill="x", pady=2)
        tk.Label(max_row, text=i18n.t("gather.settings.max_targets"), bg=BG, fg=FG,
                 font=("Segoe UI", 9), anchor="w").pack(side="left")
        self.max_targets = tk.Spinbox(max_row, from_=1, to=10, width=4)
        self.max_targets.delete(0, "end")
        self.max_targets.insert(0, str(values.get("max_targets", DEFAULT_MAX_TARGETS)))
        self.max_targets.pack(side="left", padx=(6, 0))

        tk.Label(self.top, text=i18n.t("gather.settings.hint"), bg=BG, fg=MUTED,
                 font=("Segoe UI", 8), wraplength=320, justify="left").pack(
                     anchor="w", pady=(8, 2))

        self._error = tk.StringVar(value="")
        tk.Label(self.top, textvariable=self._error, bg=BG, fg="#ff6b6b",
                 font=("Segoe UI", 9), wraplength=320, justify="left").pack(anchor="w")

        buttons = tk.Frame(self.top, bg=BG)
        buttons.pack(fill="x", pady=(8, 0))
        tk.Button(buttons, text=i18n.t("gather.settings.reset"),
                  command=self._reset).pack(side="left")
        tk.Button(buttons, text=i18n.t("gather.settings.cancel"),
                  command=self.close).pack(side="right")
        tk.Button(buttons, text=i18n.t("gather.settings.save"),
                  command=self._save).pack(side="right")

    def _collect(self) -> dict:
        return {
            "kinds": [kind for kind, var in self.kind_vars.items() if var.get()],
            "show_living": bool(self.living_var.get()),
            "tier_min": self.tier_min.get().strip(),
            "tier_max": self.tier_max.get().strip(),
            "sort": self.sort_var.get(),
            "max_targets": self.max_targets.get().strip(),
        }

    def _save(self) -> None:
        values = self._collect()
        problem = validate_settings(values)
        if problem:
            key, detail = problem
            self._error.set(self.i18n.t(key, value=detail))
            return
        values["tier_min"] = _as_int(values["tier_min"])
        values["tier_max"] = _as_int(values["tier_max"])
        values["max_targets"] = _as_int(values["max_targets"])
        self._on_save(values)
        self.close()

    def _reset(self) -> None:
        defaults = DEFAULT_CONFIG["gather"]
        for kind, var in self.kind_vars.items():
            var.set(kind in defaults["kinds"])
        self.living_var.set(defaults["show_living"])
        for widget, value in ((self.tier_min, defaults["tier_min"]),
                              (self.tier_max, defaults["tier_max"]),
                              (self.max_targets, defaults["max_targets"])):
            widget.delete(0, "end")
            widget.insert(0, str(value))
        self.sort_var.set(defaults["sort"])
        self._error.set("")

    def close(self) -> None:
        self.closed = True
        try:
            self.top.destroy()
        except tk.TclError:
            pass

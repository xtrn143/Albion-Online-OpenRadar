"""采集筛选设置窗：资源种类、活体开关、品质矩阵、排序与数量。"""
import tkinter as tk

from albion_aware.config import DEFAULT_CONFIG
from albion_aware.gather_targets import (ALL_QUALITIES, DEFAULT_MAX_TARGETS, DEFAULT_SORT,
                                         KIND_ORDER, SORT_MODES)

BG = "#1b1b1b"
FG = "#e6e6e6"
MUTED = "#9a9a9a"


def validate_settings(values: dict) -> tuple[str, str] | None:
    """返回 (错误 key, 出错内容)；全部合法返回 None。"""
    if not values.get("kinds"):
        return ("gather.settings.no_kinds", "")
    if not values.get("qualities"):
        return ("gather.settings.no_qualities", "")
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
                                      master.winfo_screenheight() // 2 - 220))

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

        tk.Label(self.top, text=i18n.t("gather.settings.qualities"), bg=BG, fg=MUTED,
                 font=("Segoe UI", 8), anchor="w").pack(fill="x", pady=(8, 2))
        quality_box = tk.Frame(self.top, bg=BG)
        quality_box.pack(fill="x")
        selected = set(values.get("qualities")
                       or [f"{tier}.{enchant}" for tier, enchant in sorted(ALL_QUALITIES)])
        self.quality_vars: dict[tuple[int, int], tk.BooleanVar] = {}
        for column, tier in enumerate(range(1, 9), start=1):
            tk.Label(quality_box, text=i18n.t("gather.settings.tier_column", value=tier),
                     bg=BG, fg=FG, font=("Segoe UI", 8)).grid(row=0, column=column,
                                                              padx=1)
            for row, enchant in enumerate(range(0, 5), start=1):
                if column == 1:
                    tk.Label(quality_box, text=str(enchant), bg=BG, fg=MUTED,
                             font=("Segoe UI", 8)).grid(row=row, column=0)
                text = f"{tier}.{enchant}"
                var = tk.BooleanVar(value=text in selected)
                self.quality_vars[(tier, enchant)] = var
                tk.Checkbutton(quality_box, text=text, variable=var, bg=BG, fg=FG,
                               selectcolor="#2a2a2a", activebackground=BG,
                               activeforeground=FG, font=("Segoe UI", 7),
                               highlightthickness=0, bd=0, padx=0).grid(
                                   row=row, column=column, sticky="w")

        quality_buttons = tk.Frame(self.top, bg=BG)
        quality_buttons.pack(fill="x", pady=(2, 0))
        tk.Button(quality_buttons, text=i18n.t("gather.settings.all"),
                  command=lambda: self._set_all_qualities(True)).pack(side="left")
        tk.Button(quality_buttons, text=i18n.t("gather.settings.clear"),
                  command=lambda: self._set_all_qualities(False)).pack(side="left",
                                                                      padx=(6, 0))

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
            "qualities": [f"{tier}.{enchant}"
                          for (tier, enchant), var in self.quality_vars.items() if var.get()],
            "sort": self.sort_var.get(),
            "max_targets": self.max_targets.get().strip(),
        }

    def _set_all_qualities(self, value: bool) -> None:
        for var in self.quality_vars.values():
            var.set(value)

    def _save(self) -> None:
        values = self._collect()
        problem = validate_settings(values)
        if problem:
            key, detail = problem
            self._error.set(self.i18n.t(key, value=detail))
            return
        values["max_targets"] = _as_int(values["max_targets"])
        self._on_save(values)
        self.close()

    def _reset(self) -> None:
        defaults = DEFAULT_CONFIG["gather"]
        for kind, var in self.kind_vars.items():
            var.set(kind in defaults["kinds"])
        self.living_var.set(defaults["show_living"])
        selected = set(defaults["qualities"])
        for (tier, enchant), var in self.quality_vars.items():
            var.set(f"{tier}.{enchant}" in selected)
        self.max_targets.delete(0, "end")
        self.max_targets.insert(0, str(defaults["max_targets"]))
        self.sort_var.set(defaults["sort"])
        self._error.set("")

    def close(self) -> None:
        self.closed = True
        try:
            self.top.destroy()
        except tk.TclError:
            pass

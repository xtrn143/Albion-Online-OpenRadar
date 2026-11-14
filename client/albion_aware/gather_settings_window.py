"""采集筛选设置窗：按资源种类分页签，各自配置品质，另有活体开关、排序与数量。"""
import tkinter as tk

from albion_aware.config import DEFAULT_CONFIG
from albion_aware.gather_targets import (DEFAULT_MAX_TARGETS, DEFAULT_SORT,
                                         KIND_ORDER, SORT_MODES)

BG = "#1b1b1b"
FG = "#e6e6e6"
MUTED = "#9a9a9a"
TAB_BG = "#2a2a2a"
TAB_ACTIVE_BG = "#3a3a3a"

QUALITY_TEXTS = tuple(f"{tier}.{enchant}"
                      for tier in range(1, 9) for enchant in range(0, 5))


def validate_settings(values: dict) -> tuple[str, str] | None:
    """返回 (错误 key, 出错内容)；全部合法返回 None。"""
    kinds = list(values.get("kinds") or [])
    if not kinds:
        return ("gather.settings.no_kinds", "")
    qualities = values.get("qualities")
    if not isinstance(qualities, dict):
        qualities = {}
    for kind in kinds:
        if not qualities.get(kind):
            return ("gather.settings.no_qualities", kind)
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
        self.top.geometry("+%d+%d" % (master.winfo_screenwidth() // 2 - 240,
                                      master.winfo_screenheight() // 2 - 220))

        tk.Label(self.top, text=i18n.t("gather.settings.title"), bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")

        selected_kinds = set(values.get("kinds") or KIND_ORDER)
        raw_qualities = values.get("qualities")
        if not isinstance(raw_qualities, dict):
            raw_qualities = {}

        self._tab_var = tk.StringVar(value=KIND_ORDER[0])
        tab_bar = tk.Frame(self.top, bg=BG)
        tab_bar.pack(fill="x", pady=(8, 0))
        for kind in KIND_ORDER:
            tk.Radiobutton(tab_bar, text=i18n.t("gather.kind." + kind),
                           variable=self._tab_var, value=kind, command=self._show_tab,
                           indicatoron=0, bg=TAB_BG, fg=FG, selectcolor=TAB_ACTIVE_BG,
                           activebackground=TAB_ACTIVE_BG, activeforeground=FG,
                           font=("Segoe UI", 9), bd=0, highlightthickness=0,
                           padx=10, pady=3).pack(side="left", padx=(0, 4))

        container = tk.Frame(self.top, bg=BG)
        container.pack(fill="both", expand=True, pady=(6, 0))

        self.kind_vars: dict[str, tk.BooleanVar] = {}
        self.quality_vars: dict[str, dict[tuple[int, int], tk.BooleanVar]] = {}
        self._pages: dict[str, tk.Frame] = {}
        for kind in KIND_ORDER:
            page = tk.Frame(container, bg=BG)
            self._pages[kind] = page

            kind_var = tk.BooleanVar(value=kind in selected_kinds)
            self.kind_vars[kind] = kind_var
            tk.Checkbutton(page, text=i18n.t("gather.settings.show_kind"),
                           variable=kind_var, bg=BG, fg=FG, selectcolor=TAB_BG,
                           activebackground=BG, activeforeground=FG,
                           font=("Segoe UI", 9), highlightthickness=0).pack(
                               anchor="w", pady=(0, 4))

            selected = set(raw_qualities.get(kind) or [])
            if not selected:
                selected = set(QUALITY_TEXTS)
            box = tk.Frame(page, bg=BG)
            box.pack(fill="x")
            vars_for_kind: dict[tuple[int, int], tk.BooleanVar] = {}
            for column, tier in enumerate(range(1, 9), start=1):
                tk.Label(box, text=i18n.t("gather.settings.tier_column", value=tier),
                         bg=BG, fg=FG, font=("Segoe UI", 8)).grid(
                             row=0, column=column, padx=1)
                for row, enchant in enumerate(range(0, 5), start=1):
                    if column == 1:
                        tk.Label(box, text=str(enchant), bg=BG, fg=MUTED,
                                 font=("Segoe UI", 8)).grid(row=row, column=0)
                    text = f"{tier}.{enchant}"
                    var = tk.BooleanVar(value=text in selected)
                    vars_for_kind[(tier, enchant)] = var
                    tk.Checkbutton(box, text=text, variable=var, bg=BG, fg=FG,
                                   selectcolor=TAB_BG, activebackground=BG,
                                   activeforeground=FG, font=("Segoe UI", 7),
                                   highlightthickness=0, bd=0, padx=0).grid(
                                       row=row, column=column, sticky="w")
            self.quality_vars[kind] = vars_for_kind

            quality_buttons = tk.Frame(page, bg=BG)
            quality_buttons.pack(fill="x", pady=(2, 0))
            tk.Button(quality_buttons, text=i18n.t("gather.settings.all"),
                      command=lambda k=kind: self._set_all_qualities(k, True)).pack(
                          side="left")
            tk.Button(quality_buttons, text=i18n.t("gather.settings.clear"),
                      command=lambda k=kind: self._set_all_qualities(k, False)).pack(
                          side="left", padx=(6, 0))

        self._show_tab()

        self.living_var = tk.BooleanVar(value=bool(values.get("show_living", True)))
        tk.Checkbutton(self.top, text=i18n.t("gather.settings.living"),
                       variable=self.living_var, bg=BG, fg=FG, selectcolor=TAB_BG,
                       activebackground=BG, activeforeground=FG, font=("Segoe UI", 9),
                       highlightthickness=0).pack(anchor="w", pady=(6, 2))

        sort_row = tk.Frame(self.top, bg=BG)
        sort_row.pack(fill="x", pady=(6, 2))
        tk.Label(sort_row, text=i18n.t("gather.settings.sort"), bg=BG, fg=FG,
                 font=("Segoe UI", 9), anchor="w").pack(side="left")
        self.sort_var = tk.StringVar(value=values.get("sort", DEFAULT_SORT))
        for mode in SORT_MODES:
            tk.Radiobutton(sort_row, text=i18n.t("gather.settings.sort." + mode),
                           variable=self.sort_var, value=mode, bg=BG, fg=FG,
                           selectcolor=TAB_BG, activebackground=BG, activeforeground=FG,
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
                 font=("Segoe UI", 8), wraplength=420, justify="left").pack(
                     anchor="w", pady=(8, 2))

        self._error = tk.StringVar(value="")
        tk.Label(self.top, textvariable=self._error, bg=BG, fg="#ff6b6b",
                 font=("Segoe UI", 9), wraplength=420, justify="left").pack(anchor="w")

        buttons = tk.Frame(self.top, bg=BG)
        buttons.pack(fill="x", pady=(8, 0))
        tk.Button(buttons, text=i18n.t("gather.settings.reset"),
                  command=self._reset).pack(side="left")
        tk.Button(buttons, text=i18n.t("gather.settings.cancel"),
                  command=self.close).pack(side="right")
        tk.Button(buttons, text=i18n.t("gather.settings.save"),
                  command=self._save).pack(side="right")

    def _show_tab(self) -> None:
        for page in self._pages.values():
            page.pack_forget()
        self._pages[self._tab_var.get()].pack(fill="both", expand=True)

    def _collect(self) -> dict:
        return {
            "kinds": [kind for kind in KIND_ORDER if self.kind_vars[kind].get()],
            "show_living": bool(self.living_var.get()),
            "qualities": {
                kind: [f"{tier}.{enchant}"
                       for (tier, enchant), var in self.quality_vars[kind].items()
                       if var.get()]
                for kind in KIND_ORDER
            },
            "sort": self.sort_var.get(),
            "max_targets": self.max_targets.get().strip(),
        }

    def _set_all_qualities(self, kind: str, value: bool) -> None:
        for var in self.quality_vars[kind].values():
            var.set(value)

    def _save(self) -> None:
        values = self._collect()
        problem = validate_settings(values)
        if problem:
            key, detail = problem
            if key == "gather.settings.no_qualities" and detail:
                detail = self.i18n.t("gather.kind." + detail)
            self._error.set(self.i18n.t(key, value=detail))
            return
        values["max_targets"] = _as_int(values["max_targets"])
        self._on_save(values)
        self.close()

    def _reset(self) -> None:
        defaults = DEFAULT_CONFIG["gather"]
        for kind, var in self.kind_vars.items():
            var.set(True)
        self.living_var.set(defaults["show_living"])
        for kind in KIND_ORDER:
            self._set_all_qualities(kind, True)
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

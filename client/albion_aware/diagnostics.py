"""零流量诊断：识别加速器、给分场景步骤、生成可复制的诊断摘要。"""
import tkinter as tk
import webbrowser

from albion_aware import __version__
from albion_aware.launcher import FEEDBACK_URL, run_cmd

NPCAP_URL = "https://npcap.com/#download"

ACCELERATOR_PROCESSES = {
    "thunder": ("thunder", "leiting"),
    "exitlag": ("exitlag",),
    "uu": ("uu", "netease"),
    "xunyou": ("xunyou",),
    "qiyou": ("qiyou",),
}


def running_tasklist(run=run_cmd) -> str:
    code, output = run(["tasklist", "/FO", "CSV", "/NH"])
    return output if code == 0 else ""


def parse_process_names(output: str) -> list[str]:
    names = []
    for line in output.splitlines():
        parts = line.split('","')
        if len(parts) >= 2 and parts[0].startswith('"'):
            names.append(parts[0].strip('"'))
    return names


def detect_accelerator(process_names) -> str | None:
    lowered = [str(name).lower() for name in process_names]
    for key, keywords in ACCELERATOR_PROCESSES.items():
        if any(word in name for name in lowered for word in keywords):
            return key
    return None


def scenario_steps(kind: str, accelerator: str | None = None) -> list[str]:
    if kind == "accelerator":
        return ["diag.accelerator." + (accelerator or "generic")]
    if kind == "direct":
        return ["diag.direct.firewall", "diag.direct.process", "diag.direct.restart"]
    return ["diag.generic.one", "diag.generic.two", "diag.generic.three"]


def report_lines(npcap_installed: bool, npcap_running: bool, radar_status: str,
                 interface_count: int, accelerator: str | None) -> list[str]:
    return [
        f"albion-aware={__version__}",
        f"npcap={'installed' if npcap_installed else 'missing'}/"
        f"{'running' if npcap_running else 'stopped'}",
        f"radar={radar_status}",
        f"interfaces={interface_count}",
        f"accelerator={accelerator or 'none'}",
    ]


class DiagnosticsWindow:
    """诊断向导：网卡全选、分场景步骤、复制摘要并打开反馈页。"""

    def __init__(self, master, i18n, collect_report, on_select_all, accelerator=None):
        self.i18n = i18n
        self._collect_report = collect_report      # () -> list[str]
        self._on_select_all = on_select_all        # () -> list[str]
        self._accelerator = accelerator
        self.closed = False

        self.top = tk.Toplevel(master)
        self.top.title(i18n.t("diag.title"))
        self.top.attributes("-topmost", True)
        self.top.configure(bg="#1b1b1b", padx=14, pady=12)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.geometry("+%d+%d" % (master.winfo_screenwidth() // 2 - 170,
                                      master.winfo_screenheight() // 2 - 130))

        tk.Label(self.top, text=i18n.t("diag.no_traffic"), bg="#1b1b1b", fg="#e6e6e6",
                 font=("Segoe UI", 10, "bold"), wraplength=320,
                 justify="left").pack(anchor="w")

        row = tk.Frame(self.top, bg="#1b1b1b")
        row.pack(fill="x", pady=(8, 4))
        self.choice = tk.StringVar(value="accelerator")
        for value, key in (("accelerator", "diag.accelerator"), ("direct", "diag.direct")):
            tk.Radiobutton(row, text=i18n.t(key), value=value, variable=self.choice,
                           command=self._update_steps, bg="#1b1b1b", fg="#e6e6e6",
                           selectcolor="#1b1b1b", activebackground="#1b1b1b").pack(anchor="w")

        self.steps = tk.Label(self.top, text="", bg="#1b1b1b", fg="#9a9a9a",
                              font=("Segoe UI", 9), wraplength=320, justify="left")
        self.steps.pack(anchor="w", pady=(4, 8))

        buttons = tk.Frame(self.top, bg="#1b1b1b")
        buttons.pack(fill="x")
        tk.Button(buttons, text=i18n.t("diag.select_all"), command=self._select_all).pack(fill="x")
        tk.Button(buttons, text=i18n.t("diag.copy_and_open"),
                  command=self._copy_and_open).pack(fill="x", pady=(4, 0))
        tk.Button(buttons, text=i18n.t("diag.npcap_download"),
                  command=lambda: webbrowser.open(NPCAP_URL)).pack(fill="x", pady=(4, 0))
        tk.Button(buttons, text=i18n.t("common.ok"), command=self.close).pack(anchor="e", pady=(6, 0))

        self._update_steps()

    def _update_steps(self) -> None:
        steps = scenario_steps(self.choice.get(), self._accelerator)
        self.steps.configure(text="\n".join("• " + self.i18n.t(key) for key in steps))

    def _select_all(self) -> None:
        names = self._on_select_all()
        self._update_steps()
        self.steps.configure(
            text=self.steps.cget("text") + "\n" + self.i18n.t("diag.select_all_done", count=len(names))
        )

    def _copy_and_open(self) -> None:
        text = "\n".join(self._collect_report())
        self.top.clipboard_clear()
        self.top.clipboard_append(text)
        webbrowser.open(FEEDBACK_URL)

    def close(self) -> None:
        self.closed = True
        try:
            self.top.destroy()
        except tk.TclError:
            pass

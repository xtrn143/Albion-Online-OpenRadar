"""启动器：Npcap/雷达/网卡检测、零流量判断与首启向导。"""
import subprocess
import time

FEEDBACK_URL = "https://portaler.pages.dev/"


def run_cmd(args, timeout: float = 15.0) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, str(exc)
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def npcap_installed(run=run_cmd) -> bool:
    code, _output = run(["sc", "query", "npcap"])
    return code == 0


def npcap_running(run=run_cmd) -> bool:
    code, output = run(["sc", "query", "npcap"])
    return code == 0 and "RUNNING" in output.upper()


def ensure_npcap_running(run=run_cmd) -> bool:
    if npcap_running(run):
        return True
    run(["sc", "start", "npcap"])
    return npcap_running(run)


def is_silent(last_activity: float, now: float, threshold: float = 60.0) -> bool:
    return (now - last_activity) >= threshold


def _requests():
    import requests
    return requests


def _get_json(url: str, session=None, timeout: float = 3.0):
    session = session or _requests()
    try:
        response = session.get(url, timeout=timeout)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None


def radar_state(base_url: str, session=None):
    return _get_json(base_url + "/api/network/state", session)


def list_interfaces(base_url: str, session=None) -> list:
    data = _get_json(base_url + "/api/network/interfaces", session, timeout=5.0)
    return data if isinstance(data, list) else []


def select_all_interfaces(base_url: str, session=None) -> list:
    session = session or _requests()
    try:
        session.post(base_url + "/api/network/refresh", timeout=10)
    except Exception:
        pass
    names = [
        row.get("name") for row in list_interfaces(base_url, session)
        if isinstance(row, dict) and row.get("name")
    ]
    try:
        session.post(base_url + "/api/network/interfaces", json={"names": names}, timeout=10)
    except Exception:
        return []
    return names


def wait_radar_ready(base_url: str, timeout: float = 30.0, interval: float = 1.0,
                     session=None, sleep=time.sleep, clock=time.monotonic) -> bool:
    deadline = clock() + timeout
    while clock() <= deadline:
        if radar_state(base_url, session) is not None:
            return True
        sleep(interval)
    return False


def wizard_needed(config) -> bool:
    return not bool(config.get("onboarded"))


def run_wizard(root, config, i18n) -> None:
    """首启向导：选语言、填自己的角色名。"""
    import tkinter as tk

    top = tk.Toplevel(root)
    top.title(i18n.t("wizard.title"))
    top.geometry("+%d+%d" % (root.winfo_screenwidth() // 2 - 160,
                             root.winfo_screenheight() // 2 - 110))
    top.attributes("-topmost", True)
    top.configure(bg="#1b1b1b", padx=16, pady=12)

    tk.Label(top, text=i18n.t("wizard.title"), bg="#1b1b1b", fg="#e6e6e6",
             font=("Segoe UI", 11, "bold")).pack(anchor="w")
    tk.Label(top, text=i18n.t("wizard.language"), bg="#1b1b1b", fg="#9a9a9a",
             font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 2))
    language = tk.StringVar(value=config.get("language", "auto"))
    tk.OptionMenu(top, language, "auto", "zh-CN", "en").pack(anchor="w", fill="x")

    tk.Label(top, text=i18n.t("wizard.self_name"), bg="#1b1b1b", fg="#9a9a9a",
             font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 2))
    self_name = tk.StringVar(value=config.get("self_name", ""))
    tk.Entry(top, textvariable=self_name).pack(anchor="w", fill="x")
    tk.Label(top, text=i18n.t("wizard.self_name_hint"), bg="#1b1b1b", fg="#777777",
             font=("Segoe UI", 8)).pack(anchor="w")

    def finish() -> None:
        config.set("language", language.get())
        config.set("self_name", self_name.get().strip())
        config.set("onboarded", True)
        config.save()
        top.destroy()

    tk.Button(top, text=i18n.t("wizard.next"), command=finish).pack(anchor="e", pady=(12, 0))
    root.wait_window(top)

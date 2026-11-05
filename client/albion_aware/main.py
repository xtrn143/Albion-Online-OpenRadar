# client/albion_aware/main.py
"""装配层：配置、解析、玩家表、悬浮窗、托盘与热键。"""
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk

from albion_aware import __version__
from albion_aware.config import Config
from albion_aware.detail_panel import DetailPanel, equipment_entries
from albion_aware.diagnostics import (
    DiagnosticsWindow,
    detect_accelerator,
    parse_process_names,
    report_lines,
    running_tasklist,
)
from albion_aware.event_parser import (
    PartyEvent,
    PlayerLeft,
    PlayerSeen,
    PlayerUpdated,
    ZoneChanged,
    parse_message,
)
from albion_aware.i18n import I18n
from albion_aware.icons import IconCache, ItemDatabase, draw_enchant_badge, enchant_level
from albion_aware.launcher import (
    FEEDBACK_URL,
    ensure_radar,
    list_interfaces,
    npcap_installed,
    npcap_running,
    radar_executable,
    radar_state,
    run_wizard,
    select_all_interfaces,
    wizard_needed,
)
from albion_aware.map_index import AvalonMapIndex, is_roads_zone
from albion_aware.map_window import MapWindow
from albion_aware.models import View
from albion_aware.overlay import ICON_SIZE, OverlayWindow
from albion_aware.party import PartyList
from albion_aware.player_store import PlayerStore
from albion_aware.radar_client import RadarClient
from albion_aware.tray import build_tray
from albion_aware.win32_ext import HotkeyListener


SOUND_COOLDOWN_S = 2.0
RADAR_RETRY_S = 15.0


def has_new_stranger(before_ids: set[int], after_ids: set[int]) -> bool:
    return bool(after_ids - before_ids)


def sound_cooldown_ok(last_at: float | None, now: float,
                      cooldown: float = SOUND_COOLDOWN_S) -> bool:
    return last_at is None or (now - last_at) >= cooldown


def push_history(history, name: str, limit: int = 10) -> list[str]:
    cleaned = [str(item) for item in history if str(item) != name]
    return [str(name)] + cleaned[:limit - 1]


def _load_items(app_dir: Path) -> ItemDatabase:
    try:
        return ItemDatabase.load(app_dir / "data" / "items.min.json")
    except (OSError, ValueError):
        return ItemDatabase([])


def _resource_dir(app_dir: Path) -> Path:
    """打包后资源在 sys._MEIPASS 里，开发时在 app_dir。"""
    return Path(getattr(sys, "_MEIPASS", None) or app_dir)


def user_data_dir(app_dir: Path) -> Path:
    """打包运行时用户数据放 %LOCALAPPDATA%，避免安装目录只读。"""
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "AlbionAware"
    return Path(app_dir)


class AlbionAwareApp:
    def __init__(self, app_dir: Path):
        self.app_dir = app_dir
        self.data_dir = user_data_dir(app_dir)
        self.config = Config(self.data_dir / "config.json")
        self.i18n = I18n(self.config.language())
        resource_dir = _resource_dir(app_dir)
        self.db = _load_items(resource_dir)
        bundled_icons = resource_dir / "data" / "icons"
        self.icons = IconCache(self.data_dir / "cache" / "icons", self.db,
                               bundled=bundled_icons if bundled_icons.is_dir() else None)
        self.store = PlayerStore(
            self_name=self.config.get("self_name", ""),
            timeout=float(self.config.get("player_timeout", 60)),
        )
        self.party = PartyList(self.data_dir / "party.json")
        self._expanded = False
        self._rows = []
        self._photo_cache = {}
        self._icon_pending: set[int] = set()
        self._state = "connecting"
        self._flash_pending = False
        self._events: list[list] = []
        self._actions: list[tuple] = []
        self._connected_at = None
        self._started_at = time.monotonic()
        self._ever_received = False
        self._diag_shown = False
        self._diag_window = None
        self._last_sound_at = None
        self._stopping = threading.Event()
        self._no_radar_warned = False
        self._zone_id = ""
        self._in_roads = False
        self._map_index = None
        self._map_index_loading = False
        self._map_window = None
        self._map_history = [str(name) for name in (self.config.get("map_history") or [])]

        self.window = OverlayWindow(
            i18n=self.i18n,
            icon_loader=self._row_icon,
            on_row_click=self._on_row_click,
            on_more_click=self._on_more_click,
            on_drag_end=self._save_position,
            on_sound_click=self._toggle_sound,
            on_map_click=self._open_maps,
        )
        self.window.set_sound(bool(self.config.get("overlay.sound", False)))
        self.window.render(View(), self._item_power)

        saved_x = self.config.get("overlay.x")
        saved_y = self.config.get("overlay.y")
        if saved_x is None or saved_y is None:
            self.window.reset_position()
        else:
            self.window.place_at(saved_x, saved_y)
        self.window.set_opacity(self.config.get("overlay.opacity", 0.9))

        self.panel = DetailPanel(self.window.root, self.i18n, self._detail_icon,
                                 self._on_mark_party, lambda _player: None)

        self.client = RadarClient(self.config.get("radar.ws_url", "ws://localhost:5001/ws"),
                                  on_frames=self._on_frames, on_state=self._on_state)
        self.hotkeys = HotkeyListener({
            self.config.get("hotkeys.toggle_click_through", "F10"): self._queue_toggle_click_through,
            self.config.get("hotkeys.mark_party", "F9"): self._queue_mark_selected,
            self.config.get("hotkeys.toggle_visible", "F8"): self._queue_toggle_visible,
            self.config.get("hotkeys.toggle_sound", "F7"): self._queue_toggle_sound,
            self.config.get("hotkeys.map_lookup", "F6"): self._queue_toggle_maps,
        })
        self.tray = build_tray(self.i18n, self._tray_actions())

    # ---------- 线程边界：WS/热键/托盘只入队，Tk 操作在主线程 ----------
    def _queue_action(self, action, *args) -> None:
        self._actions.append((action, args))

    def _queue_toggle_visible(self):
        self._queue_action(self._toggle_visible)

    def _queue_toggle_click_through(self):
        self._queue_action(self._toggle_click_through)

    def _queue_toggle_sound(self):
        self._queue_action(self._toggle_sound)

    def _queue_mark_selected(self):
        self._queue_action(self._mark_selected)

    def _queue_open_maps(self):
        self._queue_action(self._open_maps)

    def _queue_toggle_maps(self):
        self._queue_action(self._toggle_maps)

    def _toggle_maps(self) -> None:
        if self._map_window is not None and self._map_window.is_open:
            self._map_window.close()
            return
        self._open_maps()

    def _on_frames(self, frames) -> None:
        self._ever_received = True
        events = []
        for frame in frames:
            events.extend(parse_message(frame))
        if events:
            self._events.append(events)

    def _on_state(self, state: str) -> None:
        self._state = state
        if state == "connected" and self._connected_at is None:
            self._connected_at = time.monotonic()

    # ---------- 主线程 --------------
    def _drain(self) -> None:
        try:
            dirty = bool(self.store.prune())
            while self._actions:
                action, args = self._actions.pop(0)
                action(*args)
                dirty = True
            while self._events:
                if self._apply(self._events.pop(0)):
                    dirty = True
            self.window.set_status(self._state == "connected")
            if dirty:
                self._refresh()
            self._check_silence()
        except Exception:
            pass
        finally:
            self.window.root.after(100, self._drain)

    def _check_silence(self) -> None:
        if self._diag_shown or self._ever_received:
            return
        # 连上之后一直没数据，或压根没连上（雷达没起来），都要给出诊断入口
        since = self._connected_at if self._connected_at is not None else self._started_at
        if time.monotonic() - since < 60.0:
            return
        self._diag_shown = True
        threading.Thread(target=self._diagnose_silence, daemon=True).start()

    def _diagnose_silence(self) -> None:
        accelerator = detect_accelerator(parse_process_names(running_tasklist()))
        self._queue_action(self._open_diagnostics, accelerator)

    def _open_maps(self) -> None:
        if self._map_window is None or not self._map_window.alive:
            self._map_window = MapWindow(
                self.window.root,
                self.i18n,
                data_dir=_resource_dir(self.app_dir) / "data" / "avalon",
                history=self._map_history,
                on_position_changed=self._save_map_position,
                on_selected=self._remember_map,
            )
            if self._map_index is not None:
                self._map_window.set_index(self._map_index)
            else:
                self._load_map_index()
            map_x = self.config.get("overlay.map_x")
            map_y = self.config.get("overlay.map_y")
            if map_x is not None and map_y is not None:
                self._map_window.place_at(map_x, map_y)
        self._map_window.open(self._zone_id if self._in_roads else None)

    def _load_map_index(self) -> None:
        if self._map_index is not None or self._map_index_loading:
            return
        self._map_index_loading = True
        path = _resource_dir(self.app_dir) / "data" / "avalon" / "index.json"

        def work() -> None:
            try:
                index = AvalonMapIndex.load(path)
            except (OSError, ValueError):
                index = None
            self._queue_action(self._map_index_ready, index)

        threading.Thread(target=work, name="avalon-map-index", daemon=True).start()

    def _map_index_ready(self, index) -> None:
        self._map_index_loading = False
        self._map_index = index
        if self._map_window is not None:
            self._map_window.set_index(index)

    def _save_map_position(self, x: int, y: int) -> None:
        self.config.set("overlay.map_x", int(x))
        self.config.set("overlay.map_y", int(y))
        self.config.save()

    def _remember_map(self, name: str) -> None:
        self._map_history = push_history(self._map_history, name)
        self.config.set("map_history", self._map_history)
        self.config.save()

    def _open_diagnostics(self, accelerator=None) -> None:
        self._diag_window = DiagnosticsWindow(
            self.window.root, self.i18n, self._diagnostic_report,
            lambda: select_all_interfaces(self.config.get("radar.base_url", "http://localhost:5001")),
            accelerator=accelerator,
        )

    def _diagnostic_report(self) -> list[str]:
        base_url = self.config.get("radar.base_url", "http://localhost:5001")
        return report_lines(
            npcap_installed=npcap_installed(),
            npcap_running=npcap_running(),
            radar_status="ok" if radar_state(base_url) is not None else "unreachable",
            interface_count=len(list_interfaces(base_url)),
            accelerator=detect_accelerator(parse_process_names(running_tasklist())),
        )

    def _ensure_radar(self) -> None:
        try:
            base_url = self.config.get("radar.base_url", "http://localhost:5001")
            radar_dir = self.app_dir / "OpenRadar"
            if radar_executable(radar_dir) is None:
                # 只拷贝了 AlbionAware.exe、丢了 OpenRadar 文件夹时，用户只会看到灰灯
                if not self._no_radar_warned and radar_state(base_url) is None:
                    self._no_radar_warned = True
                    self._queue_action(self._warn_no_radar)
                return
            if ensure_radar(base_url, radar_dir):
                select_all_interfaces(base_url)
        except Exception:
            pass

    def _warn_no_radar(self) -> None:
        messagebox.showwarning("AlbionAware", self.i18n.t("diag.no_radar"))

    def _supervise_radar(self) -> None:
        """雷达被杀毒软件拦截或中途退出时自动重试，避免状态灯永久灰着。"""
        while not self._stopping.is_set():
            if self._state != "connected":
                self._ensure_radar()
            self._stopping.wait(RADAR_RETRY_S)

    def _apply(self, events) -> bool:
        before = {player.id for player in self._view_rows()}
        party_names_before = len(self.party.names)
        applied = False
        for event in events:
            if isinstance(event, PlayerSeen):
                self.store.upsert(event.player_id, event.fields)
                applied = True
            elif isinstance(event, PlayerUpdated):
                applied = self.store.update_existing(event.player_id, event.fields) or applied
            elif isinstance(event, PlayerLeft):
                self.store.remove(event.player_id)
                applied = True
            elif isinstance(event, ZoneChanged):
                self._zone_id = event.zone_id
                self.store.clear()
                self.panel.hide()
                if is_roads_zone(event.zone_id):
                    if not self._in_roads:
                        self.window.flash_map_icon()
                    self._in_roads = True
                else:
                    self._in_roads = False
                applied = True
            elif isinstance(event, PartyEvent):
                self.party.handle_event(event.parameters, self.store)
                applied = True
        self.party.resolve(self.store)
        if len(self.party.names) != party_names_before:
            self.party.save()
        after = {player.id for player in self._view_rows()}
        if applied and has_new_stranger(before, after):
            self._flash_pending = True
        return applied

    def _view_rows(self):
        return self.store.view(self.party, max_rows=10000,
                               sort_mode=self.config.get("sort_mode", "recent"),
                               ip_getter=self._item_power).rows

    def _refresh(self) -> None:
        max_rows = 10000 if self._expanded else int(self.config.get("max_rows", 6))
        view = self.store.view(self.party, max_rows=max_rows,
                               sort_mode=self.config.get("sort_mode", "recent"),
                               ip_getter=self._item_power)
        self._rows = view.rows
        self.window.render(view, self._item_power)
        if self._flash_pending:
            self._flash_pending = False
            self.window.flash()
            self._play_sound()

    def _item_power(self, player):
        return self.db.average_ip(player.equip)

    # ---------- 图标 ----------
    def _row_icon(self, player):
        item_id = int(player.equip[0]) if player.equip else 0
        return self._photo(item_id, ICON_SIZE)

    def _detail_icon(self, item_id):
        return self._photo(item_id, ICON_SIZE)

    def _photo(self, item_id: int, size: int):
        key = (item_id, size)
        if key in self._photo_cache:
            return self._photo_cache[key]
        path = self.icons.path_for(item_id)
        if path is None:
            if item_id not in self._icon_pending and self.db.unique_name(item_id):
                self._icon_pending.add(item_id)
                threading.Thread(target=self._fetch_icon, args=(item_id,), daemon=True).start()
            path = self.icons.placeholder_for(item_id)
        photo = None
        try:
            image = Image.open(path)
            image.thumbnail((size, size))
            # 右下角补附魔等级角标（官方图该处本来就是留空的）
            image = draw_enchant_badge(image, enchant_level(self.db.unique_name(item_id)))
            photo = ImageTk.PhotoImage(image, master=self.window.root)
        except Exception:
            photo = None
        self._photo_cache[key] = photo
        return photo

    def _fetch_icon(self, item_id: int) -> None:
        """后台下载图标；失败时保持占位图，不触发无休止的重试。"""
        try:
            path = self.icons.get(item_id)
        except Exception:
            path = None
        finally:
            self._icon_pending.discard(item_id)
        if path is None or path == self.icons.placeholder_for(item_id):
            return
        self._queue_action(self._icons_ready)

    def _icons_ready(self) -> None:
        self._photo_cache.clear()
        self._refresh()

    # ---------- 交互 ----------
    def _on_row_click(self, player) -> None:
        self.panel.show(player, self._item_power(player),
                        self.party.contains_name(player.nickname),
                        equipment_entries(player, self.db),
                        max(self.window.root.winfo_x() - 226, 0),
                        self.window.root.winfo_y())

    def _on_more_click(self) -> None:
        self._expanded = not self._expanded
        self._refresh()

    def _on_mark_party(self, player) -> None:
        if self.party.contains_name(player.nickname):
            self.party.remove_name(player.nickname)
        else:
            self.party.add_name(player.nickname)
        self.party.save()
        self.panel.hide()
        self._refresh()

    def _mark_selected(self) -> None:
        if self.panel.current is not None:
            self._on_mark_party(self.panel.current)

    def _save_position(self, x: int, y: int) -> None:
        self.config.set("overlay.x", int(x))
        self.config.set("overlay.y", int(y))
        self.config.save()

    def _set_opacity(self, value: float) -> None:
        self.window.set_opacity(value)
        self.config.set("overlay.opacity", float(value))
        self.config.save()

    def _toggle_sound(self) -> None:
        enabled = not bool(self.config.get("overlay.sound", False))
        self.config.set("overlay.sound", enabled)
        self.config.save()
        self.window.set_sound(enabled)

    def _play_sound(self) -> None:
        if not bool(self.config.get("overlay.sound", False)) or sys.platform != "win32":
            return
        now = time.monotonic()
        # 同一批新玩家只响一次，避免瞬间连续蜂鸣
        if not sound_cooldown_ok(self._last_sound_at, now):
            return
        self._last_sound_at = now

        def beep() -> None:
            try:
                import winsound
                winsound.Beep(880, 120)
            except Exception:
                pass

        threading.Thread(target=beep, daemon=True).start()

    def _toggle_visible(self) -> None:
        self.window.toggle_visible()

    def _toggle_click_through(self) -> None:
        self.window.set_click_through(not self.window.click_through)

    def _open_feedback(self) -> None:
        webbrowser.open(FEEDBACK_URL)

    def _show_about(self) -> None:
        messagebox.showinfo("AlbionAware",
                            f"{self.i18n.t('about.version', version=__version__)}\n"
                            f"{self.i18n.t('about.license')}")

    def _set_language(self, setting: str) -> None:
        self.config.set("language", setting)
        self.config.save()
        self.i18n = I18n(self.config.language())
        self.window.i18n = self.i18n
        self.panel.i18n = self.i18n
        if self._diag_window is not None:
            self._diag_window.close()
            self._diag_window = None
        if self._map_window is not None:
            self._map_window.destroy()
            self._map_window = None
        try:
            self.tray.stop()
        except Exception:
            pass
        self.tray = build_tray(self.i18n, self._tray_actions())
        self.tray.run_detached()
        self._refresh()

    def _tray_actions(self) -> dict:
        return {
            "toggle_visible": lambda: self._queue_action(self._toggle_visible),
            "click_through": lambda: self._queue_action(self._toggle_click_through),
            "map_lookup": lambda: self._queue_action(self._open_maps),
            "reset_position": lambda: self._queue_action(self.window.reset_position),
            "set_opacity": lambda value: self._queue_action(self._set_opacity, value),
            "toggle_sound": lambda: self._queue_action(self._toggle_sound),
            "sound_on": lambda: bool(self.config.get("overlay.sound", False)),
            "feedback": lambda: self._queue_action(self._open_feedback),
            "about": lambda: self._queue_action(self._show_about),
            "set_language": lambda setting: self._queue_action(self._set_language, setting),
            "quit": lambda: self._queue_action(self._quit),
        }

    def _reload_from_config(self) -> None:
        self.i18n = I18n(self.config.language())
        self.window.i18n = self.i18n
        self.store.set_self_name(self.config.get("self_name", ""))
        self._refresh()

    def _quit(self) -> None:
        self._stopping.set()
        if self._diag_window is not None:
            self._diag_window.close()
        if self._map_window is not None:
            self._map_window.destroy()
            self._map_window = None
        self.client.stop()
        self.hotkeys.stop()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.window.close()

    def run(self) -> None:
        if wizard_needed(self.config):
            run_wizard(self.window.root, self.config, self.i18n)
            self._reload_from_config()
        if wizard_needed(self.config):
            return  # 用户关闭了向导窗口且未填写，不进入主循环
        threading.Thread(target=self._supervise_radar, name="radar-supervisor", daemon=True).start()
        self.client.start()
        self.hotkeys.start()
        try:
            self.tray.run_detached()
        except Exception:
            pass
        self._refresh()
        self.window.root.after(100, self._drain)
        self.window.run()


def main() -> None:
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).resolve().parents[1]
    AlbionAwareApp(app_dir).run()


if __name__ == "__main__":
    main()

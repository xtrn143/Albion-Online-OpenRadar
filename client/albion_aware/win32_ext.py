# client/albion_aware/win32_ext.py
"""Win32 窗口扩展样式与全局热键；非 Windows 平台下所有调用安全空转。"""
import ctypes
import sys
import threading
import time

if sys.platform == "win32":
    import ctypes.wintypes  # 仅 import ctypes 不会加载该子模块

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WM_HOTKEY = 0x0312

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

_KEY_CODES = {f"F{index}": 0x6F + index for index in range(1, 13)}
_KEY_CODES.update({
    "Insert": 0x2D, "Delete": 0x2E, "Home": 0x24, "End": 0x25,
    "PageUp": 0x21, "PageDown": 0x22, "Tab": 0x09, "Esc": 0x1B,
})
_MODIFIERS = {"Alt": MOD_ALT, "Ctrl": MOD_CONTROL, "Control": MOD_CONTROL,
              "Shift": MOD_SHIFT, "Win": MOD_WIN}


def parse_hotkey(text: str) -> tuple[int, int]:
    """把 "Ctrl+F10" 解析为 (修饰键位掩码, 虚拟键码)。不可识别时抛 ValueError。"""
    parts = [part.strip() for part in str(text or "").split("+") if part.strip()]
    if not parts:
        raise ValueError("empty hotkey")
    modifiers = 0
    for part in parts[:-1]:
        modifier = _MODIFIERS.get(part.capitalize() if part.capitalize() in _MODIFIERS else part)
        if modifier is None:
            raise ValueError(f"unknown modifier: {part}")
        modifiers |= modifier
    key = parts[-1]
    code = _KEY_CODES.get(key.upper() if key.upper().startswith("F") else key)
    if code is None:
        raise ValueError(f"unknown key: {key}")
    return modifiers, code


def _user32():
    return ctypes.windll.user32


def _with_style(hwnd: int, set_bits: int, clear_bits: int) -> None:
    if sys.platform != "win32":
        return
    style = _user32().GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style | set_bits) & ~clear_bits
    _user32().SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def make_noactivate(hwnd: int) -> None:
    """置顶、不抢焦点、不进 Alt+Tab。"""
    _with_style(hwnd, WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW, 0)


def set_click_through(hwnd: int, enabled: bool) -> None:
    if enabled:
        _with_style(hwnd, WS_EX_TRANSPARENT, 0)
    else:
        _with_style(hwnd, 0, WS_EX_TRANSPARENT)


class HotkeyListener(threading.Thread):
    """在后台线程用 RegisterHotKey + PeekMessage 监听全局热键。"""

    def __init__(self, bindings: dict[str, callable]):
        super().__init__(name="hotkey-listener", daemon=True)
        self._texts: list[str] = []
        parsed = []
        for text, callback in bindings.items():
            try:
                parsed.append((parse_hotkey(text), callback))
            except ValueError:
                continue  # 用户手改配置写错时跳过，不让程序启动崩溃
            self._texts.append(text)
        self._bindings = parsed
        self.failed: list[str] = []     # 注册失败（被其他程序占用）的热键
        self.ready = threading.Event()  # 首次注册完成后置位，供调用方读取 failed
        self._stopping = threading.Event()

    def stop(self) -> None:
        self._stopping.set()
        if self.is_alive() and threading.current_thread() is not self:
            # 等旧线程注销热键，避免重建时 RegisterHotKey 因冲突失败
            self.join(timeout=1.0)

    def run(self) -> None:
        if sys.platform != "win32":
            self.ready.set()
            return
        user32 = _user32()
        registered = []
        self.failed = []
        for index, ((mods, vk), _) in enumerate(self._bindings, start=1):
            if user32.RegisterHotKey(None, index, mods, vk):
                registered.append(index)
            else:
                self.failed.append(self._texts[index - 1])
        self.ready.set()
        try:
            message = ctypes.wintypes.MSG()
            while not self._stopping.is_set():
                if user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                    if message.message == WM_HOTKEY:
                        index = int(message.wParam)
                        if 1 <= index <= len(self._bindings):
                            self._bindings[index - 1][1]()
                else:
                    time.sleep(0.05)
        finally:
            for index in registered:
                user32.UnregisterHotKey(None, index)

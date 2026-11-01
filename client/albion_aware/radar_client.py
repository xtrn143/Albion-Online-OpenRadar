"""连接 OpenRadar 的 WebSocket，拆分批次并处理指数退避重连。"""
import json
import threading


def next_delay(current: float, max_delay: float = 30.0) -> float:
    """指数退避：每次乘以 2，但不超过上限。"""
    return min(current * 2, max_delay)


def parse_frames(raw: str) -> list[dict]:
    """解析单帧或批次帧，返回规范的 {"code", "dictionary"} 列表。"""
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    if data.get("type") == "batch":
        # 批次帧把多条消息打包在一个 messages 数组里
        messages = data.get("messages")
        if not isinstance(messages, list):
            return []
    else:
        messages = [data]

    frames: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        dictionary = message.get("dictionary")
        if isinstance(dictionary, str):
            # 部分服务端把 dictionary 序列化成 JSON 字符串
            try:
                dictionary = json.loads(dictionary)
            except json.JSONDecodeError:
                continue
        if not isinstance(dictionary, dict):
            continue
        frames.append({"code": message.get("code"), "dictionary": dictionary})
    return frames


class RadarClient:
    """后台线程持续连接 OpenRadar，断线后按指数退避自动重连。"""

    def __init__(self, url: str, on_frames=None, on_state=None, max_delay: float = 30.0):
        self.url = url
        self.max_delay = max_delay
        self._on_frames = on_frames or (lambda frames: None)
        self._on_state = on_state or (lambda state: None)
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws = None
        self._opened = False

    def start(self) -> None:
        """启动 daemon 线程，不阻塞调用方。"""
        self._thread = threading.Thread(target=self._run, name="radar-client", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """通知线程退出并等待其结束。"""
        self._stopping.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _on_open(self, _ws) -> None:
        self._opened = True
        self._on_state("connected")

    def _handle(self, raw) -> None:
        frames = parse_frames(raw)
        if frames:
            self._on_frames(frames)

    def _run(self) -> None:
        import websocket  # 延迟导入，测试环境无需真实网络

        delay = 1.0
        while not self._stopping.is_set():
            self._on_state("connecting")
            self._ws = websocket.WebSocketApp(
                self.url,
                on_message=lambda _ws, message: self._handle(message),
                on_open=self._on_open,
                on_close=lambda _ws, *_args: self._on_state("disconnected"),
            )
            try:
                self._ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception:
                self._on_state("disconnected")
            if self._opened:
                # 连接成功后重置退避，避免一次掉线后重连间隔永久停在 30 秒
                delay = 1.0
                self._opened = False
            if self._stopping.is_set():
                break
            # 等待退避间隔，同时可被 stop() 立即打断
            self._stopping.wait(delay)
            delay = next_delay(delay, self.max_delay)

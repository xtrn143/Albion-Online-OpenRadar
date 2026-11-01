from albion_aware.config import Config
from albion_aware.launcher import (
    ensure_npcap_running,
    is_silent,
    list_interfaces,
    npcap_installed,
    npcap_running,
    select_all_interfaces,
    start_radar,
    wait_radar_ready,
    wizard_needed,
)


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(("GET", url))
        return self.responses.get(url, FakeResponse(500))

    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        return FakeResponse(200)


def test_npcap_installed_uses_exit_code():
    assert npcap_installed(run=lambda args: (0, "SERVICE_NAME: npcap")) is True
    assert npcap_installed(run=lambda args: (1060, "does not exist")) is False


def test_npcap_running_parses_service_state():
    assert npcap_running(run=lambda args: (0, "STATE : 4  RUNNING")) is True
    assert npcap_running(run=lambda args: (0, "STATE : 1  STOPPED")) is False
    assert npcap_running(run=lambda args: (1060, "")) is False


def test_ensure_npcap_skips_start_when_already_running():
    calls = []

    def run(args):
        calls.append(args)
        return (0, "RUNNING")

    assert ensure_npcap_running(run) is True
    assert calls == [["sc", "query", "npcap"]]


def test_ensure_npcap_starts_stopped_service():
    calls = []

    def run(args):
        calls.append(args)
        if ["sc", "start", "npcap"] in calls:
            return (0, "RUNNING")
        return (0, "STOPPED")

    assert ensure_npcap_running(run) is True
    assert ["sc", "start", "npcap"] in calls


def test_list_interfaces_reads_array():
    session = FakeSession({
        "http://radar/api/network/interfaces": FakeResponse(200, [
            {"name": "\\Device\\NPF_{AAA}", "description": "Ethernet"},
            {"description": "no name"},
        ])
    })
    rows = list_interfaces("http://radar", session)
    assert rows[0]["name"] == "\\Device\\NPF_{AAA}"


def test_select_all_interfaces_refreshes_then_posts_all_names():
    session = FakeSession({
        "http://radar/api/network/interfaces": FakeResponse(200, [{"name": "a"}, {"name": "b"}])
    })
    names = select_all_interfaces("http://radar", session)
    assert names == ["a", "b"]
    assert ("POST", "http://radar/api/network/refresh", None) in session.calls
    assert session.calls[-1] == ("POST", "http://radar/api/network/interfaces", {"names": ["a", "b"]})


def test_select_all_interfaces_returns_empty_on_failure():
    session = FakeSession({})
    assert select_all_interfaces("http://radar", session) == []


def test_wait_radar_ready_retries_until_state_available():
    class Clock:
        def __init__(self):
            self.now = 0.0

        def __call__(self):
            return self.now

        def sleep(self, seconds):
            self.now += seconds

    class FlakySession:
        def __init__(self):
            self.calls = 0

        def get(self, url, timeout=None):
            self.calls += 1
            if self.calls >= 3:
                return FakeResponse(200, {"isCapturing": True})
            return FakeResponse(500)

    clock = Clock()
    assert wait_radar_ready("http://radar", timeout=10.0, interval=1.0,
                            session=FlakySession(), sleep=clock.sleep, clock=clock) is True
    assert clock.now == 2.0


def test_wait_radar_ready_times_out():
    clock = type("Clock", (), {"now": 0.0, "__call__": lambda self: self.now,
                               "sleep": lambda self, seconds: setattr(self, "now", self.now + seconds)})()
    assert wait_radar_ready("http://radar", timeout=3.0, interval=1.0,
                            session=FakeSession({}), sleep=clock.sleep, clock=clock) is False


def test_is_silent_threshold():
    assert is_silent(last_activity=100.0, now=130.0) is False
    assert is_silent(last_activity=100.0, now=160.0) is True
    assert is_silent(last_activity=100.0, now=160.0, threshold=30.0) is True


def test_wizard_needed_until_onboarded(tmp_path):
    config = Config(tmp_path / "config.json")
    assert wizard_needed(config) is True
    config.set("onboarded", True)
    assert wizard_needed(config) is False


def test_start_radar_launches_bundled_binary(tmp_path):
    (tmp_path / "OpenRadar.exe").write_bytes(b"MZ")
    launched = []
    assert start_radar(tmp_path, popen=lambda args, cwd=None: launched.append((args, cwd))) is True
    assert launched[0][0] == [str(tmp_path / "OpenRadar.exe")]


def test_start_radar_returns_false_when_binary_missing(tmp_path):
    assert start_radar(tmp_path, popen=lambda args, cwd=None: None) is False

from albion_aware.diagnostics import (
    detect_accelerator,
    parse_process_names,
    report_lines,
    scenario_steps,
)


def test_detect_accelerator_matches_process_names():
    assert detect_accelerator(["Thunder.exe", "chrome.exe"]) == "thunder"
    assert detect_accelerator(["exitlag.exe"]) == "exitlag"
    assert detect_accelerator(["uu.exe"]) == "uu"
    assert detect_accelerator(["explorer.exe", "game.exe"]) is None


def test_scenario_steps_for_accelerator():
    steps = scenario_steps("accelerator", "exitlag")
    assert steps == ["diag.accelerator.exitlag"]
    assert scenario_steps("accelerator", None) == ["diag.accelerator.generic"]


def test_scenario_steps_for_direct_connection():
    steps = scenario_steps("direct")
    assert steps == ["diag.direct.firewall", "diag.direct.process", "diag.direct.restart"]


def test_parse_process_names_reads_tasklist_csv():
    output = (
        '"Thunder.exe","1234","Console","1","12,345 K"\n'
        '"chrome.exe","5678","Console","1","8,900 K"\n'
        "\n"
    )
    assert parse_process_names(output) == ["Thunder.exe", "chrome.exe"]


def test_report_lines_contain_no_player_data():
    report = report_lines(npcap_installed=True, npcap_running=True, radar_status="ok",
                          interface_count=3, accelerator="thunder")
    text = "\n".join(report)
    assert "npcap=installed/running" in text
    assert "radar=ok" in text
    assert "interfaces=3" in text
    assert "accelerator=thunder" in text
    assert "@" not in text          # 不可能混入邮箱等个人信息
    assert "：" not in text          # 不含中文昵称字段

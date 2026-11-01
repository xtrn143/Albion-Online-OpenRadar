import json

from albion_aware.radar_client import next_delay, parse_frames


def test_parse_single_frame():
    raw = json.dumps({"code": "event", "dictionary": {"parameters": {"252": 29, "0": 7}}})
    frames = parse_frames(raw)
    assert frames[0]["code"] == "event"
    assert frames[0]["dictionary"]["parameters"]["0"] == 7


def test_parse_batch_frame():
    raw = json.dumps({"type": "batch", "messages": [
        {"code": "event", "dictionary": {"parameters": {"252": 29, "0": 1}}},
        {"code": "response", "dictionary": {"parameters": {"253": 41, "0": "TNL-001"}}},
    ]})
    frames = parse_frames(raw)
    assert len(frames) == 2
    assert frames[1]["code"] == "response"


def test_dictionary_json_string_is_decoded():
    inner = json.dumps({"parameters": {"252": 1, "0": 42}})
    raw = json.dumps({"code": "event", "dictionary": inner})
    frames = parse_frames(raw)
    assert frames[0]["dictionary"]["parameters"]["0"] == 42


def test_invalid_payloads_return_empty():
    assert parse_frames("not json") == []
    assert parse_frames(json.dumps([1, 2, 3])) == []
    assert parse_frames(json.dumps({"code": "event"})) == []


def test_next_delay_doubles_and_caps():
    assert next_delay(1.0, 30.0) == 2.0
    assert next_delay(4.0, 30.0) == 8.0
    assert next_delay(20.0, 30.0) == 30.0
    assert next_delay(30.0, 30.0) == 30.0

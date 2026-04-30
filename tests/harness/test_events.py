"""Tests for aigernon.harness.events — Event log writer (f1.2)."""

import json
import pytest


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


@pytest.fixture()
def unit():
    from aigernon.harness.unit import create_unit
    return create_unit("Event log test")


# --- hc1: append and read back ---

def test_append_and_read_back(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])

    stored = log.append({"realm": "assess", "kind": "realm_enter"})
    events = log.read()

    assert len(events) == 1
    assert events[0]["id"] == stored["id"]
    assert events[0]["realm"] == "assess"
    assert events[0]["kind"] == "realm_enter"
    assert events[0]["unit_id"] == unit["unit_id"]
    assert "ts" in events[0]


# --- hc2: EventLog is importable as a class ---

def test_import_event_log():
    from aigernon.harness.events import EventLog
    assert callable(EventLog)


# --- hc3: event IDs use ULID prefix ---

def test_event_id_format(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])
    stored = log.append({"realm": "decide", "kind": "plan_committed"})
    assert stored["id"].startswith("evt_")
    assert len(stored["id"]) > 10


# --- sc1: read() returns a list; filtering by realm and kind works ---

def test_read_returns_list(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])
    result = log.read()
    assert isinstance(result, list)


def test_filter_by_realm(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "realm_enter"})
    log.append({"realm": "decide", "kind": "realm_enter"})
    log.append({"realm": "assess", "kind": "realm_exit"})

    assess_events = log.read(realm="assess")
    assert len(assess_events) == 2
    assert all(e["realm"] == "assess" for e in assess_events)


def test_filter_by_kind(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "realm_enter"})
    log.append({"realm": "assess", "kind": "model_call", "data": {"tokens_in": 100}})
    log.append({"realm": "assess", "kind": "realm_exit"})

    model_events = log.read(kind="model_call")
    assert len(model_events) == 1
    assert model_events[0]["data"]["tokens_in"] == 100


def test_filter_by_realm_and_kind(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "realm_enter"})
    log.append({"realm": "decide", "kind": "realm_enter"})

    result = log.read(realm="decide", kind="realm_enter")
    assert len(result) == 1
    assert result[0]["realm"] == "decide"


# --- additional: ordering, optional fields, multiple appends ---

def test_events_preserve_order(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])
    for i in range(5):
        log.append({"realm": "do", "kind": "tool_call", "data": {"i": i}})

    events = log.read()
    indices = [e["data"]["i"] for e in events]
    assert indices == list(range(5))


def test_optional_fields_stored(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])
    stored = log.append({
        "realm": "meta",
        "kind": "unit_archived",
        "session_id": "s_test",
        "parent_event_id": "evt_parent",
        "data": {"reason": "ratify_pass"},
    })
    assert stored["session_id"] == "s_test"
    assert stored["parent_event_id"] == "evt_parent"
    assert stored["data"]["reason"] == "ratify_pass"


def test_empty_log_returns_empty_list(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])
    assert log.read() == []


def test_events_persisted_to_disk(unit):
    from aigernon.harness.events import EventLog
    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "realm_enter"})

    # Re-open and verify
    log2 = EventLog(unit["unit_id"])
    assert len(log2.read()) == 1

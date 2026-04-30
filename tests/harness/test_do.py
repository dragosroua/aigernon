"""Tests for aigernon.harness.do — Claim and artifact module (f1.5)."""

import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


@pytest.fixture()
def unit():
    from aigernon.harness.unit import create_unit
    return create_unit("Do test")


VALID_CLAIM = {
    "summary": "Implemented EventLog with append/read; tests pass.",
    "files_changed": [
        {"path": "aigernon/harness/events.py", "kind": "created"},
    ],
    "tests_run": [
        {"path": "tests/harness/test_events.py", "result": "passed", "count": 11},
    ],
    "self_assessment": {
        "criteria_met_per_self": ["hc1", "hc2", "hc3"],
        "uncertainties": ["Multi-process concurrency not stress-tested"],
    },
}


# --- hc1: artifact_dir returns a writable path ---

def test_artifact_dir_exists(unit):
    from aigernon.harness.do import artifact_dir
    path = artifact_dir(unit["unit_id"])
    assert path.is_dir()


def test_artifact_dir_is_writable(unit):
    from aigernon.harness.do import artifact_dir
    path = artifact_dir(unit["unit_id"])
    test_file = path / "output.txt"
    test_file.write_text("hello")
    assert test_file.read_text() == "hello"


# --- hc2: write_claim writes claim.json ---

def test_write_claim_creates_file(unit):
    from aigernon.harness.do import write_claim
    from aigernon.harness.unit import unit_path
    write_claim(unit["unit_id"], VALID_CLAIM)
    assert (unit_path(unit["unit_id"]) / "do" / "claim.json").exists()


def test_write_claim_auto_fields(unit):
    from aigernon.harness.do import write_claim
    stored = write_claim(unit["unit_id"], VALID_CLAIM, claimed_by="model:claude-sonnet")
    assert stored["unit_id"] == unit["unit_id"]
    assert stored["claimed_by"] == "model:claude-sonnet"
    assert "claimed_at" in stored


# --- hc3: read_claim round-trips correctly ---

def test_read_claim_round_trip(unit):
    from aigernon.harness.do import write_claim, read_claim
    stored = write_claim(unit["unit_id"], VALID_CLAIM)
    fetched = read_claim(unit["unit_id"])
    assert fetched == stored


def test_read_claim_none_when_empty(unit):
    from aigernon.harness.do import read_claim
    assert read_claim(unit["unit_id"]) is None


# --- hc4: claim content is preserved ---

def test_claim_content_preserved(unit):
    from aigernon.harness.do import write_claim, read_claim
    write_claim(unit["unit_id"], VALID_CLAIM)
    fetched = read_claim(unit["unit_id"])
    assert fetched["summary"] == VALID_CLAIM["summary"]
    assert fetched["files_changed"] == VALID_CLAIM["files_changed"]
    assert fetched["self_assessment"]["criteria_met_per_self"] == ["hc1", "hc2", "hc3"]


# --- overwrite: second write replaces first ---

def test_write_claim_overwrites(unit):
    from aigernon.harness.do import write_claim, read_claim
    write_claim(unit["unit_id"], VALID_CLAIM)
    write_claim(unit["unit_id"], {**VALID_CLAIM, "summary": "Updated summary"})
    assert read_claim(unit["unit_id"])["summary"] == "Updated summary"

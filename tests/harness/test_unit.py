"""Tests for aigernon.harness.unit — Unit directory scaffolding (f1.1)."""

import json
import pytest


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    """Redirect all unit storage to a temp dir so tests don't touch ~/.aigernon."""
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


# --- f1.1 hc1: create_unit produces the correct directory structure ---

def test_create_unit_directory_structure(tmp_path):
    from aigernon.harness.unit import create_unit, _units_dir
    meta = create_unit("Add a hello() function")
    unit_id = meta["unit_id"]
    base = _units_dir() / unit_id

    assert (base / "meta.json").exists()
    assert (base / "assess").is_dir()
    assert (base / "decide").is_dir()
    assert (base / "do" / "artifact").is_dir()
    assert (base / "events.jsonl").exists()
    assert (base / "substrate.md").exists()


# --- f1.1 hc2: meta.json has correct initial shape ---

def test_create_unit_meta_fields():
    from aigernon.harness.unit import create_unit
    meta = create_unit("Test goal", parent_unit_id="u_2026-01-01_abcd")

    assert meta["unit_id"].startswith("u_")
    assert len(meta["unit_id"]) == len("u_2026-04-30_a3f2")
    assert meta["goal"] == "Test goal"
    assert meta["status"] == "assessing"
    assert meta["parent_unit_id"] == "u_2026-01-01_abcd"
    assert "created_at" in meta
    assert "updated_at" in meta


def test_create_unit_meta_persisted():
    from aigernon.harness.unit import create_unit, _units_dir
    meta = create_unit("Persisted goal")
    on_disk = json.loads((_units_dir() / meta["unit_id"] / "meta.json").read_text())
    assert on_disk == meta


# --- f1.1 hc3: get_unit round-trips correctly ---

def test_get_unit_returns_meta():
    from aigernon.harness.unit import create_unit, get_unit
    meta = create_unit("Round-trip")
    assert get_unit(meta["unit_id"]) == meta


def test_get_unit_missing_returns_none():
    from aigernon.harness.unit import get_unit
    assert get_unit("u_0000-00-00_xxxx") is None


# --- f1.1 hc4: status transitions are enforced ---

def test_valid_transition_chain():
    from aigernon.harness.unit import create_unit, update_status
    meta = create_unit("Transition test")
    uid = meta["unit_id"]

    meta = update_status(uid, "deciding")
    assert meta["status"] == "deciding"

    meta = update_status(uid, "doing")
    assert meta["status"] == "doing"

    meta = update_status(uid, "ratifying")
    assert meta["status"] == "ratifying"

    meta = update_status(uid, "archived")
    assert meta["status"] == "archived"


def test_reassess_path():
    from aigernon.harness.unit import create_unit, update_status
    meta = create_unit("Reassess path")
    uid = meta["unit_id"]
    update_status(uid, "deciding")
    update_status(uid, "doing")
    update_status(uid, "ratifying")
    meta = update_status(uid, "reassessing")
    assert meta["status"] == "reassessing"
    meta = update_status(uid, "deciding")
    assert meta["status"] == "deciding"


def test_invalid_transition_raises():
    from aigernon.harness.unit import create_unit, update_status
    meta = create_unit("Invalid transition")
    with pytest.raises(ValueError, match="Cannot transition"):
        update_status(meta["unit_id"], "archived")  # assessing → archived is not allowed


def test_update_status_persists():
    from aigernon.harness.unit import create_unit, update_status, get_unit
    meta = create_unit("Persist status")
    update_status(meta["unit_id"], "deciding")
    assert get_unit(meta["unit_id"])["status"] == "deciding"


# --- f1.1 hc5: list_units works with optional status filter ---

def test_list_units_all():
    from aigernon.harness.unit import create_unit, list_units
    create_unit("Goal A")
    create_unit("Goal B")
    assert len(list_units()) == 2


def test_list_units_filtered():
    from aigernon.harness.unit import create_unit, list_units, update_status
    m1 = create_unit("Goal A")
    m2 = create_unit("Goal B")
    update_status(m2["unit_id"], "deciding")

    assessing = list_units(status="assessing")
    assert len(assessing) == 1
    assert assessing[0]["unit_id"] == m1["unit_id"]

    deciding = list_units(status="deciding")
    assert len(deciding) == 1
    assert deciding[0]["unit_id"] == m2["unit_id"]


def test_list_units_empty(tmp_path):
    from aigernon.harness.unit import list_units
    assert list_units() == []

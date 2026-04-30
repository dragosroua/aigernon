"""Tests for aigernon.harness.criteria — Criteria contract module (f1.3)."""

import json
import pytest


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


@pytest.fixture()
def unit():
    from aigernon.harness.unit import create_unit
    return create_unit("Criteria test")


VALID_CRITERIA = {
    "goal": "Add hello() to scratch.py",
    "context": "Phase 1 test",
    "hard_criteria": [
        {"id": "hc1", "type": "file_exists", "spec": "aigernon/scratch.py"},
    ],
    "soft_criteria": [
        {"id": "sc1", "description": "Function is named hello", "rubric": "Pass if def hello exists"},
    ],
    "out_of_scope": ["error handling"],
}


# --- hc1: write and read back ---

def test_write_and_read_criteria(unit):
    from aigernon.harness.criteria import write_criteria, read_criteria
    stored = write_criteria(unit["unit_id"], VALID_CRITERIA)
    fetched = read_criteria(unit["unit_id"])
    assert fetched == stored


# --- hc2: versioning ---

def test_first_write_is_version_1(unit):
    from aigernon.harness.criteria import write_criteria
    stored = write_criteria(unit["unit_id"], VALID_CRITERIA)
    assert stored["version"] == 1
    assert stored["supersedes_version"] is None


def test_second_write_is_version_2(unit):
    from aigernon.harness.criteria import write_criteria, read_criteria
    write_criteria(unit["unit_id"], VALID_CRITERIA)
    v2 = write_criteria(unit["unit_id"], VALID_CRITERIA, reassess_reason="sc1 was ambiguous")
    assert v2["version"] == 2
    assert v2["supersedes_version"] == 1
    assert v2["reassess_reason"] == "sc1 was ambiguous"


def test_read_specific_version(unit):
    from aigernon.harness.criteria import write_criteria, read_criteria
    v1 = write_criteria(unit["unit_id"], {**VALID_CRITERIA, "goal": "Goal v1"})
    write_criteria(unit["unit_id"], {**VALID_CRITERIA, "goal": "Goal v2"})

    fetched_v1 = read_criteria(unit["unit_id"], version=1)
    assert fetched_v1["goal"] == "Goal v1"
    assert fetched_v1["version"] == 1


def test_read_latest_by_default(unit):
    from aigernon.harness.criteria import write_criteria, read_criteria
    write_criteria(unit["unit_id"], VALID_CRITERIA)
    write_criteria(unit["unit_id"], {**VALID_CRITERIA, "goal": "Goal v2"})
    fetched = read_criteria(unit["unit_id"])
    assert fetched["version"] == 2


def test_read_criteria_none_when_empty(unit):
    from aigernon.harness.criteria import read_criteria
    assert read_criteria(unit["unit_id"]) is None


# --- hc3: metadata is auto-populated ---

def test_committed_at_and_by_set(unit):
    from aigernon.harness.criteria import write_criteria
    stored = write_criteria(unit["unit_id"], VALID_CRITERIA, committed_by="model:claude-sonnet")
    assert stored["committed_by"] == "model:claude-sonnet"
    assert "committed_at" in stored


# --- hc4: validation ---

def test_validate_requires_goal(unit):
    from aigernon.harness.criteria import write_criteria
    bad = {**VALID_CRITERIA, "goal": ""}
    with pytest.raises(ValueError, match="goal"):
        write_criteria(unit["unit_id"], bad)


def test_validate_requires_hard_criteria(unit):
    from aigernon.harness.criteria import write_criteria
    bad = {**VALID_CRITERIA, "hard_criteria": []}
    with pytest.raises(ValueError, match="hard criterion"):
        write_criteria(unit["unit_id"], bad)


def test_validate_hard_criterion_fields(unit):
    from aigernon.harness.criteria import write_criteria
    bad = {**VALID_CRITERIA, "hard_criteria": [{"id": "hc1"}]}  # missing type and spec
    with pytest.raises(ValueError, match="missing"):
        write_criteria(unit["unit_id"], bad)


def test_version_count(unit):
    from aigernon.harness.criteria import write_criteria, criteria_version_count
    assert criteria_version_count(unit["unit_id"]) == 0
    write_criteria(unit["unit_id"], VALID_CRITERIA)
    assert criteria_version_count(unit["unit_id"]) == 1
    write_criteria(unit["unit_id"], VALID_CRITERIA)
    assert criteria_version_count(unit["unit_id"]) == 2

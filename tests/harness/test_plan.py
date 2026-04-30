"""Tests for aigernon.harness.plan — Plan module (f1.4)."""

import pytest


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


@pytest.fixture()
def unit():
    from aigernon.harness.unit import create_unit
    return create_unit("Plan test")


VALID_PLAN = {
    "approach": "Implement EventLog as thin JSONL wrapper",
    "alternatives_considered": [
        {"name": "SQLite", "rejected_because": "Unnecessary dependency"},
    ],
    "steps": [
        {"id": "s1", "description": "Create skeleton", "estimated_tool_calls": 3},
        {"id": "s2", "description": "Implement class", "estimated_tool_calls": 8, "depends_on": ["s1"]},
    ],
    "budgets": {
        "max_tokens": 80000,
        "max_tool_calls": 40,
        "max_wall_seconds": 1200,
        "max_dollars": 1.50,
    },
    "tools_authorized": ["view", "create_file", "str_replace"],
}


# --- hc1: write and read back ---

def test_write_and_read_plan(unit):
    from aigernon.harness.plan import write_plan, read_plan
    stored = write_plan(unit["unit_id"], VALID_PLAN)
    fetched = read_plan(unit["unit_id"])
    assert fetched == stored


# --- hc2: versioning ---

def test_first_write_is_version_1(unit):
    from aigernon.harness.plan import write_plan
    stored = write_plan(unit["unit_id"], VALID_PLAN)
    assert stored["version"] == 1


def test_second_write_is_version_2(unit):
    from aigernon.harness.plan import write_plan
    write_plan(unit["unit_id"], VALID_PLAN)
    v2 = write_plan(unit["unit_id"], {**VALID_PLAN, "approach": "Revised approach"})
    assert v2["version"] == 2


def test_read_specific_version(unit):
    from aigernon.harness.plan import write_plan, read_plan
    write_plan(unit["unit_id"], {**VALID_PLAN, "approach": "Approach v1"})
    write_plan(unit["unit_id"], {**VALID_PLAN, "approach": "Approach v2"})
    assert read_plan(unit["unit_id"], version=1)["approach"] == "Approach v1"


def test_read_latest_by_default(unit):
    from aigernon.harness.plan import write_plan, read_plan
    write_plan(unit["unit_id"], VALID_PLAN)
    write_plan(unit["unit_id"], {**VALID_PLAN, "approach": "Approach v2"})
    assert read_plan(unit["unit_id"])["version"] == 2


def test_read_plan_none_when_empty(unit):
    from aigernon.harness.plan import read_plan
    assert read_plan(unit["unit_id"]) is None


# --- hc3: metadata auto-populated ---

def test_committed_at_and_by_set(unit):
    from aigernon.harness.plan import write_plan
    stored = write_plan(unit["unit_id"], VALID_PLAN, committed_by="model:claude-sonnet")
    assert stored["committed_by"] == "model:claude-sonnet"
    assert "committed_at" in stored
    assert stored["unit_id"] == unit["unit_id"]


# --- hc4: validation ---

def test_validate_requires_approach(unit):
    from aigernon.harness.plan import write_plan
    bad = {**VALID_PLAN, "approach": ""}
    with pytest.raises(ValueError, match="approach"):
        write_plan(unit["unit_id"], bad)


def test_validate_requires_budgets(unit):
    from aigernon.harness.plan import write_plan
    bad = {k: v for k, v in VALID_PLAN.items() if k != "budgets"}
    with pytest.raises(ValueError, match="budgets"):
        write_plan(unit["unit_id"], bad)


def test_validate_budget_keys(unit):
    from aigernon.harness.plan import write_plan
    bad = {**VALID_PLAN, "budgets": {"max_tokens": 100}}  # missing other keys
    with pytest.raises(ValueError, match="missing keys"):
        write_plan(unit["unit_id"], bad)


def test_version_count(unit):
    from aigernon.harness.plan import write_plan, plan_version_count
    assert plan_version_count(unit["unit_id"]) == 0
    write_plan(unit["unit_id"], VALID_PLAN)
    assert plan_version_count(unit["unit_id"]) == 1

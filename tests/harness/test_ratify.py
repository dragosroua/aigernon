"""Tests for aigernon.harness.ratify — Ratify module (f1.7)."""

import json
import pytest


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


@pytest.fixture()
def unit():
    from aigernon.harness.unit import create_unit
    return create_unit("Ratify test")


def _write_criteria(unit_id, hard=None, soft=None):
    from aigernon.harness.criteria import write_criteria
    return write_criteria(unit_id, {
        "goal": "Test goal",
        "hard_criteria": hard or [{"id": "hc1", "type": "file_exists", "spec": __file__}],
        "soft_criteria": soft or [],
        "out_of_scope": [],
    })


def _write_claim(unit_id):
    from aigernon.harness.do import write_claim
    return write_claim(unit_id, {
        "summary": "Implemented the thing.",
        "files_changed": [],
        "tests_run": [],
        "self_assessment": {"criteria_met_per_self": ["hc1"], "uncertainties": []},
    })


# --- hc1: hard criterion file_exists ---

@pytest.mark.asyncio
async def test_ratify_file_exists_pass(unit):
    from aigernon.harness.ratify import ratify
    _write_criteria(unit["unit_id"], hard=[
        {"id": "hc1", "type": "file_exists", "spec": __file__}
    ])
    _write_claim(unit["unit_id"])
    record = await ratify(unit["unit_id"])
    assert record["results"]["hc1"]["pass"] is True
    assert record["outcome"] == "pass"


@pytest.mark.asyncio
async def test_ratify_file_exists_fail(unit):
    from aigernon.harness.ratify import ratify
    _write_criteria(unit["unit_id"], hard=[
        {"id": "hc1", "type": "file_exists", "spec": "/this/does/not/exist.py"}
    ])
    _write_claim(unit["unit_id"])
    record = await ratify(unit["unit_id"])
    assert record["results"]["hc1"]["pass"] is False
    assert record["outcome"] == "fail"


# --- hc2: hard criterion import_succeeds ---

@pytest.mark.asyncio
async def test_ratify_import_succeeds_pass(unit):
    from aigernon.harness.ratify import ratify
    _write_criteria(unit["unit_id"], hard=[
        {"id": "hc1", "type": "import_succeeds", "spec": "aigernon.harness.unit"}
    ])
    _write_claim(unit["unit_id"])
    record = await ratify(unit["unit_id"])
    assert record["results"]["hc1"]["pass"] is True


@pytest.mark.asyncio
async def test_ratify_import_fails(unit):
    from aigernon.harness.ratify import ratify
    _write_criteria(unit["unit_id"], hard=[
        {"id": "hc1", "type": "import_succeeds", "spec": "nonexistent.module.xyz"}
    ])
    _write_claim(unit["unit_id"])
    record = await ratify(unit["unit_id"])
    assert record["results"]["hc1"]["pass"] is False


# --- hc3: ratify.json is written ---

@pytest.mark.asyncio
async def test_ratify_writes_json(unit):
    from aigernon.harness.ratify import ratify, read_ratify
    _write_criteria(unit["unit_id"])
    _write_claim(unit["unit_id"])
    record = await ratify(unit["unit_id"])
    on_disk = read_ratify(unit["unit_id"])
    assert on_disk is not None
    assert on_disk["unit_id"] == unit["unit_id"]
    assert on_disk["outcome"] == record["outcome"]


# --- hc4: missing criteria/claim produce fail ---

@pytest.mark.asyncio
async def test_ratify_no_criteria(unit):
    from aigernon.harness.ratify import ratify
    record = await ratify(unit["unit_id"])
    assert record["outcome"] == "fail"
    assert "criteria" in record["fail_reason"].lower()


@pytest.mark.asyncio
async def test_ratify_no_claim(unit):
    from aigernon.harness.ratify import ratify
    _write_criteria(unit["unit_id"])
    record = await ratify(unit["unit_id"])
    assert record["outcome"] == "fail"
    assert "claim" in record["fail_reason"].lower()


# --- hc5: next_action is correct ---

@pytest.mark.asyncio
async def test_ratify_pass_next_action_archive(unit):
    from aigernon.harness.ratify import ratify
    _write_criteria(unit["unit_id"])
    _write_claim(unit["unit_id"])
    record = await ratify(unit["unit_id"])
    if record["outcome"] == "pass":
        assert record["next_action"] == "archive"
    else:
        assert record["next_action"] == "reassess"


# --- hc6: multiple hard criteria, one fail → overall fail ---

@pytest.mark.asyncio
async def test_ratify_one_fail_means_overall_fail(unit):
    from aigernon.harness.ratify import ratify
    _write_criteria(unit["unit_id"], hard=[
        {"id": "hc1", "type": "file_exists", "spec": __file__},
        {"id": "hc2", "type": "file_exists", "spec": "/does/not/exist.py"},
    ])
    _write_claim(unit["unit_id"])
    record = await ratify(unit["unit_id"])
    assert record["results"]["hc1"]["pass"] is True
    assert record["results"]["hc2"]["pass"] is False
    assert record["outcome"] == "fail"
    assert "hc2" in record["fail_reason"]


# --- hc7: judge model resolution ---

def test_resolve_judge_model_fallback(unit):
    from aigernon.harness.ratify import _resolve_judge_model, _DEFAULT_JUDGE_MODEL
    # No plan written, no config override → falls back to default
    model = _resolve_judge_model(unit["unit_id"])
    assert model == _DEFAULT_JUDGE_MODEL


def test_resolve_judge_model_from_plan(unit):
    from aigernon.harness.plan import write_plan
    from aigernon.harness.ratify import _resolve_judge_model
    write_plan(unit["unit_id"], {
        "approach": "Test",
        "budgets": {"max_tokens": 100, "max_tool_calls": 10, "max_wall_seconds": 60, "max_dollars": 0.10},
        "judge_model": "openai/gpt-4o-mini",
    })
    assert _resolve_judge_model(unit["unit_id"]) == "openai/gpt-4o-mini"

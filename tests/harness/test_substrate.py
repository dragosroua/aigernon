"""Tests for aigernon.harness.substrate — Substrate writer (f1.6)."""

import pytest


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


@pytest.fixture()
def unit():
    from aigernon.harness.unit import create_unit
    return create_unit("Substrate test goal")


# --- hc1: init_substrate writes header ---

def test_init_substrate_writes_header(unit):
    from aigernon.harness.substrate import init_substrate, read_substrate
    init_substrate(unit["unit_id"], unit["goal"])
    content = read_substrate(unit["unit_id"])
    assert unit["unit_id"] in content
    assert unit["goal"] in content


def test_init_substrate_idempotent(unit):
    from aigernon.harness.substrate import init_substrate, read_substrate
    init_substrate(unit["unit_id"], unit["goal"])
    init_substrate(unit["unit_id"], unit["goal"])  # second call should not double-write
    content = read_substrate(unit["unit_id"])
    assert content.count(unit["unit_id"]) == 1


# --- hc2: append_section produces correct Markdown ---

def test_append_section_structure(unit):
    from aigernon.harness.substrate import append_section, read_substrate
    append_section(unit["unit_id"], "assess", "Starting", "Exploring the goal.")
    content = read_substrate(unit["unit_id"])
    assert "## [Assess] Starting" in content
    assert "Exploring the goal." in content
    assert "---" in content


def test_append_section_multiple_realms(unit):
    from aigernon.harness.substrate import append_section, read_substrate
    append_section(unit["unit_id"], "assess", "Entry", "Assess body.")
    append_section(unit["unit_id"], "decide", "Entry", "Decide body.")
    append_section(unit["unit_id"], "do", "Entry", "Do body.")
    content = read_substrate(unit["unit_id"])
    assert "[Assess]" in content
    assert "[Decide]" in content
    assert "[Do]" in content
    # Order is preserved
    assert content.index("[Assess]") < content.index("[Decide]") < content.index("[Do]")


def test_append_ratify_outcome_pass(unit):
    from aigernon.harness.substrate import append_ratify_outcome, read_substrate
    append_ratify_outcome(unit["unit_id"], "pass", "All criteria met.")
    content = read_substrate(unit["unit_id"])
    assert "PASS" in content
    assert "All criteria met." in content


def test_append_ratify_outcome_fail(unit):
    from aigernon.harness.substrate import append_ratify_outcome, read_substrate
    append_ratify_outcome(unit["unit_id"], "fail", "sc1 failed.")
    content = read_substrate(unit["unit_id"])
    assert "FAIL" in content
    assert "sc1 failed." in content


# --- hc3: read_substrate returns full content ---

def test_read_substrate_empty(unit):
    from aigernon.harness.substrate import read_substrate
    # File exists but is empty (created by create_unit)
    assert read_substrate(unit["unit_id"]) == ""


def test_read_substrate_after_writes(unit):
    from aigernon.harness.substrate import init_substrate, append_section, read_substrate
    init_substrate(unit["unit_id"], "Goal")
    append_section(unit["unit_id"], "assess", "Test", "Body text here.")
    content = read_substrate(unit["unit_id"])
    assert "Body text here." in content

"""Tests for Phase 2 — re-Assess loop, imbalance detection, unit inspection.

Covers: f2.1 (re-Assess routing), f2.2 (re-Assess bound),
        f2.3 (imbalance detector), f2.4 (substrate-aware prompt),
        f2.5 (unit list/show CLI).
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


@pytest.fixture()
def unit():
    from aigernon.harness.unit import create_unit
    return create_unit("Phase 2 test goal")


# ===========================================================================
# f2.1 + f2.2 — re-Assess routing and bound
# ===========================================================================

def _make_mock_agent(responses: list[str]):
    """Return an agent_loop mock that returns each response in sequence."""
    loop = MagicMock()
    loop.process_direct = AsyncMock(side_effect=responses)
    return loop


def _write_criteria_file(unit_id: str, version: int, tmp_path):
    """Write a criteria file directly, bypassing the agent."""
    from aigernon.harness.unit import unit_path as up
    path = up(unit_id) / "assess" / f"criteria_v{version}.json"
    path.write_text(json.dumps({
        "goal": "Test goal",
        "context": "",
        "hard_criteria": [{"id": "hc1", "type": "file_exists", "spec": str(path)}],
        "soft_criteria": [],
        "out_of_scope": [],
        "version": version,
        "committed_at": "2026-04-30T00:00:00+00:00",
        "committed_by": "test",
        "supersedes_version": version - 1 if version > 1 else None,
        "reassess_reason": None,
    }))


def _write_plan_file(unit_id: str, version: int):
    from aigernon.harness.unit import unit_path as up
    path = up(unit_id) / "decide" / f"plan_v{version}.json"
    path.write_text(json.dumps({
        "approach": "test approach",
        "alternatives_considered": [],
        "steps": [{"id": "s1", "description": "step", "estimated_tool_calls": 1}],
        "budgets": {"max_tokens": 1000, "max_tool_calls": 10, "max_wall_seconds": 60, "max_dollars": 0.10},
        "tools_authorized": ["view"],
        "version": version,
        "committed_at": "2026-04-30T00:00:00+00:00",
        "committed_by": "test",
    }))


def _write_claim_file(unit_id: str):
    from aigernon.harness.unit import unit_path as up
    path = up(unit_id) / "do" / "claim.json"
    path.write_text(json.dumps({
        "unit_id": unit_id,
        "summary": "done",
        "files_changed": [],
        "tests_run": [],
        "self_assessment": {"criteria_met_per_self": ["hc1"], "uncertainties": []},
        "claimed_at": "2026-04-30T00:00:00+00:00",
        "claimed_by": "test",
    }))


def _uid_from_msg(msg: str) -> str:
    """Extract unit_id from a harness realm prompt."""
    for line in msg.splitlines():
        if line.startswith("Unit ID:"):
            return line.split(":", 1)[1].strip()
    return ""


def _make_writer(tmp_path):
    """Return an async agent side_effect that writes the realm-appropriate file."""

    async def write_and_respond(msg, session_id):
        uid = _uid_from_msg(msg)
        if not uid:
            return "ok"
        from aigernon.harness.criteria import criteria_version_count
        from aigernon.harness.plan import plan_version_count
        if "Assess realm" in msg or "re-Assess realm" in msg:
            cv = criteria_version_count(uid) + 1
            _write_criteria_file(uid, cv, tmp_path)
        elif "Decide realm" in msg:
            pv = plan_version_count(uid) + 1
            _write_plan_file(uid, pv)
        elif "Do realm" in msg:
            _write_claim_file(uid)
        return "ok"

    return write_and_respond


@pytest.mark.asyncio
async def test_reassess_count_increments_on_ratify_fail(tmp_path):
    """After a Ratify fail, reassess_count should be incremented."""
    from aigernon.harness.loop import run_unit
    from aigernon.harness.unit import get_unit

    call_count = [0]
    seen_unit = [None]

    async def fake_ratify(unit_id):
        seen_unit[0] = unit_id
        call_count[0] += 1
        if call_count[0] == 1:
            return {"outcome": "fail", "fail_reason": "test fail", "reassess_advice": "fix it",
                    "next_action": "reassess", "results": {}, "checked_at": "", "checked_by": "test",
                    "unit_id": unit_id, "checked_against_criteria_version": 1}
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 2}

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer(tmp_path))

    with patch("aigernon.harness.loop.ratify", side_effect=fake_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=Path("/tmp")):
        result = await run_unit("Phase 2 test", agent)

    assert call_count[0] == 2
    assert result["outcome"] == "pass"
    assert get_unit(seen_unit[0])["reassess_count"] == 1


@pytest.mark.asyncio
async def test_escalation_after_max_reassess(tmp_path):
    """After max_reassess failures, outcome should be 'escalated'."""
    from aigernon.harness.loop import run_unit

    async def always_fail_ratify(unit_id):
        return {"outcome": "fail", "fail_reason": "persistent fail", "reassess_advice": "try harder",
                "next_action": "reassess", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer(tmp_path))

    with patch("aigernon.harness.loop.ratify", side_effect=always_fail_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=Path("/tmp")):
        result = await run_unit("Escalation test", agent, max_reassess=2)

    assert result["outcome"] == "escalated"


@pytest.mark.asyncio
async def test_human_pause_event_on_escalation(tmp_path):
    """Escalation must write a human_pause event to the event log."""
    from aigernon.harness.loop import run_unit
    from aigernon.harness.events import EventLog

    async def always_fail(unit_id):
        return {"outcome": "fail", "fail_reason": "x", "reassess_advice": "y",
                "next_action": "reassess", "results": {}, "checked_at": "", "checked_by": "t",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer(tmp_path))

    with patch("aigernon.harness.loop.ratify", side_effect=always_fail), \
         patch("aigernon.harness.loop._archive_unit", return_value=Path("/tmp")):
        result = await run_unit("Human pause test", agent, max_reassess=1)

    uid = result["unit_id"]
    log = EventLog(uid)
    pause_events = log.read(kind="human_pause")
    assert len(pause_events) == 1
    assert pause_events[0]["data"]["reason"] == "max_reassess_reached"


# ===========================================================================
# f2.3 — Imbalance detector
# ===========================================================================

def test_no_imbalance_on_fresh_unit(unit):
    from aigernon.harness.imbalance import detect_imbalances
    assert detect_imbalances(unit["unit_id"]) == []


def test_stuck_in_assess_detected(unit):
    from aigernon.harness.events import EventLog
    from aigernon.harness.imbalance import detect_imbalances, _STUCK_REALM_THRESHOLD

    log = EventLog(unit["unit_id"])
    for _ in range(_STUCK_REALM_THRESHOLD):
        log.append({"realm": "assess", "kind": "realm_enter"})
    # No criteria_committed

    imbalances = detect_imbalances(unit["unit_id"])
    patterns = [i["pattern"] for i in imbalances]
    assert "stuck_in_assess" in patterns


def test_no_stuck_in_assess_when_criteria_committed(unit):
    from aigernon.harness.events import EventLog
    from aigernon.harness.imbalance import detect_imbalances

    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "realm_enter"})
    log.append({"realm": "assess", "kind": "criteria_committed", "data": {"version": 1}})

    imbalances = detect_imbalances(unit["unit_id"])
    patterns = [i["pattern"] for i in imbalances]
    assert "stuck_in_assess" not in patterns


def test_stuck_in_decide_detected(unit):
    from aigernon.harness.events import EventLog
    from aigernon.harness.imbalance import detect_imbalances, _STUCK_REALM_THRESHOLD

    log = EventLog(unit["unit_id"])
    for _ in range(_STUCK_REALM_THRESHOLD):
        log.append({"realm": "decide", "kind": "realm_enter"})

    imbalances = detect_imbalances(unit["unit_id"])
    patterns = [i["pattern"] for i in imbalances]
    assert "stuck_in_decide" in patterns


def test_stuck_in_do_detected(unit):
    from aigernon.harness.events import EventLog
    from aigernon.harness.imbalance import detect_imbalances, _STUCK_DO_TOOL_THRESHOLD

    log = EventLog(unit["unit_id"])
    for _ in range(_STUCK_DO_TOOL_THRESHOLD):
        log.append({"realm": "do", "kind": "tool_call"})

    imbalances = detect_imbalances(unit["unit_id"])
    patterns = [i["pattern"] for i in imbalances]
    assert "stuck_in_do" in patterns


def test_no_stuck_in_do_when_claim_complete(unit):
    from aigernon.harness.events import EventLog
    from aigernon.harness.imbalance import detect_imbalances, _STUCK_DO_TOOL_THRESHOLD

    log = EventLog(unit["unit_id"])
    for _ in range(_STUCK_DO_TOOL_THRESHOLD):
        log.append({"realm": "do", "kind": "tool_call"})
    log.append({"realm": "do", "kind": "do_claim_complete"})

    imbalances = detect_imbalances(unit["unit_id"])
    patterns = [i["pattern"] for i in imbalances]
    assert "stuck_in_do" not in patterns


def test_rapid_reassess_detected(unit):
    from aigernon.harness.unit import increment_reassess_count
    from aigernon.harness.imbalance import detect_imbalances, _RAPID_REASSESS_WARN_AT

    for _ in range(_RAPID_REASSESS_WARN_AT):
        increment_reassess_count(unit["unit_id"])

    imbalances = detect_imbalances(unit["unit_id"])
    patterns = [i["pattern"] for i in imbalances]
    assert "rapid_reassess" in patterns


# ===========================================================================
# f2.4 — Substrate-aware re-Assess prompt
# ===========================================================================

def test_reassess_prompt_includes_substrate(unit):
    from aigernon.harness.loop import _reassess_prompt
    from aigernon.harness.unit import unit_path as up

    substrate = "## [Assess] Starting\nSome journey text.\n"
    criteria = {"goal": "test", "version": 1, "hard_criteria": [], "soft_criteria": []}
    advice = "sc1 rubric was ambiguous"

    prompt = _reassess_prompt(
        unit["unit_id"], "test goal", up(unit["unit_id"]),
        criteria_version=2,
        prior_criteria=criteria,
        substrate=substrate,
        reassess_advice=advice,
        reassess_count=1,
        max_reassess=3,
    )

    assert "sc1 rubric was ambiguous" in prompt
    assert "Some journey text." in prompt
    assert "criteria_v2.json" in prompt
    assert "re-Assess attempt 1 of 3" in prompt


def test_reassess_prompt_includes_prior_criteria(unit):
    from aigernon.harness.loop import _reassess_prompt
    from aigernon.harness.unit import unit_path as up

    criteria = {"goal": "original goal", "version": 1, "hard_criteria": [], "soft_criteria": []}
    prompt = _reassess_prompt(
        unit["unit_id"], "test", up(unit["unit_id"]),
        criteria_version=2, prior_criteria=criteria,
        substrate="", reassess_advice="", reassess_count=1, max_reassess=3,
    )
    assert "original goal" in prompt


# ===========================================================================
# f2.1 — reassess_count in unit meta
# ===========================================================================

def test_increment_reassess_count(unit):
    from aigernon.harness.unit import increment_reassess_count, get_unit
    assert get_unit(unit["unit_id"])["reassess_count"] == 0
    increment_reassess_count(unit["unit_id"])
    assert get_unit(unit["unit_id"])["reassess_count"] == 1
    increment_reassess_count(unit["unit_id"])
    assert get_unit(unit["unit_id"])["reassess_count"] == 2


def test_create_unit_has_reassess_count(unit):
    assert unit["reassess_count"] == 0

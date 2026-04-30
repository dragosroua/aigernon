"""Tests for Phase 5 — scheduler, notifier, sub-unit composition, human-in-the-loop.

Covers: f5.1 (HarnessScheduler), f5.2 (HarnessNotifier), f5.3 (schedule CLI),
        f5.4 (sub-unit composition / children_passed), f5.5 (human-required pause/resume).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


@pytest.fixture()
def unit():
    from aigernon.harness.unit import create_unit
    return create_unit("Phase 5 test goal")


# ===========================================================================
# Helpers (shared across tests)
# ===========================================================================

def _write_criteria_file(unit_id, version, children_passed_spec=None):
    from aigernon.harness.unit import unit_path as up
    hard_criteria = [{"id": "hc1", "type": "file_exists",
                      "spec": str(up(unit_id) / "assess" / f"criteria_v{version}.json")}]
    if children_passed_spec:
        hard_criteria.append({"id": "hc_children", "type": "children_passed",
                               "spec": children_passed_spec})
    path = up(unit_id) / "assess" / f"criteria_v{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "goal": "test", "context": "", "version": version,
        "hard_criteria": hard_criteria,
        "soft_criteria": [], "out_of_scope": [],
        "committed_at": "2026-04-30T00:00:00+00:00", "committed_by": "test",
        "supersedes_version": None, "reassess_reason": None,
    }))


def _write_plan_file(unit_id, version, human_required_steps=None):
    from aigernon.harness.unit import unit_path as up
    steps = [{"id": "s1", "description": "step", "estimated_tool_calls": 1}]
    if human_required_steps:
        for step_id in human_required_steps:
            steps.append({"id": step_id, "description": f"Human step {step_id}",
                          "estimated_tool_calls": 0, "human_required": True})
    path = up(unit_id) / "decide" / f"plan_v{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "approach": "test", "alternatives_considered": [],
        "steps": steps,
        "budgets": {"max_tokens": 1000, "max_tool_calls": 10,
                    "max_wall_seconds": 60, "max_dollars": 0.10},
        "tools_authorized": ["view"], "version": version,
        "committed_at": "2026-04-30T00:00:00+00:00", "committed_by": "test",
    }))


def _write_claim_file(unit_id):
    from aigernon.harness.unit import unit_path as up
    path = up(unit_id) / "do" / "claim.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "unit_id": unit_id, "summary": "done", "files_changed": [], "tests_run": [],
        "self_assessment": {"criteria_met_per_self": ["hc1"], "uncertainties": []},
        "claimed_at": "2026-04-30T00:00:00+00:00", "claimed_by": "test",
    }))


def _uid_from_msg(msg):
    for line in msg.splitlines():
        if line.startswith("Unit ID:"):
            return line.split(":", 1)[1].strip()
    return ""


def _make_writer():
    async def write_and_respond(msg, session_id):
        uid = _uid_from_msg(msg)
        if not uid:
            return "ok"
        from aigernon.harness.criteria import criteria_version_count
        from aigernon.harness.plan import plan_version_count
        if "Assess realm" in msg or "re-Assess realm" in msg:
            cv = criteria_version_count(uid) + 1
            _write_criteria_file(uid, cv)
        elif "Decide realm" in msg:
            pv = plan_version_count(uid) + 1
            _write_plan_file(uid, pv)
        elif "Do realm" in msg:
            _write_claim_file(uid)
        return "ok"
    return write_and_respond


# ===========================================================================
# f5.1 — HarnessScheduler
# ===========================================================================

def test_scheduler_add_and_list_job(tmp_path):
    from aigernon.harness.scheduler import HarnessScheduler
    sched = HarnessScheduler(store_path=tmp_path / "jobs.json")
    job = sched.add_job("Daily audit", every_seconds=86400)
    jobs = sched.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == job.id
    assert jobs[0].goal == "Daily audit"
    assert jobs[0].every_seconds == 86400


def test_scheduler_remove_job(tmp_path):
    from aigernon.harness.scheduler import HarnessScheduler
    sched = HarnessScheduler(store_path=tmp_path / "jobs.json")
    job = sched.add_job("Test task", every_seconds=3600)
    assert sched.remove_job(job.id) is True
    assert sched.list_jobs() == []


def test_scheduler_remove_nonexistent_returns_false(tmp_path):
    from aigernon.harness.scheduler import HarnessScheduler
    sched = HarnessScheduler(store_path=tmp_path / "jobs.json")
    assert sched.remove_job("no-such-id") is False


def test_scheduler_next_run_set_on_add(tmp_path):
    from aigernon.harness.scheduler import HarnessScheduler
    sched = HarnessScheduler(store_path=tmp_path / "jobs.json")
    job = sched.add_job("Run me", every_seconds=60)
    assert job.next_run_at_ms is not None
    assert job.next_run_at_ms > 0


def test_scheduler_enable_disable(tmp_path):
    from aigernon.harness.scheduler import HarnessScheduler
    sched = HarnessScheduler(store_path=tmp_path / "jobs.json")
    job = sched.add_job("Toggle test", every_seconds=3600)
    sched.enable_job(job.id, enabled=False)
    assert sched.list_jobs()[0].enabled is False
    sched.enable_job(job.id, enabled=True)
    assert sched.list_jobs()[0].enabled is True


def test_scheduler_persists_across_instances(tmp_path):
    from aigernon.harness.scheduler import HarnessScheduler
    store = tmp_path / "jobs.json"
    sched1 = HarnessScheduler(store_path=store)
    sched1.add_job("Persistent task", every_seconds=7200)

    sched2 = HarnessScheduler(store_path=store)
    jobs = sched2.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].goal == "Persistent task"


def test_scheduler_schedule_description(tmp_path):
    from aigernon.harness.scheduler import HarnessScheduler
    sched = HarnessScheduler(store_path=tmp_path / "jobs.json")
    j1 = sched.add_job("hourly", every_seconds=3600)
    j2 = sched.add_job("every 30m", every_seconds=1800)
    assert j1.schedule_description() == "every 1h"
    assert j2.schedule_description() == "every 30m"


@pytest.mark.asyncio
async def test_scheduler_tick_runs_due_job(tmp_path):
    """tick() runs a job whose next_run_at_ms is in the past."""
    from aigernon.harness.scheduler import HarnessScheduler, HarnessJob, _now_ms

    store = tmp_path / "jobs.json"
    sched = HarnessScheduler(store_path=store)
    job = sched.add_job("Tick test", every_seconds=3600)

    # Force next_run to the past
    jobs = sched._load()
    jobs[0].next_run_at_ms = _now_ms() - 1000
    sched._save(jobs)

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer())

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    with patch("aigernon.harness.loop.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=tmp_path):
        started = await sched.tick(agent)

    assert len(started) == 1
    # next_run_at_ms should have advanced
    assert sched.list_jobs()[0].next_run_at_ms > _now_ms() - 1000


@pytest.mark.asyncio
async def test_scheduler_tick_skips_disabled_job(tmp_path):
    from aigernon.harness.scheduler import HarnessScheduler, _now_ms

    store = tmp_path / "jobs.json"
    sched = HarnessScheduler(store_path=store)
    job = sched.add_job("Disabled", every_seconds=3600)
    sched.enable_job(job.id, enabled=False)

    jobs = sched._load()
    jobs[0].next_run_at_ms = _now_ms() - 1000
    sched._save(jobs)

    agent = MagicMock()
    agent.process_direct = AsyncMock(return_value="ok")

    started = await sched.tick(agent)
    assert started == []
    agent.process_direct.assert_not_called()


# ===========================================================================
# f5.2 — HarnessNotifier
# ===========================================================================

@pytest.mark.asyncio
async def test_notifier_on_pass_sends_telegram():
    from aigernon.harness.notifier import HarnessNotifier

    sender = MagicMock()
    sender.send = AsyncMock(return_value=True)
    notifier = HarnessNotifier(telegram_sender=sender, chat_id="12345")

    await notifier.on_pass("unit-abc", "Build the thing")
    sender.send.assert_called_once()
    text = sender.send.call_args[0][1]
    assert "unit-abc" in text
    assert "Build the thing" in text


@pytest.mark.asyncio
async def test_notifier_on_pause_sends_telegram():
    from aigernon.harness.notifier import HarnessNotifier

    sender = MagicMock()
    sender.send = AsyncMock(return_value=True)
    notifier = HarnessNotifier(telegram_sender=sender, chat_id="12345")

    await notifier.on_pause("unit-xyz", "human_required: ['s2']", "Deploy")
    sender.send.assert_called_once()
    text = sender.send.call_args[0][1]
    assert "unit-xyz" in text
    assert "resume" in text.lower()


@pytest.mark.asyncio
async def test_notifier_on_escalated_sends_telegram():
    from aigernon.harness.notifier import HarnessNotifier

    sender = MagicMock()
    sender.send = AsyncMock(return_value=True)
    notifier = HarnessNotifier(telegram_sender=sender, chat_id="12345")

    await notifier.on_escalated("unit-esc", "Fix the bug", "persistent Ratify fail")
    sender.send.assert_called_once()
    text = sender.send.call_args[0][1]
    assert "escalated" in text.lower()


@pytest.mark.asyncio
async def test_notifier_no_channel_does_not_raise():
    """HarnessNotifier with no telegram_sender logs instead of raising."""
    from aigernon.harness.notifier import HarnessNotifier
    notifier = HarnessNotifier()
    # Should not raise
    await notifier.on_pass("u1", "goal")
    await notifier.on_pause("u1", "reason", "goal")
    await notifier.on_escalated("u1", "goal", "fail")


@pytest.mark.asyncio
async def test_run_unit_calls_notifier_on_pass(tmp_path):
    """run_unit calls notifier.on_pass when unit passes ratify."""
    from aigernon.harness.loop import run_unit
    from aigernon.harness.notifier import HarnessNotifier

    notifier = MagicMock(spec=HarnessNotifier)
    notifier.on_pass = AsyncMock()
    notifier.on_escalated = AsyncMock()
    notifier.on_pause = AsyncMock()

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer())

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    with patch("aigernon.harness.loop.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=tmp_path):
        result = await run_unit("Notifier pass test", agent, notifier=notifier)

    assert result["outcome"] == "pass"
    notifier.on_pass.assert_called_once()


# ===========================================================================
# f5.4 — Sub-Unit composition
# ===========================================================================

def test_list_children_empty(unit):
    from aigernon.harness.unit import list_children
    assert list_children(unit["unit_id"]) == []


def test_list_children_finds_children(unit):
    from aigernon.harness.unit import create_unit, list_children

    child1 = create_unit("Child task 1", parent_unit_id=unit["unit_id"])
    child2 = create_unit("Child task 2", parent_unit_id=unit["unit_id"])
    unrelated = create_unit("Unrelated task")

    children = list_children(unit["unit_id"])
    child_ids = {c["unit_id"] for c in children}
    assert child1["unit_id"] in child_ids
    assert child2["unit_id"] in child_ids
    assert unrelated["unit_id"] not in child_ids


def test_children_passed_criterion_no_children(unit):
    """children_passed passes trivially when there are no children."""
    from aigernon.harness.ratify import _check_children_passed
    passed, evidence = _check_children_passed(unit["unit_id"])
    assert passed is True
    assert "trivially" in evidence


def test_children_passed_criterion_not_archived(unit):
    """children_passed fails when children are not yet archived."""
    from aigernon.harness.unit import create_unit
    from aigernon.harness.ratify import _check_children_passed

    create_unit("Child", parent_unit_id=unit["unit_id"])
    passed, evidence = _check_children_passed(unit["unit_id"])
    assert passed is False
    assert "not yet archived" in evidence


def test_children_passed_criterion_all_archived_pass(unit, tmp_path):
    """children_passed passes when all children are archived with ratify pass."""
    from aigernon.harness.unit import create_unit, update_status, unit_path as up
    from aigernon.harness.ratify import _check_children_passed

    child = create_unit("Child", parent_unit_id=unit["unit_id"])
    cid = child["unit_id"]

    # Transition child through to archived
    update_status(cid, "deciding")
    update_status(cid, "doing")
    update_status(cid, "ratifying")
    update_status(cid, "archived")

    # Write a passing ratify record for the child
    ratify_path = up(cid) / "ratify.json"
    ratify_path.write_text(json.dumps({
        "unit_id": cid, "outcome": "pass", "fail_reason": None,
        "checked_at": "2026-04-30T00:00:00+00:00", "checked_by": "test",
        "results": {}, "next_action": "archive", "checked_against_criteria_version": 1,
    }))

    passed, evidence = _check_children_passed(unit["unit_id"])
    assert passed is True
    assert "1 child unit" in evidence


def test_run_unit_with_parent_unit_id(tmp_path):
    """run_unit with parent_unit_id creates a unit linked to the parent."""
    from aigernon.harness.unit import create_unit, list_children
    import asyncio

    parent = create_unit("Parent task")
    pid = parent["unit_id"]

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer())

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    async def run():
        from aigernon.harness.loop import run_unit
        return await run_unit("Child task", agent, parent_unit_id=pid)

    with patch("aigernon.harness.loop.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=tmp_path):
        result = asyncio.run(run())

    assert result["outcome"] == "pass"
    children = list_children(pid)
    assert any(c["unit_id"] == result["unit_id"] for c in children)


# ===========================================================================
# f5.5 — Human-in-the-loop pause/resume
# ===========================================================================

@pytest.mark.asyncio
async def test_human_required_step_pauses_unit(tmp_path):
    """Plan with human_required step causes loop to return outcome=paused."""
    from aigernon.harness.loop import run_unit

    async def agent_side_effect(msg, session_id):
        uid = _uid_from_msg(msg)
        if not uid:
            return "ok"
        from aigernon.harness.criteria import criteria_version_count
        from aigernon.harness.plan import plan_version_count
        if "Assess realm" in msg:
            cv = criteria_version_count(uid) + 1
            _write_criteria_file(uid, cv)
        elif "Decide realm" in msg:
            pv = plan_version_count(uid) + 1
            _write_plan_file(uid, pv, human_required_steps=["s_deploy"])
        elif "Do realm" in msg:
            _write_claim_file(uid)
        return "ok"

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=agent_side_effect)

    result = await run_unit("Human required test", agent)

    assert result["outcome"] == "paused"
    assert "s_deploy" in result.get("paused_steps", [])


@pytest.mark.asyncio
async def test_human_required_writes_human_pause_event(tmp_path):
    """human_required step writes human_pause event to event log."""
    from aigernon.harness.loop import run_unit
    from aigernon.harness.events import EventLog

    async def agent_side_effect(msg, session_id):
        uid = _uid_from_msg(msg)
        if not uid:
            return "ok"
        from aigernon.harness.criteria import criteria_version_count
        from aigernon.harness.plan import plan_version_count
        if "Assess realm" in msg:
            cv = criteria_version_count(uid) + 1
            _write_criteria_file(uid, cv)
        elif "Decide realm" in msg:
            pv = plan_version_count(uid) + 1
            _write_plan_file(uid, pv, human_required_steps=["s_approve"])
        return "ok"

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=agent_side_effect)

    result = await run_unit("Pause event test", agent)
    uid = result["unit_id"]
    log = EventLog(uid)
    pauses = log.read(kind="human_pause")
    assert len(pauses) >= 1
    assert any(e["data"]["reason"] == "human_required" for e in pauses)


@pytest.mark.asyncio
async def test_resume_unit_transitions_paused_to_doing(tmp_path):
    """resume_unit transitions a paused unit to doing and calls wake."""
    from aigernon.harness.loop import run_unit, resume_unit
    from aigernon.harness.unit import get_unit

    async def agent_side_effect(msg, session_id):
        uid = _uid_from_msg(msg)
        if not uid:
            return "ok"
        from aigernon.harness.criteria import criteria_version_count
        from aigernon.harness.plan import plan_version_count
        if "Assess realm" in msg:
            cv = criteria_version_count(uid) + 1
            _write_criteria_file(uid, cv)
        elif "Decide realm" in msg:
            pv = plan_version_count(uid) + 1
            # First time: write plan with human_required; second time: without
            meta = get_unit(uid)
            if meta and meta.get("status") == "paused":
                _write_plan_file(uid, pv)  # no human_required on resume
            else:
                _write_plan_file(uid, pv, human_required_steps=["s_approve"])
        elif "Do realm" in msg:
            _write_claim_file(uid)
        return "ok"

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=agent_side_effect)

    # First run — will pause
    result = await run_unit("Resume test", agent)
    assert result["outcome"] == "paused"
    uid = result["unit_id"]

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    with patch("aigernon.harness.wake.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=tmp_path):
        resumed = await resume_unit(uid, agent, human_response="Approved for deploy")

    assert resumed["outcome"] == "pass"


def test_resume_unit_raises_if_not_paused(unit):
    """resume_unit raises ValueError if unit is not in paused status."""
    from aigernon.harness.loop import resume_unit
    import asyncio

    async def run():
        return await resume_unit(unit["unit_id"], MagicMock(), human_response="go")

    with pytest.raises(ValueError, match="not paused"):
        asyncio.run(run())


def test_paused_status_in_unit_transitions(unit):
    """deciding → paused → doing is a valid transition path."""
    from aigernon.harness.unit import update_status, get_unit

    update_status(unit["unit_id"], "deciding")
    update_status(unit["unit_id"], "paused")
    assert get_unit(unit["unit_id"])["status"] == "paused"
    update_status(unit["unit_id"], "doing")
    assert get_unit(unit["unit_id"])["status"] == "doing"

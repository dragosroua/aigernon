"""Tests for Phase 4 — Hands abstraction, tool auth gate, budget enforcement.

Covers: f4.1 (InProcessHands), f4.2 (DockerHands stub),
        f4.3 (tool auth gate), f4.4 (budget enforcement).
"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call


@pytest.fixture(autouse=True)
def isolated_units_dir(tmp_path, monkeypatch):
    import aigernon.harness.unit as u
    monkeypatch.setattr(u, "_units_dir", lambda: tmp_path / "units")


@pytest.fixture()
def unit():
    from aigernon.harness.unit import create_unit
    return create_unit("Phase 4 test goal")


def _make_plan(max_tool_calls=10, max_wall_seconds=60, tools_authorized=None):
    return {
        "approach": "test",
        "alternatives_considered": [],
        "steps": [{"id": "s1", "description": "step", "estimated_tool_calls": 1}],
        "budgets": {
            "max_tokens": 10000,
            "max_tool_calls": max_tool_calls,
            "max_wall_seconds": max_wall_seconds,
            "max_dollars": 1.0,
        },
        "tools_authorized": tools_authorized if tools_authorized is not None else ["view", "edit"],
        "version": 1,
        "committed_at": "2026-04-30T00:00:00+00:00",
        "committed_by": "test",
    }


# ===========================================================================
# f4.1 — InProcessHands basic interface
# ===========================================================================

def test_hands_start_sets_start_time(unit):
    from aigernon.harness.hands import InProcessHands
    hands = InProcessHands(unit["unit_id"], _make_plan())
    assert hands._start_time is None
    hands.start()
    assert hands._start_time is not None


def test_hands_elapsed_seconds_before_start(unit):
    from aigernon.harness.hands import InProcessHands
    hands = InProcessHands(unit["unit_id"], _make_plan())
    assert hands.elapsed_seconds() == 0.0


def test_hands_elapsed_seconds_after_start(unit):
    from aigernon.harness.hands import InProcessHands
    hands = InProcessHands(unit["unit_id"], _make_plan())
    hands.start()
    time.sleep(0.01)
    assert hands.elapsed_seconds() > 0.0


@pytest.mark.asyncio
async def test_inprocess_hands_calls_process_direct(unit):
    from aigernon.harness.hands import InProcessHands
    hands = InProcessHands(unit["unit_id"], _make_plan())
    hands.start()

    agent = MagicMock()
    agent.process_direct = AsyncMock(return_value="ok")

    await hands.run(agent, "test message", "sess:test")
    agent.process_direct.assert_called_once_with("test message", "sess:test")


# ===========================================================================
# f4.3 — Tool authorization gate
# ===========================================================================

def test_verify_tool_auth_no_violations(unit):
    from aigernon.harness.hands import InProcessHands
    from aigernon.harness.events import EventLog

    plan = _make_plan(tools_authorized=["view", "edit"])
    log = EventLog(unit["unit_id"])
    log.append({"realm": "do", "kind": "tool_call", "data": {"name": "view"}})
    log.append({"realm": "do", "kind": "tool_call", "data": {"name": "edit"}})

    hands = InProcessHands(unit["unit_id"], plan)
    assert hands.verify_tool_auth() == []


def test_verify_tool_auth_detects_violation(unit):
    from aigernon.harness.hands import InProcessHands
    from aigernon.harness.events import EventLog

    plan = _make_plan(tools_authorized=["view"])
    log = EventLog(unit["unit_id"])
    log.append({"realm": "do", "kind": "tool_call", "data": {"name": "view"}})
    log.append({"realm": "do", "kind": "tool_call", "data": {"name": "bash_exec"}})

    hands = InProcessHands(unit["unit_id"], plan)
    violations = hands.verify_tool_auth()
    assert "bash_exec" in violations
    assert "view" not in violations


def test_verify_tool_auth_empty_authorized_means_no_restriction(unit):
    """Empty tools_authorized = no gate (plan imposes no tool restriction)."""
    from aigernon.harness.hands import InProcessHands
    from aigernon.harness.events import EventLog

    plan = _make_plan(tools_authorized=[])
    log = EventLog(unit["unit_id"])
    log.append({"realm": "do", "kind": "tool_call", "data": {"name": "anything"}})

    hands = InProcessHands(unit["unit_id"], plan)
    assert hands.verify_tool_auth() == []


def test_verify_tool_auth_ignores_non_do_tool_calls(unit):
    """Tool calls in assess or decide realm are not subject to the Do gate."""
    from aigernon.harness.hands import InProcessHands
    from aigernon.harness.events import EventLog

    plan = _make_plan(tools_authorized=["view"])
    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "tool_call", "data": {"name": "bash_exec"}})
    log.append({"realm": "do", "kind": "tool_call", "data": {"name": "view"}})

    hands = InProcessHands(unit["unit_id"], plan)
    assert hands.verify_tool_auth() == []


# ===========================================================================
# f4.4 — Budget enforcement
# ===========================================================================

def test_check_tool_calls_ok_under_budget(unit):
    from aigernon.harness.hands import InProcessHands
    from aigernon.harness.events import EventLog

    plan = _make_plan(max_tool_calls=5)
    log = EventLog(unit["unit_id"])
    for _ in range(4):
        log.append({"realm": "do", "kind": "tool_call", "data": {"name": "view"}})

    hands = InProcessHands(unit["unit_id"], plan)
    hands.check_tool_calls()  # should not raise


def test_check_tool_calls_raises_at_limit(unit):
    from aigernon.harness.hands import InProcessHands, BudgetExceededError
    from aigernon.harness.events import EventLog

    plan = _make_plan(max_tool_calls=3)
    log = EventLog(unit["unit_id"])
    for _ in range(3):
        log.append({"realm": "do", "kind": "tool_call", "data": {"name": "view"}})

    hands = InProcessHands(unit["unit_id"], plan)
    with pytest.raises(BudgetExceededError) as exc_info:
        hands.check_tool_calls()
    assert exc_info.value.budget_kind == "tool_calls"
    assert exc_info.value.actual == 3
    assert exc_info.value.limit == 3


def test_check_wall_time_ok_under_budget(unit):
    from aigernon.harness.hands import InProcessHands
    plan = _make_plan(max_wall_seconds=60)
    hands = InProcessHands(unit["unit_id"], plan)
    hands.start()
    hands.check_wall_time()  # should not raise (<<1s elapsed)


def test_check_wall_time_raises_when_exceeded(unit):
    from aigernon.harness.hands import InProcessHands, BudgetExceededError
    plan = _make_plan(max_wall_seconds=0.001)  # 1ms — will be exceeded immediately
    hands = InProcessHands(unit["unit_id"], plan)
    hands.start()
    time.sleep(0.01)  # 10ms > 1ms limit
    with pytest.raises(BudgetExceededError) as exc_info:
        hands.check_wall_time()
    assert exc_info.value.budget_kind == "wall_seconds"


def test_no_budget_key_means_no_check(unit):
    """Absent budget keys are not enforced."""
    from aigernon.harness.hands import InProcessHands
    plan = {
        "approach": "test", "alternatives_considered": [], "steps": [],
        "budgets": {},  # empty — no limits
        "tools_authorized": [], "version": 1,
        "committed_at": "2026-04-30T00:00:00+00:00", "committed_by": "test",
    }
    hands = InProcessHands(unit["unit_id"], plan)
    hands.start()
    hands.check_budgets()  # should not raise


# ===========================================================================
# f4.4 — Budget exceeded propagates through loop.run_unit
# ===========================================================================

def _write_criteria_file(unit_id, version):
    from aigernon.harness.unit import unit_path as up
    path = up(unit_id) / "assess" / f"criteria_v{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "goal": "test", "context": "", "version": version,
        "hard_criteria": [{"id": "hc1", "type": "file_exists", "spec": str(path)}],
        "soft_criteria": [], "out_of_scope": [],
        "committed_at": "2026-04-30T00:00:00+00:00", "committed_by": "test",
        "supersedes_version": None, "reassess_reason": None,
    }))


def _write_plan_file(unit_id, version, tools_authorized=None, max_tool_calls=10):
    from aigernon.harness.unit import unit_path as up
    path = up(unit_id) / "decide" / f"plan_v{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "approach": "test", "alternatives_considered": [],
        "steps": [{"id": "s1", "description": "step", "estimated_tool_calls": 1}],
        "budgets": {"max_tokens": 1000, "max_tool_calls": max_tool_calls,
                    "max_wall_seconds": 60, "max_dollars": 0.10},
        "tools_authorized": tools_authorized or ["view"],
        "version": version,
        "committed_at": "2026-04-30T00:00:00+00:00", "committed_by": "test",
    }))


def _uid_from_msg(msg):
    for line in msg.splitlines():
        if line.startswith("Unit ID:"):
            return line.split(":", 1)[1].strip()
    return ""


@pytest.mark.asyncio
async def test_budget_exceeded_in_do_returns_escalated(tmp_path):
    """When Hands raises BudgetExceededError during Do, loop returns escalated."""
    from aigernon.harness.loop import run_unit
    from aigernon.harness.hands import BudgetExceededError as BEE

    call_count = [0]

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
            _write_plan_file(uid, pv)
        elif "Do realm" in msg:
            call_count[0] += 1
            raise BEE("tool_calls", 10, 10)
        return "ok"

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=agent_side_effect)

    # Patch hands_for_unit to return a Hands that raises on run()
    from aigernon.harness import hands as hands_mod

    class BudgetHands(hands_mod.InProcessHands):
        async def run(self, agent_loop, msg, session_id):
            raise BEE("tool_calls", 10, 10)

    with patch("aigernon.harness.loop.hands_for_unit",
               return_value=BudgetHands("placeholder", _make_plan())):
        result = await run_unit("Budget exceeded test", agent)

    assert result["outcome"] == "escalated"
    assert "budget exceeded" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_budget_exceeded_writes_human_pause_event(tmp_path):
    """BudgetExceededError in Do writes budget_exceeded + human_pause events."""
    from aigernon.harness.loop import run_unit
    from aigernon.harness.events import EventLog
    from aigernon.harness.hands import BudgetExceededError as BEE
    from aigernon.harness import hands as hands_mod

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
            _write_plan_file(uid, pv)
        return "ok"

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=agent_side_effect)

    result_holder = {}

    class BudgetHands(hands_mod.InProcessHands):
        async def run(self, agent_loop, msg, session_id):
            raise BEE("wall_seconds", 120.0, 60.0)

    with patch("aigernon.harness.loop.hands_for_unit",
               side_effect=lambda uid, plan, log=None: BudgetHands(uid, plan, log)):
        result = await run_unit("Budget pause event test", agent)

    uid = result["unit_id"]
    log = EventLog(uid)
    assert len(log.read(kind="budget_exceeded")) == 1
    assert len(log.read(kind="human_pause")) == 1
    pause = log.read(kind="human_pause")[0]
    assert pause["data"]["reason"] == "budget_exceeded"


@pytest.mark.asyncio
async def test_tool_auth_violation_returns_escalated(tmp_path):
    """Tool auth violation during Do returns escalated with human_pause event."""
    from aigernon.harness.loop import run_unit
    from aigernon.harness.events import EventLog
    from aigernon.harness import hands as hands_mod

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
            _write_plan_file(uid, pv, tools_authorized=["view"])
        elif "Do realm" in msg:
            # Simulate unauthorized tool call written to event log
            from aigernon.harness.events import EventLog as EL
            EL(uid).append({"realm": "do", "kind": "tool_call",
                             "data": {"name": "bash_exec"}})
        return "ok"

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=agent_side_effect)

    # Use real InProcessHands so verify_tool_auth() reads the event log
    result = await run_unit("Tool auth violation test", agent)

    assert result["outcome"] == "escalated"
    assert "tool auth violation" in result.get("error", "").lower()

    uid = result["unit_id"]
    log = EventLog(uid)
    violation_events = log.read(kind="tool_auth_violation")
    assert len(violation_events) == 1
    assert "bash_exec" in violation_events[0]["data"]["unauthorized_tools"]

    pause_events = log.read(kind="human_pause")
    assert any(e["data"]["reason"] == "tool_auth_violation" for e in pause_events)


# ===========================================================================
# f4.2 — DockerHands stub falls back to InProcessHands
# ===========================================================================

@pytest.mark.asyncio
async def test_docker_hands_falls_back_to_inprocess(unit):
    from aigernon.harness.hands import DockerHands

    hands = DockerHands(unit["unit_id"], _make_plan())
    hands.start()

    agent = MagicMock()
    agent.process_direct = AsyncMock(return_value="ok")

    await hands.run(agent, "msg", "sess")
    agent.process_direct.assert_called_once()


def test_hands_for_unit_default_is_inprocess(unit, monkeypatch):
    import os
    monkeypatch.delenv("AIGERNON_HANDS", raising=False)
    from aigernon.harness.hands import hands_for_unit, InProcessHands
    h = hands_for_unit(unit["unit_id"], _make_plan())
    assert isinstance(h, InProcessHands)


def test_hands_for_unit_docker_env(unit, monkeypatch):
    monkeypatch.setenv("AIGERNON_HANDS", "docker")
    from aigernon.harness import hands as hands_mod
    import importlib
    importlib.reload(hands_mod)
    h = hands_mod.hands_for_unit(unit["unit_id"], _make_plan())
    assert isinstance(h, hands_mod.DockerHands)

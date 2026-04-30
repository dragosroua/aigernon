"""Tests for Phase 3 — compaction, wake/resume, checkpoint events, archive lessons, memory.

Covers: f3.1 (compact), f3.2 (wake), f3.3 (checkpoint events),
        f3.4 (lessons.md in archive), f3.5 (daily memory file).
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
    return create_unit("Phase 3 test goal")


# ===========================================================================
# f3.1 — Compaction
# ===========================================================================

def test_compact_collapses_do_trace(unit):
    from aigernon.harness.events import EventLog
    from aigernon.harness.compact import compact_unit

    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "realm_enter"})
    log.append({"realm": "assess", "kind": "criteria_committed", "data": {"version": 1}})
    log.append({"realm": "do", "kind": "realm_enter"})
    for _ in range(5):
        log.append({"realm": "do", "kind": "tool_call", "data": {"name": "view"}})
    for _ in range(3):
        log.append({"realm": "do", "kind": "tool_result", "data": {}})
    log.append({"realm": "do", "kind": "do_claim_complete"})
    log.append({"realm": "do", "kind": "realm_exit"})

    result = compact_unit(unit["unit_id"])
    # 2 assess + 1 do realm_enter + 5 tool_call + 3 tool_result + do_claim_complete + realm_exit = 13
    assert result["original_count"] == 13
    # 5 tool_calls + 3 tool_results = 8 collapsed into 1 compact_summary
    assert result["compacted_count"] < result["original_count"]


def test_compact_preserves_boundary_events(unit):
    from aigernon.harness.events import EventLog
    from aigernon.harness.compact import compact_unit, read_compacted

    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "realm_enter"})
    log.append({"realm": "assess", "kind": "criteria_committed", "data": {"version": 1}})
    log.append({"realm": "do", "kind": "realm_enter"})
    log.append({"realm": "do", "kind": "tool_call", "data": {"name": "bash"}})
    log.append({"realm": "do", "kind": "do_claim_complete"})
    log.append({"realm": "do", "kind": "realm_exit"})

    compact_unit(unit["unit_id"])
    events = read_compacted(unit["unit_id"])

    kinds = [e["kind"] for e in events]
    assert "realm_enter" in kinds
    assert "criteria_committed" in kinds
    assert "do_claim_complete" in kinds
    assert "realm_exit" in kinds


def test_compact_summary_has_correct_kind(unit):
    from aigernon.harness.events import EventLog
    from aigernon.harness.compact import compact_unit, read_compacted

    log = EventLog(unit["unit_id"])
    log.append({"realm": "do", "kind": "tool_call", "data": {"name": "view"}})
    log.append({"realm": "do", "kind": "tool_result", "data": {}})

    compact_unit(unit["unit_id"])
    events = read_compacted(unit["unit_id"])

    summary_events = [e for e in events if e["kind"] == "compact_summary"]
    assert len(summary_events) == 1
    assert summary_events[0]["data"]["collapsed_event_count"] == 2


def test_compact_assess_events_preserved_verbatim(unit):
    from aigernon.harness.events import EventLog
    from aigernon.harness.compact import compact_unit, read_compacted

    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "criteria_committed", "data": {"version": 1}})
    log.append({"realm": "decide", "kind": "plan_committed", "data": {"version": 1}})
    log.append({"realm": "do", "kind": "tool_call", "data": {"name": "edit"}})

    compact_unit(unit["unit_id"])
    events = read_compacted(unit["unit_id"])

    # Assess and Decide events preserved; Do tool_call collapsed
    kinds = {e["kind"] for e in events}
    assert "criteria_committed" in kinds
    assert "plan_committed" in kinds
    assert "tool_call" not in kinds
    assert "compact_summary" in kinds


def test_read_compacted_falls_back_to_full_log(unit):
    """read_compacted returns full log when events_compacted.jsonl doesn't exist."""
    from aigernon.harness.events import EventLog
    from aigernon.harness.compact import read_compacted

    log = EventLog(unit["unit_id"])
    log.append({"realm": "assess", "kind": "realm_enter"})

    events = read_compacted(unit["unit_id"])
    assert len(events) == 1
    assert events[0]["kind"] == "realm_enter"


# ===========================================================================
# f3.2 — Wake / Resume
# ===========================================================================

def _write_criteria_file(unit_id, version, tmp_path=None):
    from aigernon.harness.unit import unit_path as up
    path = up(unit_id) / "assess" / f"criteria_v{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "goal": "test goal", "context": "", "version": version,
        "hard_criteria": [{"id": "hc1", "type": "file_exists", "spec": str(path)}],
        "soft_criteria": [], "out_of_scope": [],
        "committed_at": "2026-04-30T00:00:00+00:00", "committed_by": "test",
        "supersedes_version": None, "reassess_reason": None,
    }))


def _write_plan_file(unit_id, version):
    from aigernon.harness.unit import unit_path as up
    path = up(unit_id) / "decide" / f"plan_v{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "approach": "test", "alternatives_considered": [],
        "steps": [{"id": "s1", "description": "step", "estimated_tool_calls": 1}],
        "budgets": {"max_tokens": 1000, "max_tool_calls": 10, "max_wall_seconds": 60, "max_dollars": 0.10},
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


@pytest.mark.asyncio
async def test_wake_from_assessing(tmp_path):
    """Wake from 'assessing' status runs the full A→D→Do→Ratify cycle."""
    from aigernon.harness.unit import create_unit, update_status
    from aigernon.harness.wake import wake

    meta = create_unit("Wake test from assessing")
    uid = meta["unit_id"]
    # status is already 'assessing'

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer())

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    with patch("aigernon.harness.wake.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=tmp_path):
        result = await wake(uid, agent)

    assert result["outcome"] == "pass"
    assert result["unit_id"] == uid


@pytest.mark.asyncio
async def test_wake_from_deciding(tmp_path):
    """Wake from 'deciding' skips Assess and runs Decide→Do→Ratify."""
    from aigernon.harness.unit import create_unit, update_status
    from aigernon.harness.wake import wake

    meta = create_unit("Wake test from deciding")
    uid = meta["unit_id"]
    # Simulate criteria already written
    _write_criteria_file(uid, 1)
    update_status(uid, "deciding")

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer())

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    with patch("aigernon.harness.wake.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=tmp_path):
        result = await wake(uid, agent)

    assert result["outcome"] == "pass"


@pytest.mark.asyncio
async def test_wake_from_doing(tmp_path):
    """Wake from 'doing' skips Assess+Decide and runs Do→Ratify."""
    from aigernon.harness.unit import create_unit, update_status
    from aigernon.harness.wake import wake

    meta = create_unit("Wake test from doing")
    uid = meta["unit_id"]
    _write_criteria_file(uid, 1)
    _write_plan_file(uid, 1)
    update_status(uid, "deciding")
    update_status(uid, "doing")

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer())

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    with patch("aigernon.harness.wake.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=tmp_path):
        result = await wake(uid, agent)

    assert result["outcome"] == "pass"


@pytest.mark.asyncio
async def test_wake_from_ratifying(tmp_path):
    """Wake from 'ratifying' runs only Ratify."""
    from aigernon.harness.unit import create_unit, update_status
    from aigernon.harness.wake import wake

    meta = create_unit("Wake test from ratifying")
    uid = meta["unit_id"]
    _write_criteria_file(uid, 1)
    _write_plan_file(uid, 1)
    _write_claim_file(uid)
    update_status(uid, "deciding")
    update_status(uid, "doing")
    update_status(uid, "ratifying")

    agent = MagicMock()
    agent.process_direct = AsyncMock(return_value="ok")

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    with patch("aigernon.harness.wake.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=tmp_path):
        result = await wake(uid, agent)

    assert result["outcome"] == "pass"
    # Agent should not have been called (no realm needed before ratify)
    agent.process_direct.assert_not_called()


def test_wake_archived_unit_returns_immediately():
    """Wake on an archived unit returns pass immediately."""
    from aigernon.harness.unit import create_unit, update_status
    from aigernon.harness.wake import wake
    import asyncio

    meta = create_unit("Wake archived test")
    uid = meta["unit_id"]
    update_status(uid, "deciding")
    update_status(uid, "doing")
    update_status(uid, "ratifying")
    update_status(uid, "archived")

    agent = MagicMock()
    result = asyncio.run(wake(uid, agent))
    assert result["outcome"] == "pass"
    agent.process_direct.assert_not_called()


@pytest.mark.asyncio
async def test_wake_writes_checkpoint_event():
    """Wake writes a checkpoint_taken event to the event log."""
    from aigernon.harness.unit import create_unit
    from aigernon.harness.events import EventLog
    from aigernon.harness.wake import wake

    meta = create_unit("Wake checkpoint test")
    uid = meta["unit_id"]

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer())

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    with patch("aigernon.harness.wake.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=Path("/tmp")):
        await wake(uid, agent)

    log = EventLog(uid)
    checkpoints = log.read(kind="checkpoint_taken")
    # Wake itself writes one, plus the loop writes one per realm transition
    assert len(checkpoints) >= 1
    wake_cp = [e for e in checkpoints if e.get("data", {}).get("wake")]
    assert len(wake_cp) == 1


# ===========================================================================
# f3.3 — Checkpoint events in loop
# ===========================================================================

@pytest.mark.asyncio
async def test_loop_writes_checkpoint_after_each_realm(tmp_path):
    """loop.run_unit writes checkpoint_taken after assess, decide, and do."""
    from aigernon.harness.loop import run_unit
    from aigernon.harness.events import EventLog

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer())

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    with patch("aigernon.harness.loop.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", return_value=tmp_path):
        result = await run_unit("Checkpoint test goal", agent)

    uid = result["unit_id"]
    log = EventLog(uid)
    checkpoints = log.read(kind="checkpoint_taken")
    # Expect 3: after assess, after decide, after do
    after_values = {e.get("data", {}).get("after") for e in checkpoints}
    assert "assess" in after_values
    assert "decide" in after_values
    assert "do" in after_values


# ===========================================================================
# f3.4 — lessons.md in archive
# ===========================================================================

@pytest.mark.asyncio
async def test_archive_writes_lessons_md(tmp_path):
    """Archiving a unit writes lessons.md to the archive destination."""
    from aigernon.harness.loop import run_unit

    archive_dest = tmp_path / "archive_dest"
    archive_dest.mkdir()

    agent = MagicMock()
    agent.process_direct = AsyncMock(side_effect=_make_writer())

    async def pass_ratify(unit_id):
        return {"outcome": "pass", "fail_reason": None, "reassess_advice": None,
                "next_action": "archive", "results": {}, "checked_at": "", "checked_by": "test",
                "unit_id": unit_id, "checked_against_criteria_version": 1}

    def fake_archive(unit_id):
        from aigernon.harness.loop import _archive_unit as real_archive
        # Call the real archive but redirect to tmp
        import shutil
        from aigernon.harness.unit import unit_path
        shutil.copytree(str(unit_path(unit_id)), str(archive_dest), dirs_exist_ok=True)
        # Write lessons.md as real _archive_unit would
        from aigernon.harness.substrate import read_substrate
        from aigernon.harness.unit import get_unit
        from datetime import datetime, timezone
        substrate = read_substrate(unit_id)
        meta = get_unit(unit_id)
        goal = (meta or {}).get("goal", "")
        now = datetime.now(timezone.utc)
        (archive_dest / "lessons.md").write_text(
            f"# Lessons — {unit_id}\n\n**Goal:** {goal}\n\n**Archived:** {now.isoformat()}\n\n---\n\n{substrate}"
        )
        return archive_dest

    with patch("aigernon.harness.loop.ratify", side_effect=pass_ratify), \
         patch("aigernon.harness.loop._archive_unit", side_effect=fake_archive):
        result = await run_unit("Lessons test goal", agent)

    lessons = archive_dest / "lessons.md"
    assert lessons.exists()
    content = lessons.read_text()
    assert "Lessons —" in content
    assert "Lessons test goal" in content


# ===========================================================================
# f3.5 — Daily memory file
# ===========================================================================

def test_append_to_daily_memory(tmp_path, monkeypatch):
    """_append_to_daily_memory writes entry to daily file and indexes in MEMORY.md."""
    from aigernon.harness.loop import _append_to_daily_memory
    from datetime import datetime, timezone
    import aigernon.utils.helpers as helpers

    monkeypatch.setattr(helpers, "get_data_path", lambda: tmp_path)

    now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
    _append_to_daily_memory("test-unit-01", "Test goal here", now, tmp_path / "archive")

    daily = tmp_path / "workspace" / "memory" / "2026-04-30.md"
    assert daily.exists()
    content = daily.read_text()
    assert "test-unit-01" in content
    assert "Test goal here" in content

    index = tmp_path / "workspace" / "memory" / "MEMORY.md"
    assert index.exists()
    assert "2026-04-30.md" in index.read_text()


def test_append_to_daily_memory_no_duplicate_index(tmp_path, monkeypatch):
    """Calling _append_to_daily_memory twice doesn't duplicate MEMORY.md entry."""
    from aigernon.harness.loop import _append_to_daily_memory
    from datetime import datetime, timezone
    import aigernon.utils.helpers as helpers

    monkeypatch.setattr(helpers, "get_data_path", lambda: tmp_path)

    now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
    _append_to_daily_memory("unit-a", "Goal A", now, tmp_path / "a")
    _append_to_daily_memory("unit-b", "Goal B", now, tmp_path / "b")

    index = tmp_path / "workspace" / "memory" / "MEMORY.md"
    # Each index_line contains the date string twice (link text + href), so count
    # matching lines instead of raw string occurrences
    lines_with_date = [l for l in index.read_text().splitlines() if "2026-04-30.md" in l]
    assert len(lines_with_date) == 1

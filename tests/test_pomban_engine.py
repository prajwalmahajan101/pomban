"""Unit tests for PombanEngine — the UI-agnostic facade that the Textual app drives.

These exercise the engine directly with a real on-disk DB and no Textual,
so the facade can be unit-tested independently of the app shell.
"""

import tempfile
import time
from pathlib import Path

import pytest

from pomban.core.db import DB
from pomban.core.engine import PombanEngine, TickOutcome
from pomban.core.timer_engine import Event, Phase, Settings


@pytest.fixture
def fast_settings() -> Settings:
    return Settings(
        focus_seconds=5,
        short_break_seconds=3,
        long_break_seconds=4,
        cycles_before_long_break=4,
        warning_seconds=2,
    )


@pytest.fixture
def engine(fast_settings):
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "e.db")
        yield PombanEngine(db=db, settings=fast_settings)
        db.close()


# ---------- delegating properties ----------


def test_phase_remaining_running_delegate_to_timer(engine):
    assert engine.phase == Phase.IDLE
    assert engine.remaining == 0
    assert engine.running is False
    assert engine.completed_focus_cycles == 0


def test_settings_round_trip(engine):
    new = Settings(focus_seconds=10, short_break_seconds=2, long_break_seconds=2)
    engine.settings = new
    assert engine.settings.focus_seconds == 10
    assert engine.timer.settings.focus_seconds == 10


def test_active_task_setter_wraps_single_task_into_list(engine):
    task = engine.db.add_task("Demo")
    engine.active_task = task
    assert engine.active_tasks == [task]
    engine.active_task = None
    assert engine.active_tasks == []


# ---------- tick loop ----------


def test_tick_when_not_running_returns_empty_plan(engine):
    assert engine.tick(time.monotonic()) == []


def test_tick_emits_ending_soon_then_completed(engine):
    task = engine.db.add_task("Run")
    engine.start_focus_on_many([task])
    assert engine.running is True

    # Step right up to warning_seconds (focus=5, warning=2 → fire at t=3)
    base = time.monotonic()
    outcomes_at_warning = engine.tick(base + 3)
    kinds = [o.kind for o in outcomes_at_warning]
    assert "ending_soon" in kinds

    outcomes_at_end = engine.tick(base + 6)
    assert any(o.kind == "phase_completed" for o in outcomes_at_end)


def test_events_to_outcomes_handles_both_events(engine):
    out = engine._events_to_outcomes([Event.PHASE_ENDING_SOON, Event.PHASE_COMPLETED])
    assert [o.kind for o in out] == ["ending_soon", "phase_completed"]
    assert all(isinstance(o, TickOutcome) for o in out)


# ---------- start_focus_on_many ----------


def test_start_focus_on_many_with_empty_list_is_noop(engine):
    assert engine.start_focus_on_many([]) is False
    assert engine.phase == Phase.IDLE


def test_start_focus_on_many_marks_todo_doing_and_starts_timer(engine):
    a = engine.db.add_task("A")  # status="todo" by default
    b = engine.db.add_task("B")
    assert engine.start_focus_on_many([a, b]) is True
    assert engine.phase == Phase.FOCUS
    assert engine.running is True
    assert engine.active_tasks == [a, b]
    assert engine.active_chip_index == 0
    assert engine.db.get_task(a.id).status == "doing"
    assert engine.db.get_task(b.id).status == "doing"


def test_start_focus_on_many_opens_session_row(engine):
    task = engine.db.add_task("Work")
    engine.start_focus_on_many([task])
    sid = engine.current_session_id
    assert sid is not None
    assert engine.session_start_monotonic is not None
    row = engine.db.conn.execute(
        "SELECT kind, planned_seconds FROM sessions WHERE id=?", (sid,)
    ).fetchone()
    assert row["kind"] == "focus"
    assert row["planned_seconds"] == engine.settings.focus_seconds


def test_start_focus_on_many_resets_chip_index(engine):
    engine.active_chip_index = 7
    task = engine.db.add_task("T")
    engine.start_focus_on_many([task])
    assert engine.active_chip_index == 0


# ---------- log_new_session ----------


def test_log_new_session_skips_idle(engine):
    engine.log_new_session()
    assert engine.current_session_id is None


# ---------- finalize_multi_complete ----------


def test_finalize_multi_complete_closes_session_and_marks_done(engine):
    a = engine.db.add_task("A")
    b = engine.db.add_task("B")
    engine.start_focus_on_many([a, b])
    sid = engine.current_session_id

    engine.finalize_multi_complete(sid, actual=100, ids=[a.id])

    # Original focus session is closed completed.
    row = engine.db.conn.execute(
        "SELECT completed, actual_seconds FROM sessions WHERE id=?", (sid,)
    ).fetchone()
    assert row["completed"] == 1
    assert row["actual_seconds"] == 100
    # A done, B not.
    assert engine.db.get_task(a.id).status == "done"
    assert engine.db.get_task(b.id).status != "done"
    # B stays in the active set so the next phase keeps it.
    assert [t.id for t in engine.active_tasks] == [b.id]


def test_finalize_multi_complete_with_none_ids_does_not_mark_task_done(engine):
    a = engine.db.add_task("A")
    engine.start_focus_on_many([a])
    sid = engine.current_session_id
    engine.finalize_multi_complete(sid, actual=0, ids=None)
    # The focus row closed, but no task was flipped to done because no ids
    # were passed in.
    row = engine.db.conn.execute(
        "SELECT completed FROM sessions WHERE id=?", (sid,)
    ).fetchone()
    assert row["completed"] == 1
    assert engine.db.get_task(a.id).status != "done"


# ---------- fire_phase_hooks ----------


def test_fire_phase_hooks_runs_user_hook_with_env(engine):
    captured: list[tuple[str, dict]] = []

    def fake_run_hook(cmd, env):
        captured.append((cmd, dict(env)))

    class FakeHooks:
        on_focus_start = "echo focus start"
        on_focus_end = "echo focus end"
        on_break_start = "echo break start"
        on_break_end = "echo break end"

    engine._hooks = FakeHooks()
    engine._run_hook = fake_run_hook
    task = engine.db.add_task("Demo")
    engine.active_task = task

    engine.fire_phase_hooks(starting=True, phase=Phase.FOCUS)
    assert captured == [
        (
            "echo focus start",
            {
                "POMODORO_PHASE": "focus",
                "POMODORO_TASK_TITLE": "Demo",
                "POMODORO_EVENT": "start",
            },
        )
    ]


def test_fire_phase_hooks_without_config_is_silent(engine):
    # Default engine has no hooks/run_hook/plugin_registry — call must not raise.
    engine.fire_phase_hooks(starting=False, phase=Phase.SHORT_BREAK)

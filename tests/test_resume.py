import pytest

from pomodoro.app import PomodoroApp
from pomodoro.core.db import DB
from pomodoro.core.timer_engine import Phase
from pomodoro.screens.dashboard import DashboardScreen
from pomodoro.screens.resume import ResumePrompt


async def wait_for(pilot, screen_cls):
    for _ in range(40):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(type(pilot.app.screen))


def test_kv_set_get_delete(tmp_path):
    db = DB(tmp_path / "kv.db")
    assert db.kv_get("x") is None
    db.kv_set("x", "hello")
    assert db.kv_get("x") == "hello"
    db.kv_set("x", "world")
    assert db.kv_get("x") == "world"
    db.kv_delete("x")
    assert db.kv_get("x") is None
    db.close()


@pytest.mark.asyncio
async def test_pending_session_persists_on_exit(tmp_path):
    db_path = tmp_path / "r.db"
    db = DB(db_path)
    db.add_task("Resumable")
    app = PomodoroApp(db=db, fast=True)
    async with app.run_test() as pilot:
        scr = await wait_for(pilot, DashboardScreen)
        from textual.widgets import ListView

        lv = scr.query_one("#task-list", ListView)
        lv.focus()
        lv.index = 0
        await pilot.press("enter")
        await pilot.pause()
        assert app.engine.phase == Phase.FOCUS
        # quit triggers on_unmount which persists
        await app.action_quit()
    # Now check db state
    db2 = DB(db_path)
    assert db2.kv_get("pending_session_id") is not None
    assert db2.kv_get("pending_phase") == "focus"
    db2.close()


@pytest.mark.asyncio
async def test_resume_prompt_appears_when_pending(tmp_path):
    db_path = tmp_path / "r.db"
    db = DB(db_path)
    t = db.add_task("Resumable")
    sid = db.start_session("focus", 1500, [t.id])
    db.kv_set("pending_session_id", str(sid))
    db.kv_set("pending_remaining_seconds", "600")
    db.kv_set("pending_phase", "focus")
    db.kv_set("pending_task_id", str(t.id))
    db.close()

    db = DB(db_path)
    app = PomodoroApp(db=db, fast=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Wait for ResumePrompt to be pushed
        for _ in range(40):
            await pilot.pause()
            if isinstance(app.screen, ResumePrompt):
                break
        assert isinstance(app.screen, ResumePrompt)
        await pilot.press("y")
        await pilot.pause()
        assert app.engine.phase == Phase.FOCUS
        assert app.engine.remaining > 0
        assert app.active_task is not None
        assert app.current_session_id == sid
        # KV cleared
        assert db.kv_get("pending_session_id") is None
    db.close()


@pytest.mark.asyncio
async def test_resume_discard_closes_session_incomplete(tmp_path):
    db_path = tmp_path / "r.db"
    db = DB(db_path)
    t = db.add_task("Drop")
    sid = db.start_session("focus", 1500, [t.id])
    db.kv_set("pending_session_id", str(sid))
    db.kv_set("pending_remaining_seconds", "100")
    db.kv_set("pending_phase", "focus")
    db.close()

    db = DB(db_path)
    app = PomodoroApp(db=db, fast=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        for _ in range(40):
            await pilot.pause()
            if isinstance(app.screen, ResumePrompt):
                break
        assert isinstance(app.screen, ResumePrompt)
        await pilot.press("n")
        await pilot.pause()
        row = db.conn.execute(
            "SELECT completed, ended_at FROM sessions WHERE id=?", (sid,)
        ).fetchone()
        assert row["completed"] == 0
        assert row["ended_at"] is not None
    db.close()

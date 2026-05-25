import tempfile
from pathlib import Path

import pytest

from pomodoro.app import PomodoroApp
from pomodoro.core.db import DB
from pomodoro.screens.dashboard import DashboardScreen


async def wait_for_dashboard(pilot) -> DashboardScreen:
    for _ in range(40):
        await pilot.pause()
        if isinstance(pilot.app.screen, DashboardScreen):
            return pilot.app.screen
    raise AssertionError(f"Dashboard never became active: {type(pilot.app.screen)}")


@pytest.mark.asyncio
async def test_edit_task_round_trip():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "e.db")
        t = db.add_task("Old title", tags="x", estimated_pomodoros=4)
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for_dashboard(pilot)
            app._on_task_edited(t.id, {"title": "New title", "tags": "a,b",
                                       "estimate": 6, "project": "proj"})
            await pilot.pause()
            row = db.get_task(t.id)
            assert row.title == "New title"
            assert row.estimated_pomodoros == 6
            assert row.tags == "a,b"
            assert row.project_id is not None
        db.close()


@pytest.mark.asyncio
async def test_edit_task_clears_project():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "e.db")
        proj = db.get_or_create_project("home")
        t = db.add_task("Task", project_id=proj.id)
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for_dashboard(pilot)
            assert db.get_task(t.id).project_id == proj.id
            app._on_task_edited(t.id, {"title": "Task", "tags": "",
                                       "estimate": 0, "project": ""})
            await pilot.pause()
            assert db.get_task(t.id).project_id is None
        db.close()

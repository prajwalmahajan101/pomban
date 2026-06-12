"""Pilot tests for the SprintRunnerScreen overlay (Shift+R)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.sprint_runner import RetroModal, SprintRunnerScreen


async def wait_for(pilot, screen_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


def _seed_sprint_with_tasks(db: DB) -> tuple[int, int, int]:
    project = db.add_project("Demo")
    sprint = db.add_sprint(project.id, "S1", "2026-06-01", "2026-06-30", pomodoro_target=2)
    db.activate_sprint(sprint.id)
    t1 = db.add_task("First", project_id=project.id, sprint_id=sprint.id)
    db.add_task("Second", project_id=project.id, sprint_id=sprint.id)
    db.kv_set("ui.active_project", f"project:{project.id}")
    db.kv_set("ui.active_sprint", str(sprint.id))
    return project.id, sprint.id, t1.id


@pytest.mark.asyncio
async def test_shift_r_opens_runner_when_active_sprint_present():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "sr.db")
        _seed_sprint_with_tasks(db)
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("R")
            await wait_for(pilot, SprintRunnerScreen)
        db.close()


@pytest.mark.asyncio
async def test_shift_r_noops_without_active_sprint():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "sr2.db")
        db.add_project("NoSprint")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("R")
            for _ in range(5):
                await pilot.pause()
                assert not isinstance(pilot.app.screen, SprintRunnerScreen)
        db.close()


@pytest.mark.asyncio
async def test_runner_enter_starts_focus_on_highlighted_task():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "sr3.db")
        _project_id, _sprint_id, first_task_id = _seed_sprint_with_tasks(db)
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("R")
            runner = await wait_for(pilot, SprintRunnerScreen)
            # First row is auto-cursored by DataTable.
            assert runner is not None
            await pilot.press("enter")
            await wait_for(pilot, DashboardScreen)
            assert app.active_task is not None
            assert app.active_task.id == first_task_id
        db.close()


@pytest.mark.asyncio
async def test_runner_close_with_retro_marks_sprint_completed():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "sr4.db")
        _, sprint_id, _ = _seed_sprint_with_tasks(db)
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("R")
            await wait_for(pilot, SprintRunnerScreen)
            await pilot.press("c")
            await wait_for(pilot, RetroModal)
            await pilot.press("g", "o", "o", "d")
            await pilot.press("enter")
            await wait_for(pilot, DashboardScreen)
            sp = db.get_sprint(sprint_id)
            assert sp.status == "completed"
            assert sp.retrospective == "good"
            assert app.active_sprint_id is None
        db.close()

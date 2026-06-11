"""Kanban A4: Sprint board / Project board / All tasks framing."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import pytest
from textual.widgets import Static

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.core.filters import ProjectFilter
from pomban.screens.kanban import KanbanScreen


async def _switch_to_kanban(pilot, app, max_pumps: int = 40) -> KanbanScreen:
    for _ in range(max_pumps):
        await pilot.pause()
        if app.screen.__class__.__name__ == "DashboardScreen":
            break
    app.action_switch("kanban")
    for _ in range(max_pumps):
        await pilot.pause()
        if isinstance(app.screen, KanbanScreen):
            return app.screen
    raise AssertionError("kanban never mounted")


def _framing(scr: KanbanScreen) -> str:
    return str(scr.query_one("#kanban-framing", Static).render())


@pytest.mark.asyncio
async def test_framing_all_tasks_no_filter():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _switch_to_kanban(pilot, app)
            assert "All tasks" in _framing(scr)
        db.close()


@pytest.mark.asyncio
async def test_framing_project_board_when_project_filtered():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        proj = db.add_project("release-week")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _switch_to_kanban(pilot, app)
            app.set_project_filter(ProjectFilter.project(proj.id))
            await pilot.pause()
            text = _framing(scr)
            assert "Project board" in text
            assert "release-week" in text
            assert "release-week" in scr.sub_title
        db.close()


@pytest.mark.asyncio
async def test_framing_sprint_board_with_progress_and_days_left():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        proj = db.add_project("api")
        today = dt.date.today()
        sp = db.add_sprint(
            project_id=proj.id,
            name="rollout",
            start_date=today.isoformat(),
            end_date=(today + dt.timedelta(days=5)).isoformat(),
            pomodoro_target=8,
            status="active",
        )
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _switch_to_kanban(pilot, app)
            app.set_project_filter(ProjectFilter.project(proj.id))
            app.set_active_sprint(sp.id)
            await pilot.pause()
            text = _framing(scr)
            assert "Sprint board" in text
            assert "rollout" in text
            assert "0/8" in text
            assert "5 days left" in text
        db.close()

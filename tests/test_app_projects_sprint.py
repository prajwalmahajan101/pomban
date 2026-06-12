"""Pilot test for the M3 ``s`` binding on ProjectsScreen.

Pressing ``s`` while a real project row is focused creates and activates
a sprint scoped to it. Pressing ``s`` on the synthetic Inbox row is a
no-op.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.projects import ProjectsScreen


async def wait_for(pilot, screen_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


@pytest.mark.asyncio
async def test_s_creates_and_activates_sprint_for_focused_project():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "ps.db")
        project = db.add_project("Demo")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("5")
            await wait_for(pilot, ProjectsScreen)
            # First row is the only real project — cursor lands on row 0 by default.
            await pilot.press("s")
            await pilot.pause()
            sprints = db.list_sprints(project_id=project.id)
            assert len(sprints) == 1
            assert sprints[0].status == "active"
            assert sprints[0].name == "Sprint 1"
            assert app.active_sprint_id == sprints[0].id
            assert app.project_filter.project_id == project.id
        db.close()


@pytest.mark.asyncio
async def test_s_noop_on_inbox_row():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "ps2.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("5")
            screen = await wait_for(pilot, ProjectsScreen)
            # No real projects — only the synthetic Inbox row exists.
            from textual.widgets import DataTable

            table = screen.query_one("#proj-table", DataTable)
            table.move_cursor(row=0)
            await pilot.press("s")
            await pilot.pause()
            assert db.list_sprints() == []
            assert app.active_sprint_id is None
        db.close()

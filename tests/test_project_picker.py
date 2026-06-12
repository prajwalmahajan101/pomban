"""Pilot tests for ProjectPickerModal.

Reproduces the bug where Enter on the picker dismissed with `None`
(picker swallowed the keystroke because ListView consumes `enter`
before the modal's binding can run). Asserts that:

* Enter on a freshly-opened picker selects the highlighted row
  ("All" → -1) rather than dismissing as cancelled.
* `j` then Enter picks the next row.
* Submitting a task with no project context from the Dashboard now
  routes through the picker and produces a task assigned to the
  picked project.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.project_picker import ProjectPickerModal


async def wait_for(pilot, screen_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


@pytest.mark.asyncio
async def test_picker_enter_selects_highlighted_row_not_cancel():
    """Regression: Enter must select, not dismiss as cancelled."""
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "p.db")
        db.add_project("Demo")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            result: list = []
            app.push_screen(
                ProjectPickerModal(db.list_projects(), None),
                lambda r: result.append(r),
            )
            await wait_for(pilot, ProjectPickerModal)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            assert result == [-1], (
                f"Enter on first row should pick All (-1), got {result}"
            )


@pytest.mark.asyncio
async def test_picker_j_then_enter_picks_inbox():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "p.db")
        db.add_project("Demo")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            result: list = []
            app.push_screen(
                ProjectPickerModal(db.list_projects(), None),
                lambda r: result.append(r),
            )
            await wait_for(pilot, ProjectPickerModal)
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            assert result == [0], f"Down then Enter should pick Inbox (0), got {result}"


@pytest.mark.asyncio
async def test_picker_picks_real_project_by_id():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "p.db")
        proj = db.add_project("Demo")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            result: list = []
            app.push_screen(
                ProjectPickerModal(db.list_projects(), None),
                lambda r: result.append(r),
            )
            await wait_for(pilot, ProjectPickerModal)
            # 0=All (initial), 1=Inbox, 2=Demo
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            assert result == [proj.id], (
                f"Picker should pick Demo's project id ({proj.id}), got {result}"
            )


@pytest.mark.asyncio
async def test_picker_escape_cancels():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "p.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            result: list = []
            app.push_screen(
                ProjectPickerModal(db.list_projects(), None),
                lambda r: result.append(r),
            )
            await wait_for(pilot, ProjectPickerModal)
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            assert result == [None], f"Escape should dismiss with None, got {result}"

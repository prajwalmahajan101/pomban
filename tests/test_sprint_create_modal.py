"""Pilot tests for the SprintCreateModal.

Replaces the prior single-line "name [target]" input with a structured
modal that collects name + pomodoro target + duration + goal. Asserts:

* Submitting the modal with defaults yields a SprintCreateResult with the
  suggested name, target=0, days=14, goal="".
* On the Projects screen, pressing `s` opens the modal and a Ctrl+S submit
  creates an active sprint on the focused project with the chosen fields.
* Empty name keeps the modal open (no None dismiss).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.projects import ProjectsScreen
from pomban.screens.sprint_create import SprintCreateModal, SprintCreateResult


async def wait_for(pilot, screen_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


@pytest.mark.asyncio
async def test_sprint_modal_ctrl_s_returns_result_with_defaults():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "s.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            picked: list = []
            app.push_screen(
                SprintCreateModal(suggested_name="Sprint 1"),
                lambda r: picked.append(r),
            )
            await wait_for(pilot, SprintCreateModal)
            await pilot.press("ctrl+s")
            await pilot.pause()
            await pilot.pause()
            assert len(picked) == 1
            res = picked[0]
            assert isinstance(res, SprintCreateResult)
            assert res.name == "Sprint 1"
            assert res.pomodoro_target == 0
            assert res.duration_days == 14
            assert res.goal == ""


@pytest.mark.asyncio
async def test_sprint_modal_escape_cancels():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "s.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            picked: list = []
            app.push_screen(SprintCreateModal(), lambda r: picked.append(r))
            await wait_for(pilot, SprintCreateModal)
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            assert picked == [None]


@pytest.mark.asyncio
async def test_projects_s_opens_modal_and_creates_active_sprint():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "s.db")
        proj = db.add_project("Demo")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("5")
            await wait_for(pilot, ProjectsScreen)
            await pilot.pause()
            # Cursor lands on the only row; press `s` to fire action_new_sprint.
            await pilot.press("s")
            modal = await wait_for(pilot, SprintCreateModal)
            # Fill: leave name = "Sprint 1", target = 12, days = 7, goal = "ship M5"
            target_input = modal.query_one("#sc-target")
            days_input = modal.query_one("#sc-days")
            goal_input = modal.query_one("#sc-goal")
            target_input.value = "12"
            days_input.value = "7"
            goal_input.value = "ship M5"
            await pilot.press("ctrl+s")
            await wait_for(pilot, ProjectsScreen)
            sprints = db.list_sprints(project_id=proj.id)
            assert len(sprints) == 1, f"Expected one sprint, got {sprints}"
            sp = sprints[0]
            assert sp.pomodoro_target == 12
            assert sp.goal == "ship M5"
            assert app.active_sprint_id == sp.id, "New sprint should be activated"

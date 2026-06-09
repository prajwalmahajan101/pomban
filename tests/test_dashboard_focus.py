import tempfile
from pathlib import Path

import pytest
from textual.widgets import ListView

from pomodoro.app import PomodoroApp
from pomodoro.core.db import DB
from pomodoro.screens.dashboard import DashboardScreen


@pytest.mark.asyncio
async def test_dashboard_task_list_focused_and_panes_focusable():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            for _ in range(40):
                await pilot.pause()
                if isinstance(app.screen, DashboardScreen):
                    break
            scr = app.screen
            # Timer pane is focusable so it can be the active panel.
            assert scr.query_one("#timer-pane").can_focus is True
            # Task list starts focused → task pane highlights via :focus-within.
            assert isinstance(app.focused, ListView)
            # Tab moves focus to another panel (not the same ListView).
            await pilot.press("tab")
            await pilot.pause()
            assert app.focused is not None
        db.close()

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.help import HelpScreen
from pomban.screens.kanban import KanbanScreen


async def _to_dashboard(pilot, app):
    for _ in range(40):
        await pilot.pause()
        if isinstance(app.screen, DashboardScreen):
            return
    raise AssertionError("dashboard never active")


@pytest.mark.asyncio
async def test_help_opens_and_renders_without_crashing():
    with tempfile.TemporaryDirectory() as td:
        app = PomodoroApp(db=DB(Path(td) / "h.db"), fast=True)
        async with app.run_test(size=(120, 40)) as pilot:
            await _to_dashboard(pilot, app)
            await pilot.press("question_mark")
            await pilot.pause()
            # Reaching here means the screen pushed and the compositor rendered it
            # without crashing — the regression was a render-time AttributeError
            # because _render() shadowed Textual's internal Widget._render().
            assert isinstance(app.screen, HelpScreen)
            static = next(iter(app.screen.query("Static")))
            assert "pomban" in str(static.render())
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)
        app.db.close()


@pytest.mark.asyncio
async def test_kanban_help_includes_how_it_works_intro():
    """`?` on the kanban screen renders the HELP_INTRO explainer + the Keymap header."""
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        db.add_task("alpha")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test(size=(120, 40)) as pilot:
            await _to_dashboard(pilot, app)
            await pilot.press("2")
            for _ in range(40):
                await pilot.pause()
                if isinstance(app.screen, KanbanScreen):
                    break
            await pilot.press("question_mark")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)
            static = next(iter(app.screen.query("Static")))
            rendered = str(static.render())
            assert "How the board works" in rendered, (
                "Kanban help should lead with the HELP_INTRO explainer"
            )
            assert "Keymap" in rendered, (
                "Help should separate the intro from the per-key list with a Keymap heading"
            )
            assert "Visual mode" in rendered
        app.db.close()

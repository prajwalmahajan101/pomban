"""Pilot tests for the Kanban screen task-selection regression.

Bug 1 (focus): the docked Input grabbed initial focus, so j/k/h/l were typed
into the input instead of firing the screen bindings — the cursor never
moved, no card got the `-focused` class.

Bug 2 (paint timing): `body.mount(TaskCard(...))` is async, but
`_paint_cursor()` ran synchronously immediately after — at that point the
DOM query returned an empty cards list, so the very first card never got
highlighted even if focus was correct.

These tests guard both:

* On mount, the focused widget is NOT the kanban input.
* After mount settles, the first To Do card carries the `-focused` class.
* Pressing `j` moves the focus marker to the next card.
* Pressing `n` switches focus to the input (add-card mode).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.config import Config
from pomban.core.db import DB
from pomban.screens.kanban import KanbanScreen
from pomban.widgets.card import TaskCard


async def wait_for(pilot, screen_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


def _todo_cards(screen: KanbanScreen) -> list[TaskCard]:
    body = screen.query_one("#body-todo")
    return list(body.query(TaskCard))


@pytest.mark.asyncio
async def test_kanban_mount_does_not_focus_input():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        db.add_task("alpha")
        db.add_task("beta")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test() as pilot:
            await pilot.press("2")
            await wait_for(pilot, KanbanScreen)
            inp = pilot.app.screen.query_one("#kanban-input")
            assert app.focused is not inp, (
                "Kanban input must not steal initial focus — j/k/h/l would be typed into it"
            )


@pytest.mark.asyncio
async def test_kanban_first_card_is_focused_after_mount():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        db.add_task("alpha")
        db.add_task("beta")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test() as pilot:
            await pilot.press("2")
            kb = await wait_for(pilot, KanbanScreen)
            # call_after_refresh defers the first paint by one frame.
            await pilot.pause()
            await pilot.pause()
            cards = _todo_cards(kb)
            assert cards, "Expected at least one TaskCard in To Do"
            focused = [c for c in cards if c.has_class("-focused")]
            assert len(focused) == 1, (
                f"Exactly one card should carry the -focused class on mount, "
                f"got {len(focused)}: {[(c.task_data.title, c.classes) for c in cards]}"
            )
            assert focused[0] is cards[0], "First card should be the focused one"


@pytest.mark.asyncio
async def test_kanban_j_moves_focus_to_next_card():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        db.add_task("alpha")
        db.add_task("beta")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test() as pilot:
            await pilot.press("2")
            kb = await wait_for(pilot, KanbanScreen)
            await pilot.pause()
            await pilot.pause()
            await pilot.press("j")
            await pilot.pause()
            cards = _todo_cards(kb)
            focused = [c for c in cards if c.has_class("-focused")]
            assert len(focused) == 1
            # Cards are sorted by priority then due then position. Without explicit
            # priorities, the original insertion order is reversed by `position DESC`
            # in the DB layer, so `beta` is row 0 and `alpha` is row 1. We just
            # assert that pressing `j` moved focus off card 0 and onto card 1.
            assert focused[0] is cards[1], (
                f"After `j`, focused card should be row 1, got "
                f"{focused[0].task_data.title!r} vs row1={cards[1].task_data.title!r}"
            )


@pytest.mark.asyncio
async def test_kanban_n_focuses_input_for_add_card():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        db.add_task("alpha")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test() as pilot:
            await pilot.press("2")
            kb = await wait_for(pilot, KanbanScreen)
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            inp = kb.query_one("#kanban-input")
            assert app.focused is inp, "After pressing `n`, the kanban input should hold focus"

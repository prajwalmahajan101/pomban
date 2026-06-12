"""Tests for the M3 FirstRunModal: empty-DB launch seeds an initial project."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.first_run import FirstRunModal


async def wait_for_modal(pilot, cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, cls):
            return pilot.app.screen
    raise AssertionError(f"{cls.__name__} never became active: {type(pilot.app.screen)}")


async def wait_until(pilot, predicate, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if predicate():
            return
    raise AssertionError("predicate never satisfied")


@pytest.mark.asyncio
async def test_first_run_modal_creates_and_activates_project():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "fr.db")
        assert db.list_projects() == []
        app = PomodoroApp(db=db, fast=True, first_run_check=True)
        async with app.run_test() as pilot:
            await wait_for_modal(pilot, FirstRunModal)
            await pilot.press("D", "e", "m", "o")
            await pilot.press("enter")
            await wait_until(pilot, lambda: len(db.list_projects()) == 1)
            project = db.list_projects()[0]
            assert project.name == "Demo"
            assert app.project_filter.project_id == project.id
        db.close()


@pytest.mark.asyncio
async def test_first_run_modal_skip_leaves_db_empty():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "fr2.db")
        app = PomodoroApp(db=db, fast=True, first_run_check=True)
        async with app.run_test() as pilot:
            await wait_for_modal(pilot, FirstRunModal)
            await pilot.press("escape")
            await pilot.pause()
            assert db.list_projects() == []
        db.close()


@pytest.mark.asyncio
async def test_first_run_modal_skipped_when_projects_exist():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "fr3.db")
        db.add_project("Existing")
        app = PomodoroApp(db=db, fast=True, first_run_check=True)
        async with app.run_test() as pilot:
            # Modal should never appear — let the event loop run, then assert.
            for _ in range(10):
                await pilot.pause()
                assert not isinstance(pilot.app.screen, FirstRunModal)
        db.close()

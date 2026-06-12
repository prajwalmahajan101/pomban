"""Pilot tests for the startup help (welcome walkthrough + per-launch tip).

Asserts the user-visible contract:

* ``pick_next_tip`` rotates through ``TIPS`` deterministically and wraps.
* On first launch with ``show_startup_tips = true``, the ``WelcomeModal``
  pushes; on subsequent launches a ``StartupTipModal`` pushes instead.
* ``show_startup_tips = false`` suppresses both surfaces entirely.

The startup-help flow itself is gated by ``first_run_check=True`` (the
production default). Tests pass ``fast=False`` to enable it deliberately.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.config import Config, UISection
from pomban.core.db import DB
from pomban.screens.welcome import (
    TIPS,
    StartupTipModal,
    WelcomeModal,
    pick_next_tip,
)


async def wait_until_modal(pilot, modal_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        # Walk the screen stack looking for our modal.
        for scr in list(pilot.app.screen_stack):
            if isinstance(scr, modal_cls):
                return scr
    return None


def test_pick_next_tip_rotates_and_wraps():
    assert TIPS, "TIPS must not be empty"
    first, idx1 = pick_next_tip(0)
    assert first == TIPS[0]
    assert idx1 == 1 % len(TIPS)
    # Wraparound: an index past the end maps back.
    over, _ = pick_next_tip(len(TIPS) + 3)
    assert over == TIPS[3 % len(TIPS)]


@pytest.mark.asyncio
async def test_welcome_modal_pushes_on_first_launch():
    """First launch (no `welcome_seen` KV row) → WelcomeModal opens."""
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "w.db")
        # Seed a project so the FirstRunModal doesn't fire and confuse the stack.
        db.add_project("Inbox")
        cfg = Config()
        cfg.ui = UISection(show_startup_tips=True)
        # fast=False + first_run_check=True enables the startup-help gate.
        app = PomodoroApp(db=db, fast=False, config=cfg, first_run_check=True)
        async with app.run_test() as pilot:
            modal = await wait_until_modal(pilot, WelcomeModal)
            assert modal is not None, "WelcomeModal should open on first launch"
            # Stack should now record we've seen it.
            assert db.kv_get("welcome_seen") == "1"


@pytest.mark.asyncio
async def test_tip_modal_pushes_on_subsequent_launch():
    """Second launch (welcome_seen=1) → StartupTipModal opens, tip_index advances."""
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "w.db")
        db.add_project("Inbox")
        db.kv_set("welcome_seen", "1")
        cfg = Config()
        cfg.ui = UISection(show_startup_tips=True)
        app = PomodoroApp(db=db, fast=False, config=cfg, first_run_check=True)
        async with app.run_test() as pilot:
            modal = await wait_until_modal(pilot, StartupTipModal)
            assert modal is not None, "StartupTipModal should open on subsequent launch"
            # Index advanced from 0 → 1 (wrap-safe for short TIPS lists).
            assert db.kv_get("tip_index") == str(1 % len(TIPS))


@pytest.mark.asyncio
async def test_show_startup_tips_false_suppresses_both():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "w.db")
        db.add_project("Inbox")
        cfg = Config()
        cfg.ui = UISection(show_startup_tips=False)
        app = PomodoroApp(db=db, fast=False, config=cfg, first_run_check=True)
        async with app.run_test() as pilot:
            welcome = await wait_until_modal(pilot, WelcomeModal, tries=15)
            tip = await wait_until_modal(pilot, StartupTipModal, tries=15)
            assert welcome is None and tip is None, (
                "show_startup_tips=False must suppress both modals"
            )
            assert db.kv_get("welcome_seen") is None, "Disabled flow should not mark welcome_seen"

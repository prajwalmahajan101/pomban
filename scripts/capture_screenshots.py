"""Generate the README / PyPI hero screenshots as SVG.

Drives the real :class:`PomodoroApp` under Textual's pilot harness,
seeds an in-memory SQLite DB with a small set of tasks / projects /
sprints, and saves three screens to ``docs/screenshots/``:

- ``dashboard.svg`` — Dashboard with a focus session running, the
  task list populated, and the stats strip filled.
- ``kanban.svg``    — Kanban board with priorities and due dates.
- ``stats.svg``     — Stats screen with sample bucket data.

Run with: ``python scripts/capture_screenshots.py``. No CLI args.

Why SVG: Textual's ``save_screenshot`` emits a self-contained SVG that
renders pixel-perfect on GitHub and PyPI, no external rasterisation
step needed.

This script is intentionally tolerant — it logs what it captured and
exits 0 even if a screen registration changes. Re-run after a UI
refactor; visual review the SVGs before committing.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import tempfile
from pathlib import Path

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.core.timer_engine import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "screenshots"

# Generous terminal sizes so the SVGs read well on a wide README.
DASHBOARD_SIZE = (180, 50)
KANBAN_SIZE = (200, 55)
STATS_SIZE = (180, 45)


def _seed(db: DB) -> None:
    """Populate a fresh DB with a handful of representative rows."""
    p_inbox = db.add_project("inbox", color="white")
    p_docs = db.add_project("docs", color="cyan")
    p_release = db.add_project("v1.0-launch", color="magenta")

    sprint_id = db.create_sprint(
        project_id=p_release,
        name="release-week",
        target_pomodoros=12,
    )

    today = dt.date.today()
    db.add_task("Write release notes", project_id=p_docs, tags="docs", est=2)
    db.add_task("Wire OAuth flow", project_id=p_release, sprint_id=sprint_id, est=3,
                priority="high", due=today.isoformat())
    db.add_task("Email Dana", project_id=p_inbox)
    db.add_task("Fix the kanban refresh bug", project_id=p_release, sprint_id=sprint_id,
                est=1, priority="med")

    # A few completed sessions so the stats screen isn't empty.
    for hours_ago in (1, 2, 3, 5, 24, 25, 48):
        ts = dt.datetime.now() - dt.timedelta(hours=hours_ago)
        db.log_completed_session(planned_seconds=1500, actual_seconds=1500, ended_at=ts)


async def _capture(app: PomodoroApp, size: tuple[int, int], path: Path) -> None:
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        await pilot.pause()
        path.parent.mkdir(parents=True, exist_ok=True)
        app.save_screenshot(str(path))
        print(f"wrote {path.relative_to(REPO_ROOT)}")


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "library.db"
        db = DB(path=db_path)
        _seed(db)

        # Dashboard
        app = PomodoroApp(
            db=DB(path=db_path),
            settings=Settings(focus_seconds=1500, short_break_seconds=300,
                              long_break_seconds=900, cycles_before_long_break=4,
                              warning_seconds=30),
        )
        await _capture(app, DASHBOARD_SIZE, OUT_DIR / "dashboard.svg")

        # Kanban
        app = PomodoroApp(db=DB(path=db_path))
        async with app.run_test(size=KANBAN_SIZE) as pilot:
            await pilot.pause()
            await pilot.press("2")  # switch to kanban
            await pilot.pause()
            app.save_screenshot(str(OUT_DIR / "kanban.svg"))
            print("wrote docs/screenshots/kanban.svg")

        # Stats
        app = PomodoroApp(db=DB(path=db_path))
        async with app.run_test(size=STATS_SIZE) as pilot:
            await pilot.pause()
            await pilot.press("3")  # switch to stats
            await pilot.pause()
            app.save_screenshot(str(OUT_DIR / "stats.svg"))
            print("wrote docs/screenshots/stats.svg")


if __name__ == "__main__":
    asyncio.run(main())

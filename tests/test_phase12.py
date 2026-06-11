import tempfile
from pathlib import Path

import pytest

from pomban.core.config import Preset
from pomban.core.db import DB
from pomban.core.exporter import export_markdown
from pomban.notifications import run_hook


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as td:
        d = DB(Path(td) / "p.db")
        yield d
        d.close()


def test_export_markdown_contains_expected_sections(db):
    t = db.add_task("Demo")
    sid = db.start_session("focus", 1500, [t.id])
    db.end_session(sid, actual_seconds=1500, completed=True)
    out = export_markdown(db, days=7)
    assert out.startswith("# Pomodoro review")
    assert "focus sessions" in out
    assert "## Top tasks" in out
    assert "Demo" in out
    assert "## Daily breakdown" in out


def test_export_empty_db_does_not_crash(db):
    out = export_markdown(db, days=7)
    assert "# Pomodoro review" in out
    assert "Daily breakdown" in out


def test_hook_writes_to_log_and_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    marker = tmp_path / "marker.txt"
    run_hook(f"echo hooked > {marker}", env_extra={"FOO": "bar"})
    # Give the spawned shell a moment
    import time

    for _ in range(30):
        if marker.exists():
            break
        time.sleep(0.05)
    assert marker.exists()
    assert marker.read_text().strip() == "hooked"


def test_hook_with_missing_command_is_silent():
    # None/empty must not raise even without XDG_STATE_HOME set.
    run_hook(None)
    run_hook("")


def test_preset_dataclass_construction():
    p = Preset(name="deep", focus_minutes=50)
    assert p.name == "deep"
    assert p.short_break_minutes == 5
    assert p.cycles_before_long_break == 4

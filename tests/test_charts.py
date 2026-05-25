"""Tests for Phase N: sessions_by_bucket aggregation and chart widget rendering."""
from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from pomodoro.core.db import DB
from pomodoro.widgets.bar_chart import render_bars, render_vertical_bars
from pomodoro.widgets.sparkline import render_sparkline


@pytest.fixture
def db():
    p = Path(tempfile.mktemp(suffix=".db"))
    d = DB(p)
    yield d
    d.close()
    p.unlink(missing_ok=True)


def test_sessions_by_bucket_day_returns_n_buckets(db):
    out = db.sessions_by_bucket("day", n_buckets=7)
    assert len(out) == 7
    # All zero counts since no sessions
    assert all(mins == 0 for _, mins, _ in out)


def test_sessions_by_bucket_week_and_month(db):
    assert len(db.sessions_by_bucket("week", n_buckets=4)) == 4
    assert len(db.sessions_by_bucket("month", n_buckets=3)) == 3


def test_sessions_by_bucket_picks_up_completed_sessions(db):
    # Insert a focus session for today
    today = date.today().isoformat() + "T10:00:00"
    db.conn.execute(
        "INSERT INTO sessions (kind, started_at, planned_seconds, actual_seconds, completed)"
        " VALUES ('focus', ?, 1500, 1500, 1)",
        (today,),
    )
    db.conn.commit()
    out = db.sessions_by_bucket("day", n_buckets=1)
    assert out[-1][1] == 25  # 1500s = 25 min


def test_render_bars_empty():
    assert "no data" in render_bars([])


def test_render_bars_basic():
    text = render_bars([("a", 1), ("b", 2)], width=4)
    assert "a" in text and "b" in text


def test_render_vertical_bars_empty():
    assert "no data" in render_vertical_bars([])


def test_sparkline_empty():
    assert "—" in render_sparkline([])


def test_sparkline_renders_blocks():
    out = render_sparkline([1.0, 2.0, 3.0])
    # Should contain colored block characters
    assert any(c in out for c in "▁▂▃▄▅▆▇█")


def test_project_analytics_returns_keys(db):
    p = db.get_or_create_project("x")
    an = db.project_analytics(p.id)
    for key in ("total_minutes", "week_minutes", "month_minutes",
                "active_days", "avg_per_active_day_minutes",
                "last_session", "dow_minutes", "estimate_ratio"):
        assert key in an
    assert len(an["dow_minutes"]) == 7


def test_tag_color_stable_across_calls():
    from pomodoro.widgets.card import tag_color
    assert tag_color("backend") == tag_color("backend")


def test_stable_index_is_deterministic():
    from pomodoro.core.colors import stable_index
    assert stable_index("hello", 8) == stable_index("hello", 8)
    assert 0 <= stable_index("anything", 5) < 5


def test_no_color_strips_markup(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    from pomodoro.core.colors import adapt, paint
    assert adapt("bright_cyan") == ""
    assert paint("x", "red") == "x"

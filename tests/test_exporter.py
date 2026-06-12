"""Tests for M4 structured exports (markdown / CSV / JSON)."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta

import pytest

from pomban.core.db import DB
from pomban.core.exporter import export_csv, export_json, export_markdown


@pytest.fixture
def seeded_db(tmp_path):
    db = DB(tmp_path / "ex.db")
    project = db.add_project("Demo")
    sprint = db.add_sprint(
        project.id,
        "S1",
        date.today().isoformat(),
        (date.today() + timedelta(days=14)).isoformat(),
        pomodoro_target=4,
    )
    db.activate_sprint(sprint.id)
    db.add_task("Slides", project_id=project.id, sprint_id=sprint.id, tags="deep,writing")
    standup = db.add_task("Standup", project_id=project.id, tags="meeting")
    sid = db.start_session("focus", planned_seconds=1500, task_ids=[standup.id])
    db.end_session(sid, actual_seconds=1500, completed=True)
    db.update_session(sid, notes="solid sync")
    yield db
    db.close()


# ---------- markdown ----------


def test_markdown_default_contains_window_and_counts(seeded_db):
    out = export_markdown(seeded_db, days=7)
    assert "Pomodoro review" in out
    assert "**1** focus sessions" in out
    assert "Top tasks" in out
    assert "Standup" in out


def test_markdown_group_by_project_lists_project_block(seeded_db):
    out = export_markdown(seeded_db, days=7, group_by="project")
    assert "By project" in out
    assert "Demo" in out


def test_markdown_group_by_sprint_lists_sprint_block(seeded_db):
    out = export_markdown(seeded_db, days=7, group_by="sprint")
    assert "By sprint" in out
    assert "S1" in out


def test_markdown_group_by_tag_lists_tag_block(seeded_db):
    out = export_markdown(seeded_db, days=7, group_by="tag")
    assert "By tag" in out
    assert "#meeting" in out


def test_markdown_rejects_invalid_group_by(seeded_db):
    with pytest.raises(ValueError):
        export_markdown(seeded_db, days=7, group_by="bogus")


# ---------- CSV ----------


def test_csv_header_and_row_count(seeded_db):
    out = export_csv(seeded_db, days=7)
    reader = csv.reader(io.StringIO(out))
    rows = list(reader)
    assert rows[0][0] == "started_at"
    assert "notes" in rows[0]
    # One seeded focus session.
    assert len(rows) == 2
    body = rows[1]
    assert "solid sync" in body
    assert "Standup" in body[-1]


# ---------- JSON ----------


def test_json_parses_with_expected_top_level_keys(seeded_db):
    out = export_json(seeded_db, days=7)
    payload = json.loads(out)
    assert set(payload.keys()) == {"window", "sessions", "tasks", "sprints"}
    assert payload["window"]["days"] == 7
    assert len(payload["sessions"]) == 1
    assert payload["sessions"][0]["notes"] == "solid sync"
    # Tasks carry project + sprint linkage
    assert any(t["sprint_id"] is not None for t in payload["tasks"])
    # Sprints carry target + completed + pct
    assert all({"pomodoro_target", "completed", "pct"} <= set(s.keys()) for s in payload["sprints"])


# ---------- CLI parser ----------


def test_cli_parse_export_args_defaults():
    from pomban.__main__ import _parse_export_args

    assert _parse_export_args([]) == (7, "markdown", None)


def test_cli_parse_export_args_full():
    from pomban.__main__ import _parse_export_args

    days, fmt, group = _parse_export_args(
        ["--since", "14d", "--format", "json", "--group-by", "project"]
    )
    assert (days, fmt, group) == (14, "json", "project")


def test_cli_parse_export_args_md_alias():
    from pomban.__main__ import _parse_export_args

    _, fmt, _ = _parse_export_args(["--format", "md"])
    assert fmt == "markdown"


def test_cli_parse_export_args_rejects_bad_format():
    from pomban.__main__ import _parse_export_args

    _, fmt, _ = _parse_export_args(["--format", "xml"])
    # Bad format silently keeps default; CLI mirrors the existing tolerant style.
    assert fmt == "markdown"

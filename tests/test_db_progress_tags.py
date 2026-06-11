"""DB helpers added in v0.2.0 M1: sprint_progress + minutes_per_tag."""

from __future__ import annotations

import datetime as dt
from datetime import date, timedelta

import pytest

from pomban.core.db import DB


def _seed_session(db: DB, task_id: int, *, started_at: str | None = None) -> int:
    sid = db.start_session("focus", planned_seconds=1500, task_ids=[task_id])
    db.end_session(sid, actual_seconds=1500, completed=True)
    if started_at:
        db.conn.execute("UPDATE sessions SET started_at=? WHERE id=?", (started_at, sid))
        db.conn.commit()
    return sid


# --- sprint_progress ----------------------------------------------------


def test_sprint_progress_mid_window(tmp_path):
    db = DB(path=tmp_path / "s.db")
    proj = db.add_project("p").id
    today = date.today()
    sp = db.add_sprint(
        project_id=proj,
        name="api",
        start_date=(today - timedelta(days=7)).isoformat(),
        end_date=(today + timedelta(days=7)).isoformat(),
        pomodoro_target=10,
        status="active",
    )
    in_sprint = [db.add_task(f"t{i}", project_id=proj, sprint_id=sp.id).id for i in range(3)]
    out_of_sprint = db.add_task("orphan", project_id=proj).id
    for tid in (in_sprint[0], in_sprint[0], in_sprint[1], in_sprint[2]):
        _seed_session(db, tid)
    _seed_session(db, out_of_sprint)  # must be excluded

    p = db.sprint_progress(sp.id)
    assert p["target"] == 10
    assert p["completed"] == 4
    assert p["pct"] == 40
    assert p["days_left"] == 7
    assert isinstance(p["pace"], int)
    assert p["on_track"] == (p["pace"] >= 0)
    db.close()


def test_sprint_progress_zero_target(tmp_path):
    db = DB(path=tmp_path / "s.db")
    today = date.today()
    sp = db.add_sprint(
        project_id=None,
        name="loose",
        start_date=today.isoformat(),
        end_date=(today + timedelta(days=7)).isoformat(),
        pomodoro_target=0,
    )
    p = db.sprint_progress(sp.id)
    assert p["target"] == 0
    assert p["pct"] == 0
    assert p["completed"] == 0
    db.close()


def test_sprint_progress_malformed_dates(tmp_path):
    db = DB(path=tmp_path / "s.db")
    sp = db.add_sprint(
        project_id=None, name="bad", start_date="nope", end_date="", pomodoro_target=5
    )
    p = db.sprint_progress(sp.id)
    assert p["days_left"] == 0
    assert p["pace"] == 0
    assert p["on_track"] is True
    db.close()


# --- minutes_per_tag ----------------------------------------------------


def test_minutes_per_tag_basic(tmp_path):
    db = DB(path=tmp_path / "t.db")
    proj = db.add_project("p").id
    docs = db.add_task("write notes", project_id=proj, tags="docs").id
    both = db.add_task("ship launch", project_id=proj, tags="docs,launch").id
    bare = db.add_task("misc", project_id=proj, tags="").id
    launch = db.add_task("press release", project_id=proj, tags="launch").id

    _seed_session(db, docs)
    _seed_session(db, both)
    _seed_session(db, bare)  # excluded — no tags
    _seed_session(db, launch)

    result = db.minutes_per_tag()
    # docs: 25 (docs) + 25 (both) = 50; launch: 25 (both) + 25 (launch) = 50
    as_dict = dict(result)
    assert as_dict == {"docs": 50, "launch": 50}
    db.close()


def test_minutes_per_tag_project_filter(tmp_path):
    db = DB(path=tmp_path / "t.db")
    p1 = db.add_project("p1").id
    p2 = db.add_project("p2").id
    t1 = db.add_task("a", project_id=p1, tags="docs").id
    t2 = db.add_task("b", project_id=p2, tags="docs").id
    _seed_session(db, t1)
    _seed_session(db, t2)

    assert dict(db.minutes_per_tag(project_id=p1)) == {"docs": 25}
    assert dict(db.minutes_per_tag(project_id=p2)) == {"docs": 25}
    assert dict(db.minutes_per_tag()) == {"docs": 50}
    db.close()


def test_minutes_per_tag_time_window(tmp_path):
    db = DB(path=tmp_path / "t.db")
    t = db.add_task("a", tags="docs").id
    _seed_session(db, t)  # today
    old_iso = (dt.datetime.now() - dt.timedelta(days=60)).isoformat(timespec="seconds")
    _seed_session(db, t, started_at=old_iso)  # 60 days back

    in_window = dict(db.minutes_per_tag(since_days=30))
    full = dict(db.minutes_per_tag(since_days=365))
    assert in_window == {"docs": 25}
    assert full == {"docs": 50}
    db.close()


def test_minutes_per_tag_sort_order(tmp_path):
    db = DB(path=tmp_path / "t.db")
    t_a = db.add_task("a", tags="alpha").id
    t_b = db.add_task("b", tags="beta").id
    _seed_session(db, t_a)
    _seed_session(db, t_b)
    _seed_session(db, t_b)

    out = db.minutes_per_tag()
    assert [tag for tag, _ in out] == ["beta", "alpha"]
    assert out[0][1] >= out[1][1]
    db.close()


@pytest.mark.parametrize("tags", ["", "  ", ",,"])
def test_minutes_per_tag_skips_blank_tags(tmp_path, tags):
    db = DB(path=tmp_path / "t.db")
    t = db.add_task("a", tags=tags).id
    _seed_session(db, t)
    assert db.minutes_per_tag() == []
    db.close()

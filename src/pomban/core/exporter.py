"""Exports — pure functions over DB data producing markdown / CSV / JSON.

Each function returns a ``str`` so the CLI can write straight to stdout (or
redirect). ``export_markdown`` accepts an optional ``group_by ∈
{"project", "sprint", "tag"}`` that re-buckets the top-tasks block; CSV / JSON
ship flat session rows + structured task / sprint blocks so downstream tools
can group themselves.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta

from pomban.core.db import DB

_GROUP_KEYS = ("project", "sprint", "tag")


def _fmt(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _window(days: int) -> tuple[date, date]:
    end = date.today()
    return end - timedelta(days=days - 1), end


def _in_window(row: dict, start: date, end: date) -> bool:
    return start.isoformat() <= row["started_at"][:10] <= end.isoformat()


# ---------- markdown ----------


def export_markdown(db: DB, days: int = 7, group_by: str | None = None) -> str:
    if group_by is not None and group_by not in _GROUP_KEYS:
        raise ValueError(f"group_by must be one of {_GROUP_KEYS}, got {group_by!r}")
    start, end = _window(days)
    daily = db.daily_focus_minutes(days)
    total_minutes = sum(m for _, m in daily)
    sessions = [
        r for r in db.session_history(10_000) if r["kind"] == "focus" and _in_window(r, start, end)
    ]
    total_sessions = sum(1 for r in sessions if r["completed"])
    streak = db.stats_today()["streak"]

    lines: list[str] = []
    lines.append(f"# Pomodoro review — {start.isoformat()} → {end.isoformat()}")
    lines.append("")
    lines.append(f"- **{total_sessions}** focus sessions ({_fmt(total_minutes)})")
    lines.append(f"- Streak: **{streak}** day(s)")
    lines.append(f"- Avg interruptions / focus: **{db.avg_interruptions_per_focus():.1f}**")
    lines.append("")

    if group_by is None:
        top = db.top_tasks(10)
        if top:
            lines.append("## Top tasks")
            for title, mins in top:
                lines.append(f"- {title} — {_fmt(mins)}")
            lines.append("")
    elif group_by == "project":
        lines.append("## By project (last 30 days)")
        rows = db.sessions_per_project(since_days=30)
        if not rows:
            lines.append("- _(no sessions)_")
        else:
            for name, _color, n, secs in rows:
                lines.append(f"- {name} — {n} session(s), {_fmt(int(secs) // 60)}")
        lines.append("")
    elif group_by == "sprint":
        lines.append("## By sprint")
        sprints = db.list_sprints()
        if not sprints:
            lines.append("- _(no sprints)_")
        else:
            for sp in sprints:
                prog = db.sprint_progress(sp.id)
                lines.append(f"- {sp.name} ({sp.status}) — {prog['completed']}/{prog['target']} 🍅")
        lines.append("")
    else:  # tag
        lines.append("## By tag (last 30 days)")
        rows = db.minutes_per_tag(since_days=30)
        if not rows:
            lines.append("- _(no tagged sessions)_")
        else:
            for tag, mins in rows:
                lines.append(f"- #{tag} — {_fmt(mins)}")
        lines.append("")

    lines.append("## Daily breakdown")
    lines.append("| Date | Minutes |")
    lines.append("|------|---------|")
    for d, m in daily:
        lines.append(f"| {d} | {m} |")
    return "\n".join(lines)


# ---------- CSV ----------

_CSV_COLUMNS = [
    "started_at",
    "ended_at",
    "kind",
    "projects",
    "planned_seconds",
    "actual_seconds",
    "completed",
    "interruption_count",
    "notes",
    "task_titles",
]


def export_csv(db: DB, days: int = 7, group_by: str | None = None) -> str:
    # group_by accepted for signature parity; CSV ships flat session rows.
    _ = group_by
    start, end = _window(days)
    rows = [r for r in db.session_history(10_000) if _in_window(r, start, end)]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_COLUMNS)
    for r in rows:
        writer.writerow(
            [
                r.get("started_at", "") or "",
                r.get("ended_at", "") or "",
                r.get("kind", "") or "",
                r.get("projects", "") or "",
                r.get("planned_seconds", 0) or 0,
                r.get("actual_seconds", 0) or 0,
                int(r.get("completed", 0) or 0),
                r.get("interruption_count", 0) or 0,
                (r["notes"] if "notes" in r.keys() else "") or "",
                r.get("task_titles", "") or "",
            ]
        )
    return buf.getvalue()


# ---------- JSON ----------


def export_json(db: DB, days: int = 7, group_by: str | None = None) -> str:
    # group_by accepted for signature parity; JSON ships structured blocks
    # so downstream consumers can group however they want.
    _ = group_by
    start, end = _window(days)
    sessions = [
        {
            "started_at": r.get("started_at"),
            "ended_at": r.get("ended_at"),
            "kind": r.get("kind"),
            "projects": r.get("projects") or "",
            "planned_seconds": r.get("planned_seconds", 0),
            "actual_seconds": r.get("actual_seconds", 0),
            "completed": bool(r.get("completed", 0)),
            "interruption_count": r.get("interruption_count", 0),
            "notes": (r["notes"] if "notes" in r.keys() else "") or "",
            "task_titles": r.get("task_titles") or "",
        }
        for r in db.session_history(10_000)
        if _in_window(r, start, end)
    ]
    tasks = [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "tags": t.tags,
            "estimated_pomodoros": t.estimated_pomodoros,
            "project_id": t.project_id,
            "sprint_id": t.sprint_id,
        }
        for t in db.list_tasks(include_done=True)
    ]
    sprints = []
    for sp in db.list_sprints():
        prog = db.sprint_progress(sp.id)
        sprints.append(
            {
                "id": sp.id,
                "name": sp.name,
                "project_id": sp.project_id,
                "status": sp.status,
                "pomodoro_target": sp.pomodoro_target,
                "completed": prog["completed"],
                "pct": prog["pct"],
                "start_date": sp.start_date,
                "end_date": sp.end_date,
                "retrospective": sp.retrospective,
            }
        )
    payload = {
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "sessions": sessions,
        "tasks": tasks,
        "sprints": sprints,
    }
    return json.dumps(payload, indent=2)

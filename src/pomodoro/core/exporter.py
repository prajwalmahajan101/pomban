"""Markdown export for daily/weekly review. Pure function on DB data."""
from __future__ import annotations

from datetime import date, timedelta

from pomodoro.core.db import DB


def _fmt(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def export_markdown(db: DB, days: int = 7) -> str:
    end = date.today()
    start = end - timedelta(days=days - 1)
    daily = db.daily_focus_minutes(days)
    total_minutes = sum(m for _, m in daily)
    total_sessions = sum(1 for r in db.session_history(10_000)
                         if r["kind"] == "focus" and r["completed"]
                         and start.isoformat() <= r["started_at"][:10] <= end.isoformat())
    streak = db.stats_today()["streak"]
    top = db.top_tasks(10)

    lines = []
    lines.append(f"# Pomodoro review — {start.isoformat()} → {end.isoformat()}")
    lines.append("")
    lines.append(f"- **{total_sessions}** focus sessions ({_fmt(total_minutes)})")
    lines.append(f"- Streak: **{streak}** day(s)")
    lines.append(f"- Avg interruptions / focus: **{db.avg_interruptions_per_focus():.1f}**")
    lines.append("")
    if top:
        lines.append("## Top tasks")
        for title, mins in top:
            lines.append(f"- {title} — {_fmt(mins)}")
        lines.append("")
    lines.append("## Daily breakdown")
    lines.append("| Date | Minutes |")
    lines.append("|------|---------|")
    for d, m in daily:
        lines.append(f"| {d} | {m} |")
    return "\n".join(lines)

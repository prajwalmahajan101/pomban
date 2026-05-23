"""SQLite persistence. XDG data dir, schema migrations via PRAGMA user_version."""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from pomodoro.core.models import Task

SCHEMA_VERSION = 2


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "pomodoro"


def default_db_path() -> Path:
    return default_data_dir() / "pomodoro.db"


class DB:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        cur = self.conn.execute("PRAGMA user_version")
        version = cur.fetchone()[0]
        if version < 1:
            self.conn.executescript(
                """
                CREATE TABLE tasks (
                  id INTEGER PRIMARY KEY,
                  title TEXT NOT NULL,
                  status TEXT NOT NULL CHECK(status IN ('todo','doing','done')),
                  tags TEXT DEFAULT '',
                  estimated_pomodoros INTEGER DEFAULT 0,
                  position INTEGER DEFAULT 0,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE sessions (
                  id INTEGER PRIMARY KEY,
                  kind TEXT NOT NULL CHECK(kind IN ('focus','short_break','long_break')),
                  started_at TEXT NOT NULL,
                  ended_at TEXT,
                  planned_seconds INTEGER NOT NULL,
                  actual_seconds INTEGER NOT NULL DEFAULT 0,
                  completed INTEGER NOT NULL DEFAULT 0,
                  interruption_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE session_tasks (
                  session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
                  task_id INTEGER REFERENCES tasks(id),
                  completed_during_session INTEGER DEFAULT 0,
                  PRIMARY KEY (session_id, task_id)
                );
                CREATE TABLE config_kv (key TEXT PRIMARY KEY, value TEXT);
                """
            )
            self.conn.execute("PRAGMA user_version = 1")
            self.conn.commit()
            version = 1
        if version < 2:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS interruptions (
                  id INTEGER PRIMARY KEY,
                  session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
                  at TEXT NOT NULL,
                  reason TEXT DEFAULT ''
                );
                """
            )
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.conn.commit()

    # ---------- tasks ----------
    def add_task(self, title: str, tags: str = "", estimated_pomodoros: int = 0) -> Task:
        now = _now_iso()
        cur = self.conn.execute(
            "INSERT INTO tasks (title, status, tags, estimated_pomodoros, position, created_at, updated_at)"
            " VALUES (?, 'todo', ?, ?, COALESCE((SELECT MAX(position)+1 FROM tasks WHERE status='todo'), 0), ?, ?)",
            (title, tags, estimated_pomodoros, now, now),
        )
        self.conn.commit()
        return self.get_task(cur.lastrowid)

    def get_task(self, task_id: int) -> Task:
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return _row_to_task(row)

    def list_tasks(self, status: str | None = None, tag: str | None = None) -> list[Task]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY position, id", (status,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE status != 'done' ORDER BY status DESC, position, id"
            ).fetchall()
        tasks = [_row_to_task(r) for r in rows]
        if tag:
            tag_low = tag.lower().lstrip("#")
            tasks = [t for t in tasks if tag_low in {x.strip().lower() for x in (t.tags or "").split(",") if x.strip()}]
        return tasks

    def all_tags(self) -> list[str]:
        rows = self.conn.execute("SELECT DISTINCT tags FROM tasks WHERE tags != ''").fetchall()
        out: set[str] = set()
        for r in rows:
            for t in (r["tags"] or "").split(","):
                t = t.strip()
                if t:
                    out.add(t)
        return sorted(out)

    def update_task(self, task_id: int, **fields) -> None:
        if not fields:
            return
        fields["updated_at"] = _now_iso()
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE tasks SET {cols} WHERE id=?", (*fields.values(), task_id))
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def set_task_status(self, task_id: int, status: str) -> None:
        self.update_task(task_id, status=status)

    def move_task(self, task_id: int, status: str, position: int | None = None) -> None:
        if position is None:
            row = self.conn.execute(
                "SELECT COALESCE(MAX(position)+1, 0) AS p FROM tasks WHERE status=?",
                (status,),
            ).fetchone()
            position = row["p"]
        self.update_task(task_id, status=status, position=position)

    def swap_positions(self, task_id_a: int, task_id_b: int) -> None:
        a = self.get_task(task_id_a)
        b = self.get_task(task_id_b)
        self.conn.execute("UPDATE tasks SET position=? WHERE id=?", (b.position, a.id))
        self.conn.execute("UPDATE tasks SET position=? WHERE id=?", (a.position, b.id))
        self.conn.commit()

    def list_tasks_by_status(self) -> dict[str, list[Task]]:
        return {s: self.list_tasks(status=s) for s in ("todo", "doing", "done")}

    # ---------- sessions ----------
    def start_session(self, kind: str, planned_seconds: int, task_ids: list[int] | None = None) -> int:
        now = _now_iso()
        cur = self.conn.execute(
            "INSERT INTO sessions (kind, started_at, planned_seconds) VALUES (?, ?, ?)",
            (kind, now, planned_seconds),
        )
        sid = cur.lastrowid
        for tid in (task_ids or []):
            self.conn.execute(
                "INSERT INTO session_tasks (session_id, task_id) VALUES (?, ?)", (sid, tid)
            )
        self.conn.commit()
        return sid

    def extend_session_planned(self, session_id: int, extra_seconds: int) -> None:
        self.conn.execute(
            "UPDATE sessions SET planned_seconds = planned_seconds + ? WHERE id = ?",
            (extra_seconds, session_id),
        )
        self.conn.commit()

    def end_session(self, session_id: int, actual_seconds: int, completed: bool,
                    interruption_count: int = 0) -> None:
        self.conn.execute(
            "UPDATE sessions SET ended_at=?, actual_seconds=?, completed=?, interruption_count=?"
            " WHERE id=?",
            (_now_iso(), actual_seconds, int(completed), interruption_count, session_id),
        )
        self.conn.commit()

    def kv_set(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO config_kv(key, value) VALUES(?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def kv_get(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM config_kv WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def kv_delete(self, key: str) -> None:
        self.conn.execute("DELETE FROM config_kv WHERE key=?", (key,))
        self.conn.commit()

    def log_interruption(self, session_id: int, reason: str = "") -> None:
        self.conn.execute(
            "INSERT INTO interruptions (session_id, at, reason) VALUES (?, ?, ?)",
            (session_id, _now_iso(), reason),
        )
        self.conn.execute(
            "UPDATE sessions SET interruption_count = interruption_count + 1 WHERE id=?",
            (session_id,),
        )
        self.conn.commit()

    # ---------- stats ----------
    def stats_today(self) -> dict:
        today = date.today().isoformat()
        row = self.conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(actual_seconds), 0) AS secs"
            " FROM sessions WHERE kind='focus' AND completed=1 AND substr(started_at,1,10)=?",
            (today,),
        ).fetchone()
        return {"sessions": row["n"], "focus_seconds": row["secs"], "streak": self._streak()}

    def daily_focus_minutes(self, days: int = 7) -> list[tuple[str, int]]:
        """Return [(YYYY-MM-DD, minutes), ...] for the last `days` days, oldest first."""
        rows = self.conn.execute(
            "SELECT substr(started_at,1,10) AS d, SUM(actual_seconds) AS s FROM sessions"
            " WHERE kind='focus' AND completed=1 GROUP BY d"
        ).fetchall()
        by_day = {r["d"]: int((r["s"] or 0) // 60) for r in rows}
        out = []
        today = date.today()
        for i in range(days - 1, -1, -1):
            d = (today - timedelta(days=i)).isoformat()
            out.append((d, by_day.get(d, 0)))
        return out

    def top_tasks(self, limit: int = 5) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            "SELECT t.title AS title, SUM(s.actual_seconds) AS secs"
            " FROM sessions s JOIN session_tasks st ON st.session_id = s.id"
            " JOIN tasks t ON t.id = st.task_id"
            " WHERE s.kind='focus' AND s.completed=1"
            " GROUP BY t.id ORDER BY secs DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["title"], int((r["secs"] or 0) // 60)) for r in rows]

    def avg_interruptions_per_focus(self) -> float:
        row = self.conn.execute(
            "SELECT AVG(interruption_count) AS a FROM sessions"
            " WHERE kind='focus' AND completed=1"
        ).fetchone()
        return float(row["a"] or 0)

    def session_history(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT s.id, s.kind, s.started_at, s.ended_at, s.planned_seconds, s.actual_seconds,"
            " s.completed, s.interruption_count,"
            " (SELECT GROUP_CONCAT(t.title, ', ') FROM session_tasks st"
            "  JOIN tasks t ON t.id = st.task_id WHERE st.session_id = s.id) AS task_titles"
            " FROM sessions s ORDER BY s.started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _streak(self) -> int:
        # Consecutive days (counting back from today) with at least one completed focus session.
        rows = self.conn.execute(
            "SELECT DISTINCT substr(started_at,1,10) AS d FROM sessions"
            " WHERE kind='focus' AND completed=1 ORDER BY d DESC"
        ).fetchall()
        days = {r["d"] for r in rows}
        streak = 0
        cur = date.today()
        while cur.isoformat() in days:
            streak += 1
            cur = cur - timedelta(days=1)
        return streak


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        status=row["status"],
        tags=row["tags"] or "",
        estimated_pomodoros=row["estimated_pomodoros"] or 0,
        position=row["position"] or 0,
    )

"""SQLite persistence. XDG data dir, schema migrations via PRAGMA user_version."""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from pomodoro.core.models import Project, Sprint, Task

SCHEMA_VERSION = 8

# Sentinel: distinguishes "no project filter" from "Inbox only" (project_id IS NULL).
_NO = object()

# Mirrored from widgets/card.py so db doesn't import textual at module load.
_PROJECT_COLORS = ["cyan", "green", "yellow", "magenta", "blue", "red",
                   "bright_cyan", "bright_green", "bright_yellow", "bright_magenta"]


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
                  kind TEXT NOT NULL,
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
            self.conn.execute("PRAGMA user_version = 2")
            self.conn.commit()
            version = 2
        if version < 3:
            # Projects + tasks.project_id FK. Inbox = project_id IS NULL.
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                  id INTEGER PRIMARY KEY,
                  name TEXT NOT NULL UNIQUE,
                  color TEXT DEFAULT 'cyan',
                  archived INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL
                );
                ALTER TABLE tasks ADD COLUMN project_id INTEGER
                    REFERENCES projects(id) ON DELETE SET NULL;
                CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
                """
            )
            self.conn.execute("PRAGMA user_version = 3")
            self.conn.commit()
            version = 3
        if version < 4:
            # Notes on tasks (Phase K1 pre-wired so we don't need another migration later).
            self.conn.executescript(
                "ALTER TABLE tasks ADD COLUMN notes TEXT NOT NULL DEFAULT '';"
            )
            self.conn.execute("PRAGMA user_version = 4")
            self.conn.commit()
            version = 4
        if version < 5:
            # Recurring templates (Phase K2 placeholder — schema only).
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS recurring_templates (
                  id INTEGER PRIMARY KEY,
                  title TEXT NOT NULL,
                  tags TEXT DEFAULT '',
                  estimated_pomodoros INTEGER DEFAULT 0,
                  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                  recurrence TEXT NOT NULL,
                  next_run_at TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )
            self.conn.execute("PRAGMA user_version = 5")
            self.conn.commit()
            version = 5
        if version < 6:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sprints (
                  id INTEGER PRIMARY KEY,
                  project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                  name TEXT NOT NULL,
                  goal TEXT DEFAULT '',
                  start_date TEXT NOT NULL,
                  end_date TEXT NOT NULL,
                  pomodoro_target INTEGER DEFAULT 0,
                  status TEXT NOT NULL DEFAULT 'planned',
                  retrospective TEXT DEFAULT '',
                  created_at TEXT NOT NULL
                );
                ALTER TABLE tasks ADD COLUMN sprint_id INTEGER
                    REFERENCES sprints(id) ON DELETE SET NULL;
                CREATE INDEX IF NOT EXISTS idx_tasks_sprint ON tasks(sprint_id);
                """
            )
            self.conn.execute("PRAGMA user_version = 6")
            self.conn.commit()
            version = 6
        if version < 7:
            # session_tasks.task_id lacked ON DELETE CASCADE; with foreign_keys ON,
            # deleting a task that had sessions raised. Rebuild the table with cascade.
            self.conn.executescript(
                """
                CREATE TABLE session_tasks_new (
                  session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
                  task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
                  completed_during_session INTEGER DEFAULT 0,
                  PRIMARY KEY (session_id, task_id)
                );
                INSERT INTO session_tasks_new (session_id, task_id, completed_during_session)
                  SELECT session_id, task_id, completed_during_session FROM session_tasks;
                DROP TABLE session_tasks;
                ALTER TABLE session_tasks_new RENAME TO session_tasks;
                """
            )
            self.conn.execute("PRAGMA user_version = 7")
            self.conn.commit()
            version = 7
        if version < 8:
            # Older DBs created `sessions.kind` with a CHECK that predates the
            # 'long_pause' (lunch) kind, so lunch/long-pause inserts failed with an
            # IntegrityError. Rebuild the table without the stale constraint.
            # FKs are disabled around the rebuild so DROP TABLE sessions does not
            # cascade-delete session_tasks / interruptions (their rows are preserved
            # and re-point to the renamed table).
            self.conn.commit()
            self.conn.execute("PRAGMA foreign_keys = OFF")
            self.conn.executescript(
                """
                CREATE TABLE sessions_new (
                  id INTEGER PRIMARY KEY,
                  kind TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  ended_at TEXT,
                  planned_seconds INTEGER NOT NULL,
                  actual_seconds INTEGER NOT NULL DEFAULT 0,
                  completed INTEGER NOT NULL DEFAULT 0,
                  interruption_count INTEGER NOT NULL DEFAULT 0
                );
                INSERT INTO sessions_new
                  SELECT id, kind, started_at, ended_at, planned_seconds,
                         actual_seconds, completed, interruption_count FROM sessions;
                DROP TABLE sessions;
                ALTER TABLE sessions_new RENAME TO sessions;
                """
            )
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.conn.commit()
            self.conn.execute("PRAGMA foreign_keys = ON")

    # ---------- tasks ----------
    def add_task(self, title: str, tags: str = "", estimated_pomodoros: int = 0,
                 project_id: int | None = None, sprint_id: int | None = None) -> Task:
        now = _now_iso()
        cur = self.conn.execute(
            "INSERT INTO tasks (title, status, tags, estimated_pomodoros, position,"
            " project_id, sprint_id, created_at, updated_at)"
            " VALUES (?, 'todo', ?, ?,"
            " COALESCE((SELECT MAX(position)+1 FROM tasks WHERE status='todo'), 0),"
            " ?, ?, ?, ?)",
            (title, tags, estimated_pomodoros, project_id, sprint_id, now, now),
        )
        self.conn.commit()
        return self.get_task(cur.lastrowid)

    def get_task(self, task_id: int) -> Task:
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return _row_to_task(row)

    def list_tasks(self, status: str | None = None, tag: str | None = None,
                   sprint_id: int | None = None,
                   project_filter: object = _NO,
                   include_done: bool = False) -> list[Task]:
        """List tasks, optionally filtered.

        project_filter sentinel _NO: no project filter (default).
        project_filter=None: only Inbox (project_id IS NULL).
        project_filter=int: only that project.
        include_done=True: include done tasks even when status filter not set.
        """
        params: list = []
        where = []
        if status:
            where.append("status=?")
            params.append(status)
        elif not include_done:
            where.append("status != 'done'")
        else:
            where.append("1=1")
        if tag:
            tag_low = tag.lower().lstrip("#")
        if project_filter is not _NO:
            if project_filter is None:
                where.append("project_id IS NULL")
            else:
                where.append("project_id=?")
                params.append(project_filter)
        if sprint_id is not None:
            where.append("sprint_id=?")
            params.append(sprint_id)
        order = "ORDER BY position, id" if status else "ORDER BY status DESC, position, id"
        sql = f"SELECT * FROM tasks WHERE {' AND '.join(where)} {order}"
        rows = self.conn.execute(sql, params).fetchall()
        tasks = [_row_to_task(r) for r in rows]
        if tag:
            tasks = [t for t in tasks
                     if tag_low in {x.strip().lower() for x in (t.tags or "").split(",") if x.strip()}]
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

    def set_task_project(self, task_id: int, project_id: int | None) -> None:
        self.update_task(task_id, project_id=project_id)

    def set_task_sprint(self, task_id: int, sprint_id: int | None) -> None:
        self.update_task(task_id, sprint_id=sprint_id)

    def update_task_notes(self, task_id: int, notes: str) -> None:
        self.update_task(task_id, notes=notes)

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

    def list_tasks_by_status(self, project_filter: object = _NO) -> dict[str, list[Task]]:  # noqa: B008
        return {s: self.list_tasks(status=s, project_filter=project_filter)
                for s in ("todo", "doing", "done")}

    # ---------- projects ----------
    def add_project(self, name: str, color: str = "cyan") -> Project:
        now = _now_iso()
        cur = self.conn.execute(
            "INSERT INTO projects (name, color, created_at) VALUES (?, ?, ?)",
            (name, color, now),
        )
        self.conn.commit()
        return self.get_project(cur.lastrowid)

    def get_project(self, project_id: int) -> Project:
        row = self.conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return _row_to_project(row)

    def get_project_by_name(self, name: str) -> Project | None:
        row = self.conn.execute("SELECT * FROM projects WHERE name=?", (name,)).fetchone()
        return _row_to_project(row) if row else None

    def get_or_create_project(self, name: str, color: str | None = None) -> Project:
        existing = self.get_project_by_name(name)
        if existing:
            return existing
        from pomodoro.core.colors import stable_index
        c = color or _PROJECT_COLORS[stable_index(name, len(_PROJECT_COLORS))]
        return self.add_project(name, color=c)

    def list_projects(self, include_archived: bool = False) -> list[Project]:
        if include_archived:
            rows = self.conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM projects WHERE archived=0 ORDER BY name"
            ).fetchall()
        return [_row_to_project(r) for r in rows]

    def update_project(self, project_id: int, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE projects SET {cols} WHERE id=?",
                          (*fields.values(), project_id))
        self.conn.commit()

    def archive_project(self, project_id: int, archived: bool = True) -> None:
        self.update_project(project_id, archived=int(archived))

    def delete_project(self, project_id: int, move_tasks_to_inbox: bool = True) -> None:
        if move_tasks_to_inbox:
            self.conn.execute(
                "UPDATE tasks SET project_id=NULL WHERE project_id=?", (project_id,)
            )
        self.conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        self.conn.commit()

    def project_task_counts(self, project_id: int | None) -> dict[str, int]:
        if project_id is None:
            sql = ("SELECT status, COUNT(*) AS n FROM tasks "
                   "WHERE project_id IS NULL GROUP BY status")
            params: tuple = ()
        else:
            sql = ("SELECT status, COUNT(*) AS n FROM tasks "
                   "WHERE project_id=? GROUP BY status")
            params = (project_id,)
        rows = self.conn.execute(sql, params).fetchall()
        out = {"todo": 0, "doing": 0, "done": 0}
        for r in rows:
            out[r["status"]] = r["n"]
        return out

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

    def daily_focus_minutes(self, days: int = 7, project_id: int | None = None) -> list[tuple[str, int]]:
        """Return [(YYYY-MM-DD, minutes), ...] for the last `days` days, oldest first."""
        if project_id is None:
            rows = self.conn.execute(
                "SELECT substr(started_at,1,10) AS d, SUM(actual_seconds) AS s FROM sessions"
                " WHERE kind='focus' AND completed=1 GROUP BY d"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT substr(s.started_at,1,10) AS d, SUM(s.actual_seconds) AS s"
                " FROM sessions s JOIN session_tasks st ON st.session_id=s.id"
                " JOIN tasks t ON t.id=st.task_id"
                " WHERE s.kind='focus' AND s.completed=1 AND t.project_id=?"
                " GROUP BY d",
                (project_id,),
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

    def session_history(self, limit: int = 50, project_id: int | None = None) -> list[dict]:
        if project_id is None:
            rows = self.conn.execute(
                "SELECT s.id, s.kind, s.started_at, s.ended_at, s.planned_seconds, s.actual_seconds,"
                " s.completed, s.interruption_count,"
                " (SELECT GROUP_CONCAT(t.title, ', ') FROM session_tasks st"
                "  JOIN tasks t ON t.id = st.task_id WHERE st.session_id = s.id) AS task_titles,"
                " (SELECT GROUP_CONCAT(DISTINCT COALESCE(p.name, 'Inbox')) FROM session_tasks st"
                "  JOIN tasks t ON t.id = st.task_id"
                "  LEFT JOIN projects p ON p.id = t.project_id"
                "  WHERE st.session_id = s.id) AS projects"
                " FROM sessions s ORDER BY s.started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT DISTINCT s.id, s.kind, s.started_at, s.ended_at, s.planned_seconds,"
                " s.actual_seconds, s.completed, s.interruption_count,"
                " (SELECT GROUP_CONCAT(t2.title, ', ') FROM session_tasks st2"
                "  JOIN tasks t2 ON t2.id = st2.task_id WHERE st2.session_id = s.id) AS task_titles,"
                " (SELECT GROUP_CONCAT(DISTINCT COALESCE(p2.name, 'Inbox')) FROM session_tasks st2"
                "  JOIN tasks t2 ON t2.id = st2.task_id"
                "  LEFT JOIN projects p2 ON p2.id = t2.project_id"
                "  WHERE st2.session_id = s.id) AS projects"
                " FROM sessions s"
                " JOIN session_tasks st ON st.session_id = s.id"
                " JOIN tasks t ON t.id = st.task_id"
                " WHERE t.project_id=?"
                " ORDER BY s.started_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def sessions_per_project(self, since_days: int = 30) -> list[tuple[str, str, int, int]]:
        """Return [(project_name, color, session_count, total_seconds), ...]
        for completed focus sessions over the last N days, including Inbox as 'Inbox'.
        Sorted by total_seconds descending.
        """
        since = (date.today() - timedelta(days=since_days)).isoformat()
        rows = self.conn.execute(
            "SELECT COALESCE(p.name, 'Inbox') AS name,"
            " COALESCE(p.color, 'white') AS color,"
            " COUNT(DISTINCT s.id) AS n,"
            " SUM(s.actual_seconds) AS secs"
            " FROM sessions s"
            " JOIN session_tasks st ON st.session_id=s.id"
            " JOIN tasks t ON t.id=st.task_id"
            " LEFT JOIN projects p ON p.id=t.project_id"
            " WHERE s.kind='focus' AND s.completed=1 AND substr(s.started_at,1,10) >= ?"
            " GROUP BY COALESCE(p.id, -1)"
            " ORDER BY secs DESC",
            (since,),
        ).fetchall()
        return [(r["name"], r["color"], r["n"], int(r["secs"] or 0)) for r in rows]

    def task_actual_pomodoros(self, task_id: int) -> int:
        """Count completed focus sessions linked to this task."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM sessions s"
            " JOIN session_tasks st ON st.session_id=s.id"
            " WHERE st.task_id=? AND s.kind='focus' AND s.completed=1",
            (task_id,),
        ).fetchone()
        return int(row["n"] or 0)

    def sessions_by_bucket(self, granularity: str, n_buckets: int = 14,
                           project_id: int | None = None
                           ) -> list[tuple[str, int, float]]:
        """Aggregate completed focus sessions into time buckets.

        granularity: 'day' | 'week' | 'month'
        Returns [(bucket_label, focus_minutes, est_ratio_or_0), ...] oldest first.
        est_ratio is actual_pomodoros / sum(estimated_pomodoros) for tasks touched
        in that bucket; 0.0 if no estimates.
        """
        today = date.today()
        buckets: list[tuple[str, str, str]] = []  # (label, start_iso, end_iso inclusive)
        if granularity == "day":
            for i in range(n_buckets - 1, -1, -1):
                d = today - timedelta(days=i)
                buckets.append((d.isoformat()[5:], d.isoformat(), d.isoformat()))
        elif granularity == "week":
            # ISO weeks ending on Sunday for simplicity, oldest first.
            start_of_this_week = today - timedelta(days=today.weekday())
            for i in range(n_buckets - 1, -1, -1):
                ws = start_of_this_week - timedelta(weeks=i)
                we = ws + timedelta(days=6)
                buckets.append((ws.strftime("%m-%d"), ws.isoformat(), we.isoformat()))
        elif granularity == "month":
            y, m = today.year, today.month
            months: list[tuple[int, int]] = []
            for _ in range(n_buckets):
                months.append((y, m))
                m -= 1
                if m == 0:
                    m, y = 12, y - 1
            for y2, m2 in reversed(months):
                # First and last day of month
                first = date(y2, m2, 1)
                if m2 == 12:
                    next_first = date(y2 + 1, 1, 1)
                else:
                    next_first = date(y2, m2 + 1, 1)
                last = next_first - timedelta(days=1)
                buckets.append((first.strftime("%Y-%m"), first.isoformat(), last.isoformat()))
        else:
            return []
        out = []
        for label, start, end in buckets:
            if project_id is None:
                row = self.conn.execute(
                    "SELECT COALESCE(SUM(actual_seconds),0) AS s, COUNT(*) AS n"
                    " FROM sessions WHERE kind='focus' AND completed=1"
                    " AND substr(started_at,1,10) BETWEEN ? AND ?",
                    (start, end),
                ).fetchone()
            else:
                row = self.conn.execute(
                    "SELECT COALESCE(SUM(s.actual_seconds),0) AS s, COUNT(DISTINCT s.id) AS n"
                    " FROM sessions s JOIN session_tasks st ON st.session_id=s.id"
                    " JOIN tasks t ON t.id=st.task_id"
                    " WHERE s.kind='focus' AND s.completed=1 AND t.project_id=?"
                    " AND substr(s.started_at,1,10) BETWEEN ? AND ?",
                    (project_id, start, end),
                ).fetchone()
            mins = int((row["s"] or 0) // 60)
            # Estimate ratio: sum of actual_pomodoros / sum of estimates for tasks touched
            est_row = self.conn.execute(
                "SELECT COALESCE(SUM(t.estimated_pomodoros),0) AS est,"
                " COUNT(DISTINCT s.id) AS actual"
                " FROM sessions s JOIN session_tasks st ON st.session_id=s.id"
                " JOIN tasks t ON t.id=st.task_id"
                " WHERE s.kind='focus' AND s.completed=1"
                " AND substr(s.started_at,1,10) BETWEEN ? AND ?"
                + (" AND t.project_id=?" if project_id is not None else ""),
                (start, end, project_id) if project_id is not None else (start, end),
            ).fetchone()
            est = int(est_row["est"] or 0)
            actual = int(est_row["actual"] or 0)
            ratio = (actual / est) if est > 0 else 0.0
            out.append((label, mins, ratio))
        return out

    def project_analytics(self, project_id: int) -> dict:
        """Per-project drill-down stats."""
        today = date.today()
        week_ago = (today - timedelta(days=7)).isoformat()
        month_ago = (today - timedelta(days=30)).isoformat()
        rows = self.conn.execute(
            "SELECT s.actual_seconds AS sec, substr(s.started_at,1,10) AS d"
            " FROM sessions s JOIN session_tasks st ON st.session_id=s.id"
            " JOIN tasks t ON t.id=st.task_id"
            " WHERE s.kind='focus' AND s.completed=1 AND t.project_id=?",
            (project_id,),
        ).fetchall()
        all_secs = sum(int(r["sec"] or 0) for r in rows)
        week_secs = sum(int(r["sec"] or 0) for r in rows if r["d"] >= week_ago)
        month_secs = sum(int(r["sec"] or 0) for r in rows if r["d"] >= month_ago)
        days = sorted({r["d"] for r in rows})
        last_session = days[-1] if days else None
        avg_per_active_day = (all_secs // 60 // len(days)) if days else 0
        # Day-of-week distribution (0=Mon..6=Sun)
        dow = [0] * 7
        for r in rows:
            try:
                d = date.fromisoformat(r["d"])
                dow[d.weekday()] += int(r["sec"] or 0) // 60
            except Exception:
                pass
        # Estimate accuracy for tasks in this project (actual pomos / estimated)
        est_row = self.conn.execute(
            "SELECT COALESCE(SUM(estimated_pomodoros),0) AS est FROM tasks WHERE project_id=?",
            (project_id,),
        ).fetchone()
        actual_pomos_row = self.conn.execute(
            "SELECT COUNT(DISTINCT s.id) AS n FROM sessions s"
            " JOIN session_tasks st ON st.session_id=s.id"
            " JOIN tasks t ON t.id=st.task_id"
            " WHERE s.kind='focus' AND s.completed=1 AND t.project_id=?",
            (project_id,),
        ).fetchone()
        est = int(est_row["est"] or 0)
        actual = int(actual_pomos_row["n"] or 0)
        return {
            "total_minutes": all_secs // 60,
            "week_minutes": week_secs // 60,
            "month_minutes": month_secs // 60,
            "active_days": len(days),
            "avg_per_active_day_minutes": avg_per_active_day,
            "last_session": last_session,
            "dow_minutes": dow,
            "estimated_pomodoros": est,
            "actual_pomodoros": actual,
            "estimate_ratio": (actual / est) if est > 0 else 0.0,
        }

    # ---------- sprints ----------
    def add_sprint(self, project_id: int | None, name: str, start_date: str,
                   end_date: str, goal: str = "", pomodoro_target: int = 0,
                   status: str = "planned") -> Sprint:
        now = _now_iso()
        cur = self.conn.execute(
            "INSERT INTO sprints (project_id, name, goal, start_date, end_date,"
            " pomodoro_target, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, name, goal, start_date, end_date, pomodoro_target, status, now),
        )
        self.conn.commit()
        return self.get_sprint(cur.lastrowid)

    def get_sprint(self, sprint_id: int) -> Sprint:
        row = self.conn.execute("SELECT * FROM sprints WHERE id=?", (sprint_id,)).fetchone()
        return _row_to_sprint(row)

    def get_sprint_by_name(self, project_id: int | None, name: str) -> Sprint | None:
        if project_id is None:
            row = self.conn.execute(
                "SELECT * FROM sprints WHERE name=? AND project_id IS NULL", (name,)
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM sprints WHERE name=? AND project_id=?", (name, project_id)
            ).fetchone()
        return _row_to_sprint(row) if row else None

    def get_or_create_sprint(self, project_id: int | None, name: str) -> Sprint:
        existing = self.get_sprint_by_name(project_id, name)
        if existing:
            return existing
        today = date.today().isoformat()
        end = (date.today() + timedelta(days=14)).isoformat()
        return self.add_sprint(project_id, name, today, end, goal="", status="planned")

    def list_sprints(self, project_id: int | None = None,
                     include_completed: bool = True) -> list[Sprint]:
        clauses: list[str] = []
        params: list = []
        if project_id is not None:
            clauses.append("project_id=?")
            params.append(project_id)
        if not include_completed:
            clauses.append("status NOT IN ('completed', 'cancelled')")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM sprints {where} ORDER BY start_date DESC, id DESC", params
        ).fetchall()
        return [_row_to_sprint(r) for r in rows]

    def update_sprint(self, sprint_id: int, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE sprints SET {cols} WHERE id=?",
                          (*fields.values(), sprint_id))
        self.conn.commit()

    def activate_sprint(self, sprint_id: int) -> None:
        sp = self.get_sprint(sprint_id)
        # Deactivate any other active sprint on the same project.
        if sp.project_id is not None:
            self.conn.execute(
                "UPDATE sprints SET status='planned' WHERE project_id=? AND status='active' AND id != ?",
                (sp.project_id, sprint_id),
            )
        else:
            self.conn.execute(
                "UPDATE sprints SET status='planned' WHERE project_id IS NULL AND status='active' AND id != ?",
                (sprint_id,),
            )
        self.conn.execute("UPDATE sprints SET status='active' WHERE id=?", (sprint_id,))
        self.conn.commit()

    def active_sprint(self, project_id: int | None) -> Sprint | None:
        if project_id is None:
            row = self.conn.execute(
                "SELECT * FROM sprints WHERE project_id IS NULL AND status='active'"
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM sprints WHERE project_id=? AND status='active'", (project_id,)
            ).fetchone()
        return _row_to_sprint(row) if row else None

    def delete_sprint(self, sprint_id: int) -> None:
        self.conn.execute("UPDATE tasks SET sprint_id=NULL WHERE sprint_id=?", (sprint_id,))
        self.conn.execute("DELETE FROM sprints WHERE id=?", (sprint_id,))
        self.conn.commit()

    def sprint_burndown(self, sprint_id: int) -> dict:
        """Compute burndown stats for a sprint."""
        sp = self.get_sprint(sprint_id)
        target = sp.pomodoro_target or 0
        # Count completed focus sessions on tasks in this sprint, grouped by date
        rows = self.conn.execute(
            "SELECT substr(s.started_at,1,10) AS d, COUNT(DISTINCT s.id) AS n"
            " FROM sessions s JOIN session_tasks st ON st.session_id=s.id"
            " JOIN tasks t ON t.id=st.task_id"
            " WHERE s.kind='focus' AND s.completed=1 AND t.sprint_id=?"
            " GROUP BY d ORDER BY d",
            (sprint_id,),
        ).fetchall()
        per_day = {r["d"]: int(r["n"]) for r in rows}
        try:
            start = date.fromisoformat(sp.start_date)
            end = date.fromisoformat(sp.end_date)
        except Exception:
            return {"target": target, "completed": sum(per_day.values()),
                    "days": [], "remaining_series": [], "ideal_series": []}
        days = []
        d = start
        while d <= end:
            days.append(d.isoformat())
            d = d + timedelta(days=1)
        cumulative = 0
        remaining = []
        for d_iso in days:
            cumulative += per_day.get(d_iso, 0)
            remaining.append(max(0, target - cumulative))
        total_days = max(1, len(days) - 1)
        ideal = [target - (i * target / total_days) for i in range(len(days))]
        completed = sum(per_day.values())
        today_iso = date.today().isoformat()
        # Days remaining (inclusive)
        try:
            today_d = date.today()
            days_left = max(0, (end - today_d).days)
        except Exception:
            days_left = 0
        # Pace vs ideal: positive = ahead, negative = behind
        if today_iso in days:
            idx = days.index(today_iso)
            pace = int((target - ideal[idx]) - completed) if target else 0
        else:
            pace = 0
        return {
            "target": target,
            "completed": completed,
            "days": days,
            "per_day": per_day,
            "remaining_series": remaining,
            "ideal_series": ideal,
            "days_left": days_left,
            "pace": -pace,  # negative pace = behind ideal
        }

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
    keys = row.keys() if hasattr(row, "keys") else []
    return Task(
        id=row["id"],
        title=row["title"],
        status=row["status"],
        tags=row["tags"] or "",
        estimated_pomodoros=row["estimated_pomodoros"] or 0,
        position=row["position"] or 0,
        project_id=row["project_id"] if "project_id" in keys else None,
        sprint_id=row["sprint_id"] if "sprint_id" in keys else None,
        notes=(row["notes"] if "notes" in keys else "") or "",
    )


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        color=row["color"] or "cyan",
        archived=bool(row["archived"]),
    )


def _row_to_sprint(row: sqlite3.Row) -> Sprint:
    return Sprint(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        goal=row["goal"] or "",
        start_date=row["start_date"],
        end_date=row["end_date"],
        pomodoro_target=row["pomodoro_target"] or 0,
        status=row["status"],
        retrospective=row["retrospective"] or "",
    )

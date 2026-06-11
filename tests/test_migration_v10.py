"""Migration v10: sessions.notes added, existing rows backfill ''."""

from __future__ import annotations

import sqlite3

from pomban.core.db import DB, SCHEMA_VERSION


def _column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def test_fresh_db_stamps_v10_with_notes(tmp_path):
    db = DB(path=tmp_path / "fresh.db")
    assert SCHEMA_VERSION == 10
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == 10
    assert "notes" in _column_names(db.conn, "sessions")
    db.close()


def test_migrate_v9_to_v10_backfills_empty_notes(tmp_path):
    path = tmp_path / "v9.db"
    # Build a v9 schema by opening the DB once, then forcing user_version back
    # to 9 and dropping the v10 column so the migration has work to do.
    db = DB(path=path)
    sid = db.start_session("focus", planned_seconds=1500)
    db.end_session(sid, actual_seconds=1500, completed=True)
    db.conn.execute("PRAGMA user_version = 9")
    # SQLite doesn't support DROP COLUMN before 3.35; do the table rebuild.
    db.conn.executescript(
        """
        CREATE TABLE sessions_pre10 AS
          SELECT id, kind, started_at, ended_at, planned_seconds, actual_seconds,
                 completed, interruption_count
          FROM sessions;
        DROP TABLE sessions;
        ALTER TABLE sessions_pre10 RENAME TO sessions;
        """
    )
    db.conn.commit()
    db.close()

    db2 = DB(path=path)
    assert db2.conn.execute("PRAGMA user_version").fetchone()[0] == 10
    cols = _column_names(db2.conn, "sessions")
    assert "notes" in cols
    rows = db2.conn.execute("SELECT notes FROM sessions").fetchall()
    assert [r["notes"] for r in rows] == [""]
    db2.close()

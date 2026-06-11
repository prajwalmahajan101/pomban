# ADR 0002 — Single SQLite connection, no writer thread

Status: Accepted (2026-06-11)

## Context

pomban's 0.25 s tick path calls into `core/timer_engine.tick()`
and, when a phase ends, into `_on_phase_completed()` which writes to
the SQLite library:

- `coord.end(...)` — `UPDATE sessions` row.
- `_log_new_session()` — `INSERT INTO sessions` row + zero or more
  `INSERT INTO session_tasks` rows.
- The session-end modal callback (`_on_session_end_result`) — one or
  more `UPDATE tasks` and `UPDATE sessions` writes.

The total per phase transition is small: 2–4 statements with 2
commits in the common case, up to N+2 commits when finalising a
multi-task session.

A historical code-review entry (ISSUE-001) asked whether these writes
should be offloaded to a dedicated writer thread to keep the 0.25 s
tick path clean.

`sqlite3` connections are **not safe to share across threads**
without serialisation. A writer thread would require either:

1. A second connection owned by the writer thread (with all the
   coordination cost of two opens against the same DB).
2. A queue + serialisation around the single connection, plus
   re-attribution of failures back to the originating task.

We already mitigated the hot path two ways:

- `SessionService._lunch_cache` caches the lunch-window SELECT
  for the current day so `_should_suggest_lunch()` is O(1).
- The session-end modal push is deferred via
  `App.call_after_refresh(...)` so the tick callback returns
  immediately instead of mounting a screen synchronously.

No real-world jank has been observed.

## Decision

**Stay with a single SQLite connection. Do not introduce a writer
thread.** Close ISSUE-001 as won't-fix.

The single-connection invariant becomes a load-bearing project
convention: any future work that wants to do "background" DB work
either does it synchronously in the foreground (small + fast) or
defers it via `call_after_refresh` / `set_interval` (UI-thread, no
sharing).

## Consequences

**Positive**

- Zero coordination cost. One opener, one closer, one writer.
- No risk of split-brain on shutdown (which connection wrote the
  pending session?).
- The migration runner stays simple: it owns the connection
  exclusively at startup.
- Failures retain their natural call stack — no thread-boundary
  marshalling.

**Negative / risks**

- The tick path is hot. If a future feature adds a chunky write
  there (e.g. analytics rollups), we may revisit.
- We accept that "the user's terminal froze for 50ms once" is a
  bug we can investigate, not a category of bug we structurally
  prevent.
- A second tool that opens the DB while pomban is running will
  see locks (documented in
  [troubleshooting](../site/troubleshooting.md#sqlite-says-database-is-locked)).

## Usage

- New writes from the tick path: profile first; if visible, defer
  with `call_after_refresh` rather than reach for threads.
- New batch operations (e.g. an export): run them when the engine
  is `IDLE`, not during a session.
- Long-running reads (e.g. a stats query that could touch tens of
  thousands of rows): the right answer is a pre-aggregated table,
  not a worker. Add a migration and write a small aggregator.
- The migration runner remains a single sync block in
  `core/db.DB.__init__`. Don't make it async.

## Reference

- `.code_review/code_review_issues.md` — Resolved entry for
  ISSUE-001 with the won't-fix rationale.
- `core/session_service.py:_lunch_cache` — the lunch SELECT cache.
- `app.py:_on_phase_completed` — the `call_after_refresh` deferral.

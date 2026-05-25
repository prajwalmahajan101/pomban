# Code Review — Active Issues

Stack: tui
_Last updated: 2026-05-25_

Issue IDs are sequential and stable. Resolved issues are removed; carried-over issues keep their ID.

| ID | Severity | Priority | Effort | Category | Location | Summary |
|---|---|---|---|---|---|---|
| ISSUE-001 | High | P1 | M | Event Loop & Input Handling | src/pomodoro/app.py:157-218, 104-110 | Phase-completion handler runs synchronous DB writes and a `_should_suggest_lunch` SELECT inside the 0.25s `set_interval` tick loop; no offloading to a worker. |
| ISSUE-002 | High | P1 | S | Keyboard Navigation & Shortcut Discoverability | src/pomodoro/screens/help.py:7-22 | `?` help overlay is stale: lists ~9 keys but omits P/F/L/m/M/e/t and screen switches 3–6 that are live in BINDINGS. Primary discoverability surface lies to the user. |
| ISSUE-003 | High | P2 | M | Screen State & View Composition | src/pomodoro/app.py:123-137, 425-438 | `_refresh_all` / `action_switch` blind-`getattr` a hardcoded list of ~9 refresh method names across all screens, each wrapped in silent `try/except`. Duck-typed cross-layer refresh hides real failures. |
| ISSUE-004 | Medium | P2 | M | Configuration & Environment Management | src/pomodoro/app.py:700-771, 720-744 | Inbox encoded as magic `-2` and "All" as `None` for `active_project_id`, decoded in 5 separate methods. In-code comment admits the sentinel design is unresolved. |
| ISSUE-005 | Medium | P2 | L | Screen State & View Composition | src/pomodoro/app.py:1-873 | `PomodoroApp` is an 873-line god object: orchestration, persistence, filter state, lunch logic, music, inline task-parsing all in one class. |
| ISSUE-006 | Medium | P2 | S | Theming & Color Architecture | src/pomodoro/widgets/card.py:12-13; src/pomodoro/core/db.py:302 | Project/tag colors derived from builtin `hash()`; with default PYTHONHASHSEED randomization, colors change every launch. Non-deterministic theming. |
| ISSUE-007 | Medium | P2 | S | Error Handling & Crash Recovery | src/pomodoro/app.py:582-588, 816-821 | Resume and lunch paths mutate the otherwise-pure `TimerEngine` private state directly (`engine._last_tick`, `.phase`, `.remaining`, `.running`), bypassing the state machine API and its invariants. |
| ISSUE-008 | Medium | P3 | S | External Process / I/O Boundaries | src/pomodoro/plugins.py:82-86 | `git_sync` interpolates `repo_dir` into an unquoted `sh -c "cd {repo} && ..."` string. Path with spaces/shell metachars breaks or injects. |
| ISSUE-009 | Low | P3 | S | Accessibility | src/pomodoro/widgets/timer_display.py:16-21; repo-wide | No `NO_COLOR` support; state conveyed by color (phase color, ahead/behind) with 256-color names and no 16-color fallback. |
| ISSUE-010 | Low | P3 | S | Data Integrity | src/pomodoro/core/db.py:72-77, 244-246 | `session_tasks.task_id` has no `ON DELETE CASCADE`; `delete_task` leaves orphan `session_tasks` rows pointing at a deleted task. |
| ISSUE-011 | Low | P3 | S | Configuration & Environment Management | .gitignore; .test_db.sqlite3 | Test runs drop `.test_db.sqlite3` into the working tree; not gitignored. |
| ISSUE-012 | Low | P3 | S | Logging Without Corrupting the UI | src/pomodoro/app.py:139-829 (broad `except Exception: pass`) | Pervasive bare `except Exception: pass` around `notify`/refresh/engine calls swallows all diagnostics; no log sink while the alt-screen is active. |
</content>
</invoke>

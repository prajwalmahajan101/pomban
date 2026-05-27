# Architectural Learnings — Current State

Stack: tui
_Last updated: 2026-05-25_

## Active Patterns

- **Pure, I/O-free timer state machine** — `src/pomodoro/core/timer_engine.py`. `TimerEngine` takes an injected `now: float`, returns `list[Event]`, never touches UI or DB. Fully unit-testable with a fake clock. This is the strongest design decision in the repo and should be protected (see anti-pattern about private-state mutation).
- **Side-effect isolation via fire-and-forget helpers** — `notifications.py`, `music.py`, `plugins.py`. Each spawns subprocesses with `Popen(..., DEVNULL)`, never raises, logs to `$XDG_STATE_HOME/pomodoro/*.log`. Keeps the alt-screen render uncorrupted by stray stdout. Good TUI hygiene.
- **Explicit SQLite migrations via `PRAGMA user_version`** — `src/pomodoro/core/db.py:46-165`. Versioned, idempotent, forward-only migrations (v1→v6). DB layer returns dataclasses, never `sqlite3.Row`, keeping persistence details out of screens.
- **Config forward-compat filtering** — `core/config.py:98-101` `_filter_kwargs` drops unknown TOML keys so renamed/removed config keys never crash the loader. Theme validated against an allow-list.
- **Sentinel object for tri-state filter** — `db._NO` (`db.py:14`) cleanly distinguishes "no project filter" from "Inbox = project_id IS NULL" at the DB boundary. (Note: the *app-layer* encoding of this same tri-state with `-2`/`None` is an anti-pattern — see below.)

## Active Anti-Patterns

- **App-layer god object** — `app.py` (873 lines) owns orchestration, persistence, UI filter state, lunch scheduling, music control, and inline task-metadata parsing. Should be decomposed (a `FilterState`, a `SessionCoordinator`, a parser module). [ISSUE-005]
- **Synchronous DB work inside the tick loop** — `_on_phase_completed` (app.py:157) runs `db.end_session`, `_log_new_session`, and a `_should_suggest_lunch` SELECT while invoked from a 0.25s `set_interval`. No worker/thread offload; fine today on local SQLite, a latent stall as queries grow. [ISSUE-001]
- **Duck-typed cross-screen refresh** — `_refresh_all`/`action_switch` (app.py:123, 425) call a hardcoded list of ~9 method names via `getattr` on whatever screen is active, each in a silent `try/except`. No interface/protocol; adding a screen method requires editing the string list. [ISSUE-003]
- **Magic sentinel sprawl in app layer** — Inbox = `-2`, All = `None` for `active_project_id`, decoded independently in `project_filter_for_db`, `action_cycle_project`, `active_project_label`, `active_project_color`. Comment at app.py:700-710 admits the design is unsettled. [ISSUE-004]
- **Pure engine mutated through the back door** — resume (app.py:582) and lunch (app.py:816) set `engine.phase/.remaining/.running/._last_tick` directly, bypassing the state-machine API and its `_warning_fired`/`_carry` invariants. Erodes the engine's testability guarantee. [ISSUE-007]
- **Non-deterministic color from builtin `hash()`** — `card.tag_color` and `db.get_or_create_project` color assignment use `hash(name)`; with PYTHONHASHSEED randomized per process, colors change every launch. Use a stable hash (e.g. hashlib). [ISSUE-006]
- **Stale help overlay** — `help.py` HELP_TEXT diverged from actual `BINDINGS`. The discoverability surface must be generated from or tested against the live keymap. [ISSUE-002]
- **Catch-all exception suppression** — many `try/except Exception: pass` blocks around `notify`, refresh, and engine calls. Hides real bugs and offers no log sink during alt-screen mode. [ISSUE-012]

## Repeated Mistakes

- **Trusting `except Exception: pass` as control flow** — observed across `app.py`, `dashboard.py`, `kanban.py`, `stats.py`. Recommended direction: narrow the caught type, or route to the existing `$XDG_STATE_HOME/pomodoro/*.log` sink used by `notifications`/`music`/`plugins`.
- **Keymap defined in multiple places without a single source of truth** — per-screen `BINDINGS` plus a hand-written help string plus docs. Recommended direction: a central keymap that screens and the help overlay both consume; assert parity in a test.
- **Cross-screen coupling by string-named methods** — duck-typed refresh hooks. Recommended direction: define a `Refreshable` protocol (or Textual messages) so the contract is explicit and type-checked. (Largely addressed: `AppScreen` now defines typed `refresh_view`/`refresh_timer`.)
- **Storing a model on a `Screen` as `self.task` / `self._task`** — both collide with Textual internals (`Screen.task` is a read-only property; `MessagePump._task` is the message-pump asyncio task, which clobbers your value once the screen runs). Symptom: `AttributeError: property 'task' … has no setter`, or a stray `_asyncio.Task` where your model should be. Use a non-reserved name like `task_data` (the convention `TaskCard` already uses). This had silently broken `EditTaskModal` (only caught because no test opened it via the app).

## New module structure (this branch)

- **Pure helpers split out of the app god-object** — `core/task_input.py` (`parse_task_input`), `music_view.py` (player-status extraction + now-playing/progress rendering, shared by the dashboard panel and the full screen), `widgets/panel.py` (`panel_title` btop-style hotkey-letter titles). Each is import-light and unit-testable without Textual.
- **External-player control stays fire-and-forget** — `MusicController` gained `seek/stop/shuffle/repeat/speed` (fire-and-forget) and `history/playlists` (read, off-thread, `None` on any failure), all preserving the "never raise, log one line" contract. The full `MusicScreen` polls via `asyncio.to_thread` and escapes every player string.
</content>

# ADR 0003 — Layered screen architecture and the `AppScreen` contract

Status: Accepted (2026-06-11)

## Context

pomban has eight or nine top-level screens (Dashboard, Kanban,
Stats, History, Projects, Sprints) plus modals (Resume, PresetPicker,
SessionEndScreen, CardDetailScreen, EditTaskModal). Each is reached
via a `1`–`6` jump key. The 0.25 s tick callback in `app.py` needs to
refresh the **active** screen's timer; the global "refresh
everything" path needs to refresh whichever screen is currently
mounted.

An earlier version of the app had a hard-coded string list of valid
screens and a `match` on the active screen name to decide which
`refresh_timer()` / `refresh_view()` method to call. Adding a new
screen meant editing every list — the Kanban screen, the Sprints
screen, and the Card-detail screen each broke this convention until
they were retrofitted.

We also kept finding inline state on the `PomodoroApp` itself that
belonged on a smaller object: filter state (project + sprint),
session lifecycle, inline task-input parsing.

## Decision

**Every top-level screen subclasses `screens.base.AppScreen`** and
implements two methods:

- `refresh_view()` — re-render the whole screen against current
  state.
- `refresh_timer()` — re-render only the timer (the cheap path).

The tick / `_refresh_all` / `action_switch` paths use
`isinstance(scr, AppScreen)` to dispatch. New screens slot in with
zero edits to `app.py`.

`AppScreen` provides a default no-op `refresh_timer()` so screens
without a timer (Projects, Sprints) need not implement it.

**State that doesn't belong on `PomodoroApp` is extracted**:

- `core/task_input.py` — the inline `#tag @project !sprint ~N`
  parser.
- `core/filter_state.py` — current project filter + active sprint
  id, persisted via `db.kv_*`.
- `core/session_coordinator.py` — engine ⇄ DB ⇄ SessionService
  wiring; tracks the current session id and wall-clock start.
- `core/log.py` — file-only structured logger.

`PomodoroApp` keeps the things only it can do: own the `engine`, the
`db`, screen install/push, key bindings, action methods, modal
callbacks.

## Consequences

**Positive**

- New screens land with a constructor and a `compose`; the tick
  loop picks them up automatically.
- The "what's the active screen?" question is answered by
  `self.screen` and a type check, not a string compare.
- `PomodoroApp` shrank from a single-file kitchen sink to a
  shell that wires the engine, the DB, and the screen registry.
- Test surface is smaller: `core/task_input.py` is purely functional
  and trivially unit-tested; `core/session_coordinator.py` has no
  Textual import and tests against a real DB fixture.

**Negative / risks**

- Adding a thin "delegating shim" property on `PomodoroApp` (e.g.
  `current_session_id` proxying to `coord.current_session_id`) is
  necessary because the existing test suite pinned the public
  attribute names. We accept this and document it.
- An `AppScreen` subclass that raises in `refresh_view` could spam
  the log on every tick. We mitigate by catching at the dispatch
  site and logging once with the screen type name.
- The `AppScreen` base class is a tiny contract — easy to forget to
  implement `refresh_view()` on a new screen. Mypy will catch this
  once strict typing lands.

## Usage

- **Adding a new screen.** Subclass `screens.base.AppScreen`,
  implement `compose` + `refresh_view` (+ `refresh_timer` if the
  screen shows the timer), register it in `PomodoroApp.on_mount`
  with a name, and add a `1`–`6` binding. Don't touch the tick
  callback.
- **Modal screens.** Modals push via `App.push_screen(modal,
  callback)` and don't extend `AppScreen` — they're transient and
  the tick loop ignores them.
- **State that's not a screen concern.** New global state (e.g. a
  notification queue) goes into a new `core/` module, not onto
  `PomodoroApp` directly.
- **Boundary failures.** Catch at the boundary, call
  `log.exception("<context>")`, fall back to a safe default.
  Don't propagate exceptions into the tick path.

## Reference

- `screens/base.py:AppScreen` — the contract.
- `app.py:_refresh_active_screen_timer` /
  `app.py:_refresh_all` / `app.py:action_switch` — the dispatch
  sites.
- `.code_review/code_review_issues.md` Resolved entries for
  ISSUE-003 (duck-typed refresh) and ISSUE-005 (slim
  `PomodoroApp`).

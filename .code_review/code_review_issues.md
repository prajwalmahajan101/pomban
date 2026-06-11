# Code Review — Active Issues

Stack: tui
_Last updated: 2026-06-11_

Issue IDs are sequential and stable. Resolved issues are moved to the "Resolved" section.

_No active issues._

## Resolved (verified against HEAD)

- **ISSUE-001 phase-completion DB writes on the tick path** — Mitigations stand (cached lunch SELECT in `SessionService`, modal push deferred via `call_after_refresh`). A dedicated writer would require a second SQLite connection, which conflicts with the project's single-connection design. Closed as **won't-fix** absent observed jank.
- **ISSUE-005 slim `PomodoroApp`** — Filter state (`core/filter_state.py`), session coordinator (`core/session_coordinator.py`), and task input parsing (`core/task_input.py`) are all extracted. The music-feature removal trimmed two more UI actions and the dashboard music panel. Remaining inline clusters (`_on_session_end_result`, `_finalize_multi_complete`, `_maybe_prompt_resume`) are tightly coupled to Textual UI primitives + engine state; extracting them creates more indirection than clarity.
- **ISSUE-012 swallowed excepts in `app.py`** — Six meaningful sites (four DB reads + two `save_config` calls) now route to `log.exception`. Remaining `except Exception: pass` blocks are all cosmetic UI side effects (`notify`/`bell`/`animate`) where silent failure is the correct behavior.

- **ISSUE-002 stale help** — the `?` overlay is generated from the active screen's live `active_bindings`, so it can't drift from the real keymap.
- **ISSUE-003 duck-typed refresh** — `AppScreen.refresh_view()` plus a typed `refresh_timer()` no-op; the tick / `_refresh_all` / `action_switch` use `isinstance(scr, AppScreen)` and log failures, no string lists.
- **ISSUE-004 magic sentinel** — `core/filters.ProjectFilter` is used app-wide; the `-2`/`None` project encoding is gone.
- **ISSUE-006 non-deterministic color** — `core/colors.stable_index` (crc32) drives tag/project colors; stable across launches.
- **ISSUE-007 engine back-door** — resume and lunch go through `TimerEngine.restore()` / `enter_long_pause()`; no private-state pokes remain.
- **ISSUE-008 shell injection** — `git_sync` passes repo/message as `sh -c` positional `$1`/`$2`, not interpolated.
- **ISSUE-010 orphan session_tasks** — migration v7 rebuilt `session_tasks` with `task_id … ON DELETE CASCADE`.
- **Textual `Screen.task` pitfall (fixed)** — a `Screen` subclass must not store its model as `self.task` or `self._task`: both collide with Textual internals (`Screen.task` is a read-only property; `MessagePump._task` is the message-pump task). `EditTaskModal` had this latent bug (it would crash on open under current Textual); both it and the new `CardDetailScreen` now use `self.task_data`.

## Feature work landed (recent)

btop-style panel hotkeys (`widgets/panel.py` + `AppScreen.action_focus_pane`); kanban due-dates + priority (DB migration **v9**), card detail view (`screens/card_detail.py`), board search (`/`), per-column WIP limits (`[kanban]`), and bulk visual-mode actions. Schema is at v9; the v8 migration's version stamp was made a literal (atomicity fix). The music/cliamp subsystem was removed (no DB impact — state was read live from the external player).

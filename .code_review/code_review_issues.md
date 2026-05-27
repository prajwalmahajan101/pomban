# Code Review — Active Issues

Stack: tui
_Last updated: 2026-05-25_

Issue IDs are sequential and stable. Resolved issues are moved to the "Resolved" section.

| ID | Severity | Priority | Effort | Category | Location | Summary |
|---|---|---|---|---|---|---|
| ISSUE-001 | High | P2 | M | Event Loop & Input Handling | src/pomodoro/app.py `_on_phase_completed` | Phase-completion DB writes still run on the 0.25s tick path. Mitigated (lunch SELECT cached in SessionService, modal push deferred). Offloading the remaining inline `end`/`log_new_session` needs a dedicated writer (the single SQLite connection isn't thread-safe) — only worth it if the tick visibly janks. |
| ISSUE-005 | Medium | P2 | L | Screen State & View Composition | src/pomodoro/app.py | `PomodoroApp` is still large. Partially reduced: inline task parsing extracted to `core/task_input.py`. Remaining: a `FilterState` (project+sprint filter) and a `SessionCoordinator` (engine⇄DB⇄SessionService) extraction — behavior-preserving, keeping identically-named delegating shims because the test suite pins internal names. |
| ISSUE-012 | Low | P3 | S | Logging Without Corrupting the UI | src/pomodoro/app.py | Many `except Exception: pass` around `notify`/refresh remain (mostly cosmetic, terminal-safe). One meaningful site (lunch `log_interruption`) now routes to `core/log.py`; route the rest opportunistically. |

## Resolved (verified against HEAD)

- **ISSUE-002 stale help** — the `?` overlay is generated from the active screen's live `active_bindings`, so it can't drift from the real keymap.
- **ISSUE-003 duck-typed refresh** — `AppScreen.refresh_view()` plus a typed `refresh_timer()` no-op; the tick / `_refresh_all` / `action_switch` use `isinstance(scr, AppScreen)` and log failures, no string lists. A new screen (`MusicScreen`) slots into the tick/refresh with zero list edits.
- **ISSUE-004 magic sentinel** — `core/filters.ProjectFilter` is used app-wide; the `-2`/`None` project encoding is gone.
- **ISSUE-006 non-deterministic color** — `core/colors.stable_index` (crc32) drives tag/project colors; stable across launches.
- **ISSUE-007 engine back-door** — resume and lunch go through `TimerEngine.restore()` / `enter_long_pause()`; no private-state pokes remain.
- **ISSUE-008 shell injection** — `git_sync` passes repo/message as `sh -c` positional `$1`/`$2`, not interpolated.
- **ISSUE-010 orphan session_tasks** — migration v7 rebuilt `session_tasks` with `task_id … ON DELETE CASCADE`.
- **Textual `Screen.task` pitfall (fixed)** — a `Screen` subclass must not store its model as `self.task` or `self._task`: both collide with Textual internals (`Screen.task` is a read-only property; `MessagePump._task` is the message-pump task). `EditTaskModal` had this latent bug (it would crash on open under current Textual); both it and the new `CardDetailScreen` now use `self.task_data`.

## Feature work landed (this branch)

btop-style panel hotkeys (`widgets/panel.py` + `AppScreen.action_focus_pane`); full Music section (`screens/music.py`, shared `music_view.py`, extended `MusicController` with seek/shuffle/repeat/speed/history/playlists); kanban due-dates + priority (DB migration **v9**), card detail view (`screens/card_detail.py`), board search (`/`), per-column WIP limits (`[kanban]`), and bulk visual-mode actions. Schema is at v9; the v8 migration's version stamp was made a literal (atomicity fix).

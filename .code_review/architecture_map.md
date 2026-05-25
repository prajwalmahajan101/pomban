# Architecture Map — Current Snapshot

Stack: tui
_Last updated: 2026-05-25_

Framework: Textual (Python). Entry point `pomodoro/__main__.py` (also `pomban` CLI: `export`, `sprint export`). Packaged under `src/pomodoro` (src layout). 106 test functions across 18 test modules.

## Components & Responsibilities

### Core (pure / I/O domain) — `src/pomodoro/core/`
- `timer_engine.py` — Pure Pomodoro state machine. `Phase` / `Event` enums, immutable `Settings`, `TimerEngine` driven by injected `now`. No UI, no DB.
- `db.py` — SQLite persistence. XDG data dir, `PRAGMA user_version` migrations v1→v6 (tasks, sessions, session_tasks, interruptions, projects, recurring_templates, sprints). All stats/burndown/analytics queries live here. Returns dataclasses.
- `config.py` — TOML config (XDG config dir) with dataclass sections, forward-compatible key filtering, `save()`, and `to_settings`/`to_notify_config` adapters.
- `models.py` — Frozen-ish dataclasses: `Task`, `Session`, `Project`, `Sprint` with `Literal` status types.
- `exporter.py` — Markdown export of recent sessions.

### App orchestration — `src/pomodoro/app.py`
- `PomodoroApp(App)` — single coordinator: owns `engine`, `db`, `config`, `music`, active-task list, project/sprint filter state, session lifecycle, lunch scheduling, resume-on-launch, global key actions, theme cycling. 0.25s `set_interval` tick drives the engine and active-screen refresh. (God object — see learning.md.)

### Side-effect adapters — `src/pomodoro/`
- `notifications.py` — desktop (notify-send) + sound (paplay/aplay/ffplay) + bell; fire-and-forget, error-isolated.
- `music.py` — `MusicController` drives external player (default `cliamp`) on phase events; Popen + DEVNULL, logs to state dir.
- `plugins.py` — entry-point plugin registry (`pomodoro.hooks` group), per-callback try/except; `git_sync` for optional commit-on-exit.

### Screens — `src/pomodoro/screens/`
- Full screens: `dashboard` (timer + task list + stats strip), `kanban` (3-column board, cursor nav, visual multi-select), `stats` (bucket bars, est-accuracy sparkline, heatmap, per-project bars, drill-down, burndown), `history`, `projects`, `sprints`.
- Modals: `session_end` (+ `MultiCompleteModal`), `help`, `presets`, `resume`, `project_picker`, `sprint_picker`, `edit_task`.

### Widgets — `src/pomodoro/widgets/`
- `timer_display` (reactive), `stats_strip`, `card` (TaskCard + badge/chip renderers), `heatmap`, `bar_chart` (h/v bars), `sparkline`.

## Data Flow

```
key / input  →  Screen action / app action
                      │
                      ▼
            PomodoroApp action methods ──► TimerEngine (pure)  ──► list[Event]
                      │                          ▲
                      │  set_interval(0.25s)._tick │ injected now
                      ▼                          │
                 DB (SQLite)  ◄── session lifecycle, tasks, stats
                      │
                      ▼
           screen.refresh_* (duck-typed) ──► reactive widgets ──► Textual render
                      │
                      └──► side effects: notifications / music / plugins (fire-and-forget, logged)
```

## Layer Boundaries

- **Clean:** core (engine/db/config/models) has zero Textual imports; db deliberately mirrors color list to avoid importing textual at load (db.py:16-18). Side-effect modules are self-contained and never raise into the UI.
- **Leaky:** `app.py` reaches into `engine` private fields on resume/lunch (bypassing the state machine API); screens reach back into `app.db` directly for reads/writes (no repository/service seam); cross-screen refresh is by string-named method lookup rather than an interface.

## Persistence
- SQLite at `$XDG_DATA_HOME/pomodoro/pomodoro.db`. `config_kv` table doubles as UI state store (active project/sprint filters, pending-session resume keys). `foreign_keys = ON`, but `session_tasks.task_id` lacks `ON DELETE CASCADE`.
</content>

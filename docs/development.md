# Development

For contributors, plugin authors, and anyone curious about how the app is wired.

## Contents

1. [Architecture overview](#architecture-overview)
2. [Module layout](#module-layout)
3. [Database schema](#database-schema)
4. [The TimerEngine state machine](#the-timerengine-state-machine)
5. [Adding a new screen](#adding-a-new-screen)
6. [Plugins](#plugins)
7. [Testing](#testing)
8. [Releasing](#releasing)

---

## Architecture overview

Three layers, strictly separated:

```
  ┌─────────────────────────────────────────────────────────────┐
  │  Textual UI                                                 │
  │  ┌────────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐    │
  │  │ Dashboard  │  │  Kanban  │  │  Stats  │  │ History  │    │
  │  └────────────┘  └──────────┘  └─────────┘  └──────────┘    │
  │       (screens/ + widgets/)                                 │
  └──────────────────────────┬──────────────────────────────────┘
                             │  reads/writes via App methods
  ┌──────────────────────────▼──────────────────────────────────┐
  │  App orchestration  (app.py)                                │
  │  - Owns engine, db, active_task, current_session_id         │
  │  - Routes Textual events ↔ engine ↔ db                      │
  │  - Hosts modals (session_end, presets, resume)              │
  └──────────────────────────┬──────────────────────────────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       ▼                     ▼                     ▼
  ┌─────────────┐      ┌──────────┐         ┌──────────────┐
  │ TimerEngine │      │   DB     │         │ Notifications│
  │ (pure)      │      │ (SQLite) │         │ + Plugins    │
  └─────────────┘      └──────────┘         └──────────────┘
```

Design principles:

1. **The engine is pure.** No DB calls, no Textual references, no I/O. It takes a `now: float` from the caller. This lets us unit-test every state transition with a fake clock.
2. **The DB is dumb.** Plain CRUD + simple aggregates. No business logic. Migrations via `PRAGMA user_version`.
3. **The app glues them.** All branching ("does completing this end the session as completed=1 or 0?") lives in `app.py`, where it's easy to read.

---

## Module layout

```
src/pomodoro/
├── __main__.py           # CLI entrypoint (also handles `export` subcommand)
├── app.py                # PomodoroApp — the Textual App orchestrator
├── notifications.py      # notify-send + sound + hook runner
├── plugins.py            # entry-point discovery + git_sync
├── core/
│   ├── timer_engine.py   # Pure state machine (Phase, Event, Settings, TimerEngine)
│   ├── db.py             # SQLite wrapper, migrations, queries
│   ├── models.py         # Task, Session dataclasses
│   ├── config.py         # TOML loader, save, dataclasses
│   └── exporter.py       # Markdown export formatter
├── screens/
│   ├── dashboard.py      # The default screen
│   ├── kanban.py         # Three-column board
│   ├── stats.py          # Heatmap + summaries
│   ├── history.py        # DataTable of sessions
│   ├── session_end.py    # Modal after phase completes
│   ├── presets.py        # Preset picker modal
│   ├── resume.py         # "Resume previous session?" modal
│   └── help.py           # `?` overlay
└── widgets/
    ├── timer_display.py  # Big countdown + cycle dots
    ├── stats_strip.py    # Top bar on Dashboard
    ├── card.py           # Kanban TaskCard
    └── heatmap.py        # Unicode-block bar chart
```

Test layout mirrors source:

```
tests/
├── test_timer_engine.py
├── test_db.py
├── test_db_kanban.py
├── test_app_smoke.py
├── test_app_kanban.py
├── test_app_stats.py
├── test_config.py
├── test_tags.py
├── test_stats_and_migration.py
├── test_phase12.py        # presets + hooks + export
├── test_resume.py
└── test_plugins_and_sync.py
```

---

## Database schema

Current `PRAGMA user_version = 2`. Migrations are versioned and idempotent.

```sql
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

CREATE TABLE session_tasks (              -- join, supports multi-task sessions
  session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
  task_id INTEGER REFERENCES tasks(id),
  completed_during_session INTEGER DEFAULT 0,
  PRIMARY KEY (session_id, task_id)
);

CREATE TABLE interruptions (              -- added in v2
  id INTEGER PRIMARY KEY,
  session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
  at TEXT NOT NULL,
  reason TEXT DEFAULT ''
);

CREATE TABLE config_kv (                  -- general key/value store; used for resume state
  key TEXT PRIMARY KEY,
  value TEXT
);
```

### Adding a migration

In `core/db.py`:

1. Bump `SCHEMA_VERSION` (e.g. to 3).
2. Append a new `if version < 3:` block inside `_migrate()`.
3. Add a test in `tests/test_stats_and_migration.py` that builds a v(N-1) DB by hand, opens it through `DB(...)`, and asserts the new structure exists and old rows survive.

Never modify existing migration blocks — only append.

---

## The TimerEngine state machine

`src/pomodoro/core/timer_engine.py` is the single source of truth for time logic. ~150 lines, no imports outside stdlib.

### States

`Phase`: `IDLE`, `FOCUS`, `SHORT_BREAK`, `LONG_BREAK`.

`TimerEngine` adds three boolean flags:
- `running` — clock is decrementing
- `awaiting_decision` — phase ended, waiting for user choice (modal-equivalent state)
- `_warning_fired` — has the "ending soon" event been emitted for this phase

### Transitions

```
                       start()             tick()
                      ───────▶            ──────▶
       IDLE ────────▶ FOCUS (running) ──── remaining=0 ─▶ FOCUS (awaiting_decision)
                                                                  │
                          ┌──── extend(seconds) ────────┐          │
                          │  remaining += seconds        │          │ confirm_advance()
                          │  awaiting_decision=False     │          ▼
                          │  running=True                │     SHORT_BREAK / LONG_BREAK
                          └──────────────────────────────┘
```

`skip()` = `_complete()` + `confirm_advance()` — one-shot version that bypasses the awaiting-decision state.

### Events

`tick()` returns a `list[Event]`. The app drives event handling in `_handle_events`.

- `PHASE_STARTED` — emitted by `_enter(new_phase)`
- `PHASE_COMPLETED` — emitted by `_complete()`, alongside `awaiting_decision=True`
- `PHASE_ENDING_SOON` — emitted once when `remaining` first drops to `≤ warning_seconds`

### Why split complete and advance?

The earlier MVP auto-advanced (focus → break immediately). That made the "did you finish the task?" prompt impossible to express cleanly. The split lets the UI park between phases and ask the user. The cost is one extra method call (`confirm_advance`), which is tiny.

---

## Adding a new screen

1. Create `src/pomodoro/screens/<your>.py` subclassing `textual.screen.Screen`.
2. Define `BINDINGS` and `compose()`.
3. Register in `app.py:on_mount`:

   ```python
   self.install_screen(YourScreen(), name="your")
   ```

4. Add a number binding to `BINDINGS` on every screen that should jump to yours:

   ```python
   Binding("5", "app.switch('your')", "Yours"),
   ```

5. Extend `action_switch` in `app.py` to allow the new name.

For modals, subclass `ModalScreen[ReturnType]` and call `self.dismiss(value)` to return.

### Conventions

- Don't override `refresh()` on a `Screen` — Textual uses it internally. Name your refresh method `refresh_<thing>` (e.g. `refresh_board`, `refresh_stats_screen`).
- Bind app-level actions with the `app.` prefix: `Binding("s", "app.toggle", "Pause")`.
- Avoid screen-private state for things the app owns (engine, current_session_id, active_task). Read them off `self.app`.

---

## Plugins

In-process Python hooks discovered via setuptools entry points.

### Plugin API

A plugin is any Python object that exposes any of:

```python
def on_phase_started(phase: str, task_title: str | None) -> None: ...
def on_phase_completed(phase: str, task_title: str | None, completed: bool) -> None: ...
```

`phase` is one of `"focus"`, `"short_break"`, `"long_break"`. `completed` is `True` if the session ended naturally (user picked `c`/`k` on the modal), `False` if reset/skipped/discarded.

### Wiring

Your plugin package's `pyproject.toml`:

```toml
[project]
name = "pomodoro-plugin-myplugin"
version = "0.1.0"

[project.entry-points."pomodoro.hooks"]
mything = "my_module:plugin"
```

Where `my_module.py`:

```python
class plugin:
    @staticmethod
    def on_phase_started(phase, task_title):
        ...

    @staticmethod
    def on_phase_completed(phase, task_title, completed):
        ...
```

Install with `pip install -e .` in the same venv as `pomodoro` — entry points are discovered on app launch (`PomodoroApp.on_mount` calls `registry().discover()`).

### Safety

Every callback runs inside try/except. Errors are written to `~/.local/state/pomodoro/plugins.log` and **never** propagate to the app. A buggy plugin cannot crash your timer.

### Example

See `examples/plugin-print-events/` — a minimal plugin that prints every transition to stderr. Use it as a template.

### Hooks vs plugins — which to use?

| Need | Use |
|---|---|
| Run a shell command, no logic | `[hooks]` in config |
| Talk to a Python library (requests, sqlite3, …) | Plugin |
| Cross-platform without shelling out | Plugin |
| Quick personal automation, won't share | `[hooks]` |
| Reusable, distributed via PyPI | Plugin |

---

## Testing

```bash
pytest -q          # all 68 tests
pytest tests/test_timer_engine.py        # one file
pytest -k "session_end"                  # by name pattern
```

### Test layers

1. **Unit** — pure functions and the engine. No I/O. Fast (<1s total).
2. **DB** — opens a real SQLite file in a `tempfile.TemporaryDirectory`. Closes after each test.
3. **Integration (Textual Pilot)** — full `PomodoroApp.run_test()` with simulated key presses. The fast-mode timer (`fast=True`) shrinks durations to seconds so a full focus→modal flow finishes in ~6s.

### Useful patterns

Waiting for a particular screen to become active:

```python
async def wait_for(pilot, screen_cls):
    for _ in range(40):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(type(pilot.app.screen))
```

Building an old-schema DB to test migrations:

```python
raw = sqlite3.connect(str(db_path))
raw.executescript("CREATE TABLE … ; PRAGMA user_version = 1;")
raw.commit(); raw.close()
db = DB(db_path)  # migration runs here
```

### Adding tests for a new phase / feature

Follow the per-phase test budget in [the plan file](../../.claude/plans/mutable-waddling-puppy.md) §12.5. Approximate split: 2 unit + 2 DB + 2 integration per feature.

---

## Releasing

This project doesn't currently target PyPI — it's a personal-use TUI. If you want to publish:

1. `python -m build` (needs `pip install build`).
2. `twine upload dist/*`.
3. Tag the commit (`git tag v0.1.0 && git push --tags`).

If you fork it and want to redistribute, please rename the entry point (`pomodoro` is a generic command, your fork should pick something distinct like `pomod`, `tuipom`, etc.) and update `pyproject.toml` accordingly.

---

## Contributing checklist

Before opening a PR (or merging your own branch):

- [ ] `pytest -q` passes
- [ ] New features have at least one unit/DB test and one integration test
- [ ] Public-facing changes are reflected in `docs/user-guide.md` and `docs/keybindings.md`
- [ ] Schema changes have a migration block + a migration test
- [ ] Shift-modified keybindings include at least one symbol alias (Kitty et al. eat them)
- [ ] No new dependencies unless they earn their weight (current deps: `textual`)

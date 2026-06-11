# pomban — Project Conventions

A keyboard-driven Pomodoro TUI with kanban, projects, sprints, and
local-first SQLite persistence. Built with Textual.

## Stack

- Python ≥ 3.11
- [Textual](https://textual.textualize.io/) for the TUI
- SQLite via stdlib `sqlite3` — **one connection, single writer**
  (see [ADR-0002](docs/adr/0002-single-sqlite-connection.md))
- Ruff (format + lint, pinned 0.15.16), pytest (`asyncio_mode = auto`)
- pip-tools (`requirements/*.in` → `*.txt`) for reproducible dev installs
- pre-commit enforced

## Layout

`src/` layout. Layered:

| Layer | Responsibility |
|---|---|
| `core/` | DB, timer engine, config, logging, value objects (`Task`, `ProjectFilter`, `FilterState`), session coordinator. No Textual imports. |
| `screens/` | One `AppScreen` per top-level view (dashboard, kanban, stats, history, projects, sprints) + modals (resume, presets, session-end, card-detail). |
| `widgets/` | Reusable Textual widgets (timer display, stats strip, card, panel title, sparkline). |
| `plugins/` | In-process plugin registry + first-party plugins (`git_sync`). |
| `notifications.py` | Desktop / sound / in-TUI bell. |

`screens/` never reach into another screen's internals; they all
extend `AppScreen` and the tick / refresh / nav loop dispatches via
`isinstance(scr, AppScreen)` — see
[ADR-0003](docs/adr/0003-layered-screen-architecture.md).

## Code Style

- `from __future__ import annotations` at the top of every module.
- Type hints at boundaries (public methods, dataclasses). Mypy isn't
  the gate yet, but the `[tool.mypy]` block is wired up.
- Module-level import of `from pomban.core import log`. Boundary
  catches call `log.exception("<context>")`; the logger writes to a
  file only (`~/.local/state/pomban/pomban.log`) so it can't
  corrupt the alternate-screen TUI.
- Errors at system boundaries (DB, hooks, plugins, screen mounts)
  may be caught and logged. **Don't** add blanket
  `except Exception: pass` for control flow.
- Cosmetic UI side effects (`notify`, `bell`, `animate`) may stay
  silent — they fire during teardown / animation races where noise
  in the log is worse than a missed UI nicety.
- Comments only when the *why* is non-obvious. The code says *what*;
  don't restate it.

## Commit Discipline

- Conventional commits: `feat(scope): …`, `fix(scope): …`,
  `refactor`, `docs`, `test`, `chore`.
- Subject ≤ 72 chars, imperative, no trailing period.
- Atomic — one logical change per commit.
- Never `--no-verify`. Never amend pushed commits. **No AI
  attribution footer.**
- `main` is releasable. Work on `feature/<topic>` / `fix/<topic>` /
  `docs/<topic>` / `refactor/<topic>` branches.

## Testing

- Unit tests for `core/` (engine, DB, filters, session coordinator,
  task parser). Async pilot tests for screens (`tests/test_app_*`,
  `tests/test_dashboard_focus.py`).
- Sample DB seeded per-test in a `tmp_path`-scoped fixture.
- `pytest -q` is the gate; 168 tests live today.

## ADRs

`docs/adr/NNNN-slug.md`. Update / add when an architectural decision
changes. See `CONTRIBUTING.md` for trigger rules and
[`docs/site/adr.md`](docs/site/adr.md) for the index.

## Living code-review state

`.code_review/` tracks active and resolved issues, an architecture
map, and recurring-pattern notes. Update those files when you fix a
tracked issue or land work that retires one.

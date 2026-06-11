# ADR 0001 — Stack Choice

Status: Accepted (2026-06-11)

## Context

pomban is a keyboard-driven Pomodoro TUI with a kanban / projects /
sprints surface and local-first persistence. It needs:

- A TUI framework that handles layout, scrolling, theming, async
  input, and the alternate-screen lifecycle without surprises.
- A storage layer for tasks, sessions, projects, sprints, and
  configuration state — small schema, single user, no concurrency.
- A configuration loader that tolerates partial / hand-edited files
  without crashing on unknown keys.
- An XDG-correct paths discipline so the app lives where Linux
  expects it to live without forcing a flag.

The project is solo, phase-driven, and targets a single user on a
single machine. Cross-device sync is solved by a git plugin, not by
a server.

## Decision

| Concern | Choice |
|---|---|
| TUI framework | **Textual** — async, CSS theming, focused-pane model, mature |
| Storage | **SQLite via stdlib `sqlite3`** — single connection, hand-rolled migrations |
| Config | **stdlib `tomllib`** + dataclass loader; unknown keys filtered |
| Paths | XDG via stdlib `os.environ` + sensible defaults |
| Logging | **`core/log.py`** — stdlib `logging` to a file in `XDG_STATE_HOME` only |
| Lint / format | **Ruff** (pinned 0.15.16, both linter and formatter) |
| Tests | **pytest** with `asyncio_mode = auto` for the Textual pilot |
| Pre-commit | **pre-commit** — ruff, mypy, end-of-file-fixer, trailing-whitespace |

No ORM, no settings library, no async DB driver. The schema is
small enough that raw `sqlite3` keeps the surface area down.

## Consequences

**Positive**

- Textual gives async, theming, focus-pane (btop-style), and resize
  handling for free.
- SQLite via stdlib means zero ORM overhead and no extra runtime
  dependency. Hand-rolled migrations are unavoidable but the schema
  is small.
- `tomllib` (stdlib in 3.11) + dataclasses means the config loader
  has no third-party dependency and no runtime cost.
- `core/log.py` writing only to a file in `XDG_STATE_HOME` means the
  logger can't accidentally corrupt the alternate-screen TUI.

**Negative / risks**

- Textual is moving fast; we pin a known-good `>= 0.79` and bump
  intentionally.
- Hand-rolled migrations need discipline. We version-stamp every
  migration as a literal (not derived from a variable) for atomicity
  — see the v8 → v9 fix in the code-review history.
- No ORM means raw SQL everywhere. We keep all DB code in `core/db.py`
  and `core/session_service.py` to contain the blast radius.

## Usage

- New persistence work goes through `core/db.py` or a service module
  in `core/`; screens never touch `sqlite3` directly.
- New TUI work subclasses `screens.base.AppScreen` so it slots into
  the tick / refresh / nav loop without editing string-name lists.
  See [ADR-0003](0003-layered-screen-architecture.md).
- New boundary failures route through `core/log.py` with
  `log.exception("<context>")`; cosmetic UI side effects stay silent.
- New config sections are dataclasses in `core/config.py` with
  `_filter_kwargs` applied so unknown keys don't crash the loader.

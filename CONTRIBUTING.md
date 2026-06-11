# Contributing to Pomodoro

Thanks for considering it. The bar is high but the process is
mechanical — match it and your PR should sail through.

## Quick start

```bash
git clone https://github.com/prajwalmahajan101/pomban
cd pomban
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## The full local gate (CI runs the same thing)

```bash
pytest -q
ruff format --check . && ruff check src/ tests/
mypy src/                       # optional today; required once strict mode lands
```

All three must be green before pushing. `pre-commit` will catch most
of this on commit; CI is the backstop.

## Branch + commit policy

- **Never commit to `main`.** Cut a branch named `feature/<topic>`,
  `fix/<topic>`, `refactor/<topic>`, `docs/<topic>`, or
  `chore/<topic>` and merge via PR.
- **Conventional commits.** Subject ≤ 72 chars, imperative mood, no
  trailing period:
  - `feat(scope): add X`
  - `fix(scope): handle Y`
  - `refactor(scope): …`
  - `docs(scope): …`
  - `test(scope): …`
  - `chore(scope): …`
- **Atomic commits.** One logical change per commit; no WIP commits
  on branches that will be PR'd.
- **No AI attribution.** Don't append `Co-Authored-By: Claude` or
  similar.
- **No `--no-verify` or `--no-gpg-sign`.** If a hook fails, fix the
  cause.

## Architectural conventions

Pomodoro is a layered Textual TUI. The layers are:

| Layer | Responsibility |
|---|---|
| `core/` | DB, timer engine, config, logging, value objects (`Task`, `ProjectFilter`, `FilterState`), session coordinator, structured logger. No Textual imports. |
| `screens/` | One `AppScreen` per top-level view (dashboard, kanban, stats, history, projects, sprints, modals). Owns its `BINDINGS`, `compose`, and `refresh_view` / `refresh_timer`. |
| `widgets/` | Reusable Textual widgets (timer display, stats strip, card, panel title). No DB access. |
| `plugins/` | In-process plugin registry + first-party plugins (`git_sync`). |

- The 0.25 s tick path is hot — keep DB writes off it. See
  [ADR-0002](docs/adr/0002-single-sqlite-connection.md).
- New top-level screens slot into the tick / refresh / nav via
  `isinstance(scr, AppScreen)`; never edit a string-name list.
- Errors at boundary calls route through `core/log.py`. Don't add
  blanket `except Exception: pass` — silent failures mask real bugs.
  Cosmetic UI side effects (`notify`, `bell`, `animate`) are the
  exception and may stay silent.
- Module-level imports of `pomodoro.core.log as log`; call
  `log.exception("<context>")` from boundary catches.
- `from __future__ import annotations` at the top of every module.
- Inline comments only when the *why* is non-obvious. Don't narrate
  the *what* — the code is the source of truth.

## When to write an ADR

Add `docs/adr/NNNN-<slug>.md` whenever you change:

- A persistence schema (any `core/db.py` migration).
- A protocol between layers (`core/` ↔ `screens/`).
- A dependency choice (adding / removing a runtime dep).
- A user-visible behaviour that's not obvious from the code (e.g. the
  music-feature removal, the single-SQLite-connection policy).

Pattern: **Context · Decision · Consequences · Usage**. See existing
ADRs under `docs/adr/` for the shape.

## Pull requests

- One PR per logical change. Multi-phase work is fine as separate PRs.
- PR description: what changed, why, how you verified, screenshots for
  UI changes (vhs / SVG capture is fine).
- Make sure CI is green before requesting review.

## Releasing

Maintainer only. See [RELEASE_PLAN.md](./RELEASE_PLAN.md). Tag-driven,
fully automated via `.github/workflows/release.yml`.

## Code-review state

This repo keeps a living code-review state under `.code_review/`:

- `architecture_map.md` — high-level ASCII map.
- `code_review_history.md` — prior review sessions.
- `code_review_issues.md` — active and resolved issues.
- `learning.md` — recurring patterns + anti-patterns.

When you fix a tracked issue or introduce a new one, update those
files in the same PR.

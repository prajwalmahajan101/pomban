# Changelog

All notable changes to pomban are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-06-12

The "personal productivity platform" release. Tasks now live inside
sprints inside projects, every screen carries that context, and the
focus loop grows blocker capture, session notes, a Today digest, and
quiet-hours-aware notifications. Exports gain CSV / JSON / grouped
markdown for downstream review.

### Changed
- **Renamed package from `pomodoro` to `pomban`.** PyPI distribution,
  CLI binary, Python package, and XDG directories all migrate to the
  `pomban` name. On first launch, a one-shot migration shim renames
  the legacy `~/.local/share/pomodoro/`, `~/.local/state/pomodoro/`,
  and `~/.config/pomodoro/` directories (and the `pomodoro.db` /
  `pomodoro.log` files inside them) to their `pomban` equivalents.
  No-op when the new paths already exist.
- **Schema v10** — `tasks.project_id` becomes NOT NULL (legacy rows
  migrate to an auto-seeded "Inbox" project); `tasks.sprint_id` /
  `sprints.project_id` FKs added; "one active sprint per project"
  enforced in code (see [ADR-0005](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0005-project-sprint-task-hierarchy.md)).
- **README + docs site** reframed around the platform model
  (Plan / Focus / Review / Integrate) rather than "Pomodoro TUI".
- **Notifications** route through a single
  `notifications.notify(...)` funnel that consults the
  working-hours gate before firing desktop popup / sound channels.

### Added
- **Project → sprint → task hierarchy** as the platform's planning
  model. Inline `@project` / `!sprint` / `#tag` / `~N` syntax for
  keyboard-driven assignment ([ADR-0005](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0005-project-sprint-task-hierarchy.md)).
- **Context header** on every screen — active project + sprint chip
  + quiet-state chip, refreshed on every tick.
- **Dashboard + Kanban sprint panels** — current sprint progress
  pinned to the planning screens.
- **`PombanEngine` facade** (`core/engine.py`) owns timer +
  session orchestration end-to-end. `app.py` loses ~200 lines of
  lifecycle plumbing ([ADR-0006](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0006-pomban-engine-facade.md)).
- **`FirstRunModal`** — empty-DB launches walk through creating
  the first project so the hierarchy is never empty.
- **`SprintRunnerScreen`** (`Shift+R`) — overlay with the current
  sprint goal pinned regardless of which screen is active.
- **`SprintCompleteScreen`** — fires when `pomodoro_target` is
  crossed; closes the sprint with a retro field.
- **Inline `s` binding** on the Projects screen creates and
  activates a sprint for the focused project in one keystroke.
- **Blocker capture (`b`)** — log a one-line blocker against the
  live focus session without breaking the timer.
- **Session notes** — session-end modal field surfaces inline on
  the History screen.
- **Today digest (`7`)** — daily recap screen with sessions, top
  tasks, interruptions, and blocker list bound to the `7` digit.
- **Per-tag analytics panel** on the Stats screen (`3`),
  powered by `minutes_per_tag`.
- **Exports** — `pomban export --format csv|json|markdown`. The
  grouped-markdown format buckets sessions by project → sprint →
  task. `pomban sprint export …` for per-sprint reports.
- **Working-hours quiet** — `[breaks].working_hours_start` /
  `working_hours_end` ("HH:MM") suppress desktop popup + sound
  outside the window; the in-TUI bell still fires; header chip
  reflects the current quiet state ([ADR-0004](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0004-working-hours-quiet.md)).
- `ROADMAP.md` and `RELEASE_PLAN.md` at the repo root — forward-looking
  phase plan and the mechanics of cutting a release (tag-driven via
  `release.yml`).
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `CLAUDE.md` at
  the repo root — keep-a-changelog history, contributor onboarding,
  vulnerability-disclosure policy, and internal conventions spec.
- **mkdocs-material documentation site** scaffolded under `docs/site/`
  with index, install, quickstart, troubleshooting, ADR index, and
  changelog pages alongside the existing user-guide / keybindings /
  configuration / development pages. Auto-deployed via
  `.github/workflows/docs.yml` on every push to `main` that touches
  the docs.
- **Architecture Decision Records** under `docs/adr/`. Seeded with
  three retrospective ADRs (stack choice, single-SQLite-connection
  policy, layered-screen architecture); v0.2.0 adds three more —
  [ADR-0004](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0004-working-hours-quiet.md) (working-hours
  quiet), [ADR-0005](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0005-project-sprint-task-hierarchy.md)
  (PM hierarchy), and
  [ADR-0006](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0006-pomban-engine-facade.md) (`PombanEngine`
  facade).
- **`scripts/capture_screenshots.py`** — Textual pilot harness that
  drives `PomodoroApp` against an in-memory DB and emits hero SVGs
  for the dashboard, kanban, and stats screens.
- **`docs/demo.tape`** — vhs script for an animated README hero.
  Render with `vhs docs/demo.tape` (requires `vhs`/`ffmpeg`/`ttyd`).
- **`.pre-commit-config.yaml`** with ruff, mypy, and the standard
  pre-commit-hooks (end-of-file-fixer, trailing-whitespace, yaml,
  large-files).
- **`requirements/base.in` + `requirements/dev.in`** mirroring the
  `pyproject.toml` dependency tables for pip-tools workflows.
- **`docs` and `mypy` extras** under `[project.optional-dependencies]`.
- **`.github/workflows/release.yml`** and **`docs.yml`** —
  tag-driven PyPI publish via OIDC trusted publishing plus
  CHANGELOG-extracted GitHub Release notes; conditional docs deploy
  to GitHub Pages.

## [0.1.0] — 2026-06-11

Initial pre-release of the pomban dashboard TUI. Captures every
feature shipped on `main` to date.

### Added
- **Pomodoro timer engine** (`core/timer_engine.py`) with focus,
  short-break, long-break, lunch-pause, and idle phases; configurable
  cycle counts; auto-advance toggle; `extend`, `skip`, and `restore`
  state transitions.
- **Dashboard screen** — timer, focused-task chip, stats strip,
  task list, inline `#tag`/`@project`/`!sprint`/`~N` task syntax.
- **Kanban board** (`2`) with priorities, due dates (overdue render
  red), per-column WIP limits (`[kanban]` config), board search (`/`),
  bulk visual-mode actions (`v` then `Space`/`c`/`d`/`Shift+H,L`),
  and a card detail screen (`i`).
- **Stats screen** (`3`) — daily / weekly / monthly bucket views,
  top tasks, interruption stats.
- **History screen** (`4`) — every session, paged, with planned vs.
  actual durations.
- **Projects screen** (`5`) and **Sprints screen** (`6`) — full CRUD,
  archiving, completion states; tasks released back to backlog on
  sprint delete.
- **Resume prompt** — quit mid-focus, get a "resume? y/n" overlay on
  next launch.
- **Lunch break** — `Shift+L` triggers a long pause anywhere; the
  session-end modal suggests it inside a configurable
  `[breaks].lunch_window_*`.
- **Presets** — `[[preset]]` blocks switchable via `p`; classic 25/5,
  deep-work 50/10, sprint 15/3 ship as defaults.
- **Themes** — `nord`, `gruvbox`, `dracula`, `catppuccin-mocha`,
  `tokyo-night`. Cycle with `t`; persisted to `config.toml`.
- **Auto-advance** (`Shift+T`) — skip the end-of-phase modal and roll
  straight into the next phase, classic-Pomodoro style.
- **Hooks** — `[hooks].on_focus_start` / `on_focus_end` /
  `on_break_start` / `on_break_end` shell commands invoked with
  `POMODORO_PHASE` and `POMODORO_TASK_TITLE` env vars.
- **In-process plugins** — Python entry points discovered at startup;
  exceptions are sandboxed and never crash the app.
- **`git_sync` plugin** — commits the SQLite library on exit so it
  can sync across devices via a personal git remote.
- **btop-style panel hotkeys** — `widgets/panel.py` +
  `AppScreen.action_focus_pane` give each pane a highlighted-letter
  selector (Dashboard: `i` Timer, `a` Tasks).
- **Structured logging** via `core/log.py` — file-only writes to
  `~/.local/state/pomban/pomban.log`; never touches stdout while
  the TUI owns the terminal.

### Removed
- **Music / cliamp subsystem** — the entire `[music]` config section,
  music controller, dashboard music panel, dedicated music screen,
  and `--with-music` CLI flag. No DB impact (music state was read
  live from the external player and never persisted).

### Fixed
- Six meaningful `except Exception: pass` sites in `app.py` now route
  to `log.exception` (four DB reads, two `save_config` calls). Cosmetic
  notify/bell/animate sites are intentionally left silent.

## Resolved code-review issues (cumulative)

Tracked in [`.code_review/code_review_issues.md`](https://github.com/prajwalmahajan101/pomban/blob/main/.code_review/code_review_issues.md).

- **ISSUE-001 — DB writes on the tick path** (won't-fix): mitigations
  stand (cached lunch SELECT, deferred modal push). A dedicated writer
  thread would conflict with the project's single-SQLite-connection
  design. Revisit only if real-world jank is observed. See
  [ADR-0002](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0002-single-sqlite-connection.md).
- **ISSUE-005 — slim `PomodoroApp`** (resolved): `core/filter_state.py`,
  `core/session_coordinator.py`, and `core/task_input.py` extractions
  all landed. Music removal trimmed the remaining UI-action surface.
- **ISSUE-012 — swallowed excepts** (resolved): see _Fixed_ above.

[Unreleased]: https://github.com/prajwalmahajan101/pomban/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/prajwalmahajan101/pomban/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/prajwalmahajan101/pomban/releases/tag/v0.1.0

# Roadmap

Forward-looking phase plan for Pomodoro. Phases are sized to ship as
one or two PRs each. Done phases stay in this file (with their
deliverable list reduced to one line) so the trajectory is visible at
a glance.

The roadmap is **not** a promise of dates. It is a promise of order:
later phases assume the earlier ones landed.

---

## Phase 1 — Timer + Dashboard `(done)`

Pomodoro engine, dashboard screen, task list, presets, themes, hooks,
plugin loader, structured logger.

## Phase 2 — Boards + Filters `(done)`

Kanban board with priorities + WIP limits + visual-mode bulk actions
+ card detail; project + sprint pickers; sprint screen; stats and
history screens; lunch-break window + `Shift+L` long-pause.

## Phase 3 — Cleanup + Closures `(done)`

Music / cliamp subsystem removal; six meaningful swallowed-except
sites routed to `log.exception`; ISSUE-001 closed as won't-fix
(see [ADR-0002](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0002-single-sqlite-connection.md));
ISSUE-005 / ISSUE-012 resolved.

## Phase 4 — Release prep `(in progress)`

**Goal.** Bring the repo to PyPI-ready quality and ship `0.1.0`.

**Deliverables.**

- Root docs: `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`,
  `CLAUDE.md`, `ROADMAP.md`, `RELEASE_PLAN.md`. *(done — this commit)*
- mkdocs-material site under `docs/site/` with install / quickstart
  / troubleshooting / ADR index / changelog pages, deployed via
  `.github/workflows/docs.yml`. *(done — this commit)*
- ADRs `0001`–`0003` covering stack choice, single-SQLite-connection,
  and the layered-screen architecture. *(done — this commit)*
- `scripts/capture_screenshots.py` and `docs/demo.tape` scaffolded;
  generated SVGs / GIF committed to `docs/screenshots/`.
- `.pre-commit-config.yaml`, `requirements/{base,dev}.in`, `[tool.mypy]`
  in `pyproject.toml`, `docs` + `mypy` extras.
- `release.yml` workflow (tag-driven, PyPI trusted publishing,
  CHANGELOG-extracted release notes).
- PyPI account + trusted-publisher binding configured (out-of-band).

**Success criteria.**

- `pipx install pomodoro` works from PyPI.
- The docs site renders at `https://prajwalmahajan101.github.io/pomban/`.
- `pre-commit run --all-files` is clean on `main`.
- `python -m build` produces a clean sdist + wheel; `twine check`
  passes.

## Phase 5 — Notifications + Sound polish `(planned)`

**Goal.** Make Pomodoro feel as native as a desktop timer.

**Deliverables.**

- Cross-platform desktop-notification fallbacks (today: `notify-send`
  Linux-only). macOS via `terminal-notifier` if present; Windows via
  `win10toast` (optional dep).
- Sound theme: pluggable `[notifications.sound_file]` paths per phase
  end; default freedesktop sound, optional curated short clips
  shipped under `src/pomodoro/sounds/`.
- Bell + flash works in all supported terminals (today: kitty,
  alacritty, foot, ghostty verified; iTerm2 + WezTerm still to test).
- An ADR covering the cross-platform notification matrix.

**Success criteria.**

- `pomodoro` launches a focus session on macOS / Linux / Windows
  Terminal and fires both desktop + sound + in-TUI notifications.

## Phase 6 — Sync hardening `(planned)`

**Goal.** Make the `git_sync` plugin a reliable cross-device sync
story.

**Deliverables.**

- Push on exit (today: commits only, never pushes), behind a config
  flag with a clear "your remote can fast-forward" precondition.
- Conflict detection on launch: if `git_sync` finds the local
  `library.db` diverged from `origin/main`, prompt before reset.
- A documented "merge two libraries" workflow (export each side,
  re-import).
- Cron / systemd unit examples under `docs/site/sync.md`.

**Success criteria.**

- The author can run Pomodoro on a laptop and a desktop, switch
  between them, and never lose a session.

## Phase 7 — Plugin surface `(planned)`

**Goal.** Open enough of the engine for community plugins.

**Deliverables.**

- A documented plugin API (`docs/site/plugins.md`) covering the
  hook points (`on_phase_started`, `on_phase_completed`, `on_resume`)
  with a typed `PluginContext`.
- A second first-party plugin: ICS export of completed sessions.
- A starter template at `examples/plugin-template/`.

**Success criteria.**

- At least one externally-authored plugin lands on PyPI and works
  with no Pomodoro-side changes.

---

## Out of scope (current and explicit)

These have been considered and deferred:

- **Music / cliamp integration.** Removed in Phase 3; the
  [`code_review_issues.md`](https://github.com/prajwalmahajan101/pomban/blob/main/.code_review/code_review_issues.md) entry
  documents why. Not coming back.
- **Multi-user / multi-account.** Pomodoro is per-user, local-first.
  Sync is the only multi-device story.
- **A web dashboard.** Out of scope by design; the project's identity
  is "terminal-first".
- **A dedicated SQLite writer thread.** Considered for ISSUE-001 and
  rejected — see [ADR-0002](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0002-single-sqlite-connection.md).

---

The latest snapshot of in-flight work is always in
[`.code_review/code_review_issues.md`](https://github.com/prajwalmahajan101/pomban/blob/main/.code_review/code_review_issues.md).
This document is the longer arc.

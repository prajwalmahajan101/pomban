# Roadmap

Forward-looking phase plan for pomban. Phases are sized to ship as
one or two PRs each. Done phases stay in this file (with their
deliverable list reduced to one line) so the trajectory is visible at
a glance.

The roadmap is **not** a promise of dates. It is a promise of order:
later phases assume the earlier ones landed.

## Phase ↔ tag map

| Phase | Tag | Status |
|---|---|---|
| Phase 1 — Timer + Dashboard | [`v0.1.0`](https://github.com/prajwalmahajan101/pomban/releases/tag/v0.1.0) | shipped |
| Phase 2 — Boards + Filters | [`v0.1.0`](https://github.com/prajwalmahajan101/pomban/releases/tag/v0.1.0) | shipped |
| Phase 3 — Cleanup + Closures | (unreleased; lands on `main`) | merged |
| Phase 4 — PM reframing + release | [`v0.2.0`](https://github.com/prajwalmahajan101/pomban/releases/tag/v0.2.0) | shipped |
| Phase 4.6 — Onboarding + planning UX polish | [`v0.3.0`](https://github.com/prajwalmahajan101/pomban/releases/tag/v0.3.0) | shipped |
| Phase 5 — Notifications + Sound polish | `v0.4.0` (planned) | planned |
| Phase 6 — Sync hardening | `v0.5.0` (planned) | planned |
| Phase 7 — Plugin surface | `v1.0.0` (planned) | planned |

Phases 1 and 2 shipped as a single `v0.1.0` cut because the project
was solo and the kanban / sprints work landed before the first tag
was pushed. From `v0.2.0` onward, one phase = one tag.

---

## Phase 1 — Timer + Dashboard `(shipped — v0.1.0)`

Pomodoro engine, dashboard screen, task list, presets, themes, hooks,
plugin loader, structured logger.

## Phase 2 — Boards + Filters `(shipped — v0.1.0)`

Kanban board with priorities + WIP limits + visual-mode bulk actions
+ card detail; project + sprint pickers; sprint screen; stats and
history screens; lunch-break window + `Shift+L` long-pause.

## Phase 3 — Cleanup + Closures `(merged — unreleased)`

Music / cliamp subsystem removal; six meaningful swallowed-except
sites routed to `log.exception`; ISSUE-001 closed as won't-fix
(see [ADR-0002](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0002-single-sqlite-connection.md));
ISSUE-005 / ISSUE-012 resolved. Folded into the next tagged release.

## Phase 4 — Project-management reframing + release `(shipped 2026-06-12 as v0.2.0)`

**Goal.** Reframe pomban as a project-management TUI — make the
**Project → Sprint → Task → Pomodoro** hierarchy visible and
defaultable across every screen — and ship the result as `v0.2.0`.

The data layer already carries this shape (projects, sprints,
tasks with FKs, active-sprint enforcement, burndown). v0.2.0 makes
it the *product*. Carries the original release-prep deliverables
(PyPI packaging, screenshots, mkdocs pin, trusted publisher) inside
M1 / M5 below.

**Deliverables** (five milestones — see
[`.planning/v0.2.0-milestones.md`](https://github.com/prajwalmahajan101/pomban/blob/main/.planning/v0.2.0-milestones.md)
for the commit-by-commit breakdown).

- **M1 — Foundations & release prep.** ✓ shipped. Schema v10
  (`sessions.notes`), `db.sprint_progress` + `db.minutes_per_tag`
  helpers, PyPI metadata (`name = "pomban"`, classifiers, keywords),
  `mkdocs-material<2.0` pin, fixed `scripts/capture_screenshots.py`.
- **M2 — Hierarchy made first-class.** ✓ shipped. Persistent context header on
  every `AppScreen`, sprint-aware Dashboard + timer chip, Kanban
  reframed as sprint/project/all-tasks board, project required on
  task creation (picker fallback).
- **M2.5 — Engine / presenter decoupling.** ✓ shipped. Extract a
  `PombanEngine` facade in `core/engine.py` that owns the
  long-lived domain objects (DB, `TimerEngine`,
  `SessionCoordinator`, `FilterState`, `Settings`) and exposes a
  stable command surface returning typed outcomes
  (`Created(task)` / `NeedsProject(text)` / etc.). `PomodoroApp`
  shrinks to a thin Textual presenter (bindings, modals,
  `notify`, screen routing). Inserted before M3 so the four new
  M3 screens land on the new facade from day one. No
  user-visible change.
- **M3 — Sprint lifecycle UX.** ✓ shipped. First-run project modal, sprint
  runner overlay (`Shift+R`), sprint-completion modal at target,
  inline `s` "new sprint" on the Projects screen.
- **M4 — Supporting features.** ✓ shipped. Mid-focus blocker capture (`b`),
  session notes UI + history column, "Today" digest (`7`), per-tag
  analytics on Stats, structured CSV/JSON/grouped-markdown exports,
  working-hours notification suppression.
- **M5 — Docs reframing + tag push.** ✓ shipped. README + docs/site rewrite
  around the PM framing, ADR-0004 (working hours) + ADR-0005 (PM
  hierarchy), CHANGELOG `[0.2.0]`, ROADMAP Phase 4 → shipped,
  pyproject bump + tag → `release.yml`.

**Success criteria.**

- `pipx install pomban==0.2.0` works from PyPI.
- Clean-DB walkthrough — create project → create sprint → add
  tasks → run a focus → see header progress → close sprint with
  retro — requires no docs lookup.
- `mkdocs build --strict` clean; `release.yml` goes green on tag push.
- `pre-commit run --all-files` and `pytest -q` clean on every
  milestone-tip commit.

## Phase 4.6 — Onboarding + planning UX polish `(shipped 2026-06-12 as v0.3.0)`

**Goal.** Smooth over the rough edges first-time users hit on v0.2.0
without holding the rest of the roadmap back. Inserted between
Phase 4 and Phase 5 because two of the items (sprint modal,
WelcomeModal) materially change the planning surface and shouldn't
travel inside the same release as the notification polish.

**Deliverables.** ✓ shipped.

- Per-screen [b]HELP_INTRO[/]: every `AppScreen` ships a short
  explainer rendered above the keymap on the `?` overlay, plus a
  context-aware title (`pomban — Kanban` etc.).
- Structured `SprintCreateModal` (name, pomodoro target, duration,
  goal). Replaces the one-line `name [target]` input and the
  implicit 14-day shell sprint that the Projects screen used to
  create on `s`.
- `WelcomeModal` on first launch + rotating `StartupTipModal` on
  subsequent launches, both gated by `[ui].show_startup_tips`.

## Phase 5 — Notifications + Sound polish `(planned — targets v0.4.0)`

**Goal.** Make pomban feel as native as a desktop timer.

**Deliverables.**

- Cross-platform desktop-notification fallbacks (today: `notify-send`
  Linux-only). macOS via `terminal-notifier` if present; Windows via
  `win10toast` (optional dep).
- Sound theme: pluggable `[notifications.sound_file]` paths per phase
  end; default freedesktop sound, optional curated short clips
  shipped under `src/pomban/sounds/`.
- Bell + flash works in all supported terminals (today: kitty,
  alacritty, foot, ghostty verified; iTerm2 + WezTerm still to test).
- An ADR covering the cross-platform notification matrix.

**Success criteria.**

- `pomban` launches a focus session on macOS / Linux / Windows
  Terminal and fires both desktop + sound + in-TUI notifications.

## Phase 6 — Sync hardening `(planned — targets v0.5.0)`

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

- The author can run pomban on a laptop and a desktop, switch
  between them, and never lose a session.

## Phase 7 — Plugin surface `(planned — targets v1.0.0)`

**Goal.** Open enough of the engine for community plugins.

**Deliverables.**

- A documented plugin API (`docs/site/plugins.md`) covering the
  hook points (`on_phase_started`, `on_phase_completed`, `on_resume`)
  with a typed `PluginContext`.
- A second first-party plugin: ICS export of completed sessions.
- A starter template at `examples/plugin-template/`.

**Success criteria.**

- At least one externally-authored plugin lands on PyPI and works
  with no pomban-side changes.

---

## Out of scope (current and explicit)

These have been considered and deferred:

- **Music / cliamp integration.** Removed in Phase 3; the
  [`code_review_issues.md`](https://github.com/prajwalmahajan101/pomban/blob/main/.code_review/code_review_issues.md) entry
  documents why. Not coming back.
- **Multi-user / multi-account.** pomban is per-user, local-first.
  Sync is the only multi-device story.
- **A web dashboard.** Out of scope by design; the project's identity
  is "terminal-first".
- **A dedicated SQLite writer thread.** Considered for ISSUE-001 and
  rejected — see [ADR-0002](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0002-single-sqlite-connection.md).

---

The latest snapshot of in-flight work is always in
[`.code_review/code_review_issues.md`](https://github.com/prajwalmahajan101/pomban/blob/main/.code_review/code_review_issues.md).
This document is the longer arc.

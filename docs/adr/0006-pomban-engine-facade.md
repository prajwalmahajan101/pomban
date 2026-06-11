# ADR 0006 — PombanEngine facade between the timer and the Textual app

Status: Accepted (2026-06-12)

> Numbers 0004 and 0005 are reserved for v0.2.0 M5 (working hours,
> PM hierarchy). This ADR documents the Phase 4.5 facade extraction
> that landed before M3.

## Context

Heading into v0.2.0 M3 ("Sprint lifecycle UX" — first-run project
modal, `Shift+R` sprint runner overlay, sprint-completion modal,
inline `s` new-sprint on the Projects screen), `src/pomban/app.py`
had grown to 843 lines and mixed six concerns:

1. Textual app lifecycle (bindings, screen install/mount, theme).
2. Timer + session orchestration (tick loop, phase transitions,
   `_log_new_session`, `start_focus_on_many`).
3. DB access for task + project + session writes.
4. Plugin / shell-hook dispatch (`_fire_phase_hooks`).
5. Notification fire / bell + flash animation.
6. UI glue (modal callbacks, project / sprint pickers, refresh
   orchestration).

Screens already reached across all six layers via
`self.app.<anything>`. Adding the M3 screens — each of which needs
to know "is a sprint active?", "is a focus running?", "how do I
start one?" — would tangle the situation further unless the
non-UI bits were extracted first.

The three existing UI-free cores
([ADR-0003](0003-layered-screen-architecture.md)) — `TimerEngine`,
`SessionService`, `SessionCoordinator` — already covered the pure
state-machine and session-row layers, but the **orchestration that
binds them together** (tick → events → side effects, session
lifecycle, plugin hook firing, active-task tracking) still lived
in `app.py` and so was only testable through a Textual `App`
instance.

## Decision

Introduce `pomban.core.engine.PombanEngine` — a UI-agnostic facade
that owns the timer + sessions + coordinator trio and the active-task
set, and exposes a small `TickOutcome`-based API the Textual app
shell drives. The engine never imports Textual.

The shape:

- `PombanEngine.__init__(db, sessions, coord, timer, plugin_registry,
  hooks, run_hook)` — composes the three cores and accepts the
  plugin / hook plumbing as injected dependencies, so unit tests can
  pass `None` and run without a config.
- `engine.tick(now)` returns a `list[TickOutcome]` describing what
  the app should do next (`ending_soon`, `phase_completed`). The app
  shell dispatches each outcome to its existing side-effect handler
  (bell, toast, modal push).
- `engine.start_focus_on_many(tasks) -> bool` runs the pure engine
  work (mark tasks doing, reset+start the timer, open the session
  row) and returns `True` if the shell should switch to the Dashboard
  so the timer is visible.
- `engine.log_new_session()` / `engine.finalize_multi_complete(...)`
  / `engine.fire_phase_hooks(...)` move the relevant orchestration
  out of `app.py`.
- `engine.active_tasks` / `engine.active_chip_index` /
  `engine.active_task` / `engine.current_session_id` are the
  authoritative state; `PomodoroApp` exposes them via thin
  `@property` shims so screens and tests keep using
  `self.app.active_task*` / `self.app.current_session_id`
  unchanged.

The migration is incremental (six commits on the
`refactor/engine-facade` branch):

1. Scaffold the module + dataclasses, no wiring.
2. Route the 0.25 s `_tick` through `PombanEngine.tick`.
3. Move active-task state ownership onto the facade.
4. Move the session lifecycle methods onto the facade.
5. Add direct unit tests for `PombanEngine` (no Textual).
6. This ADR.

`PomodoroApp.engine` continues to be the `TimerEngine` instance for
this phase — the facade is accessible as `self._facade`. A future
refactor (M5 or later) may rename `_facade` → `engine` and `engine`
→ `timer`, but that touches every screen and is out of scope for
Phase 4.5.

## Consequences

**Positive**

- M3 screens get a clean handle (`self.app._facade`, or a future
  `self.app.engine`) for "start a focus on these tasks" / "is a
  session running?" without reaching into the Textual app shell.
- The engine has 15 dedicated unit tests that exercise the tick →
  outcome flow, session lifecycle, and hook firing without
  Textual's pilot. Behaviour is now testable in milliseconds
  instead of seconds.
- The seam between UI side effects (bell, toast, modal) and engine
  state is explicit: the engine emits a plan, the shell realises
  it.

**Negative / risks**

- `PomodoroApp` still holds the `TimerEngine` directly as
  `self.engine` for back-compat with screens that read
  `self.app.engine.{phase,remaining,running}`. The facade owns the
  same timer instance via composition, so the two references stay
  in sync, but the dual-name surface is mild duplication.
- `start_focus_on_many` is now split across two layers: the engine
  does the timer + session work; the app shell handles the
  `switch_screen` / `_refresh_all` side effects. New callers need
  to remember the second half.
- `PombanEngine` is now ~200 lines and may keep accreting if M4
  adds blocker-capture or working-hours suppression hooks. We'll
  watch and split if it crosses ~400.

## Usage

- **Calling the engine.** From screens or actions, use
  `self.app._facade.<method>` for new code; the legacy
  `self.app.engine.<TimerEngine method>` keeps working for now.
- **Adding a new orchestration method.** Put it on `PombanEngine`
  if it touches timer + DB or timer + tasks; put it on
  `PomodoroApp` only if it touches Textual screens/modals.
- **Testing.** New engine logic gets a unit test in
  `tests/test_pomban_engine.py` — pass a real on-disk DB via the
  `engine` fixture, no Textual import required. Reserve the
  Textual pilot tests in `tests/test_app_*.py` for behaviour that
  genuinely needs the running app.
- **Plugin / hook side effects.** Pass them in via the facade
  constructor (`plugin_registry`, `hooks`, `run_hook`); the engine
  is silent when those are `None`, which makes tests easy.

## Reference

- `src/pomban/core/engine.py` — facade implementation.
- `src/pomban/app.py:_tick` / `_dispatch_outcomes` — outcome
  dispatch.
- `tests/test_pomban_engine.py` — 15 unit tests.
- `ROADMAP.md` Phase 4.5 — the planning context.
- [ADR-0003](0003-layered-screen-architecture.md) — the previous
  extraction step that the facade builds on.

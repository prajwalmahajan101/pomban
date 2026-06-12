# ADR 0005 — Project → sprint → task hierarchy and inline assignment syntax

Status: Accepted (2026-06-12)

## Context

pomban shipped v0.1.0 as a Pomodoro timer with kanban — tasks were
loose rows, optionally tagged. v0.2.0 reframes the app as a
personal productivity platform: tasks live inside sprints, sprints
live inside projects, and every focus session attaches up the
chain. That reframing forced two questions:

1. **What's the persistence shape?** Tasks need to belong to a
   project, optionally to a sprint within that project, and the
   model should make "cross-project sprints" unrepresentable.
2. **How do users assign without a modal per task?** pomban's
   value proposition is keyboard-driven flow — a friction-free
   "type the title, hit enter" loop. Forcing a per-task modal to
   pick a project would break that.

The alternative considered for (1) was a tag-based association
(`#proj/foo`, `#sprint/bar`) with no FK. Rejected because the
sprint completion / archive lifecycle then has no schema-level
guarantee that tasks travel with their sprint, and stats /
exports would have to grep tag strings.

The alternative for (2) was a "default project" config knob plus
explicit reassignment via the edit modal. Rejected because daily
work usually spans projects within minutes — a single default
just shifts the friction, it doesn't remove it.

## Decision

**Schema v10 enforces the hierarchy at the FK layer.** `tasks`
carries `project_id` (NOT NULL after migration, with an "Inbox"
project seeded for legacy rows) and `sprint_id` (NULLable).
`sprints` carries `project_id` (NOT NULL). The "one active sprint
per project" rule is enforced in `core/db.py` write paths, not as
a partial-unique index — partial uniqueness across SQLite versions
is uneven and the code-level check is easier to test.

**Inline assignment is the keyboard path.** Task input parses
four tokens:

| Token | Meaning |
|---|---|
| `@project` | Assign to project; auto-create if new. First `@` wins. |
| `!sprint` | Assign to sprint within the active project; auto-create as a 14-day shell if new. First `!` wins. |
| `#tag` | Add a tag. Multiple allowed. |
| `~N` | Estimated pomodoros. First `~N` wins. |

Parsing lives in `core/task_input.py`; the edit modal exposes
the same fields explicitly so mouse / form-driven users aren't
locked out.

`FirstRunModal` seeds the user's first project on empty-DB launch
so the hierarchy is never empty.

## Consequences

- **Cross-project sprints are unrepresentable** — every sprint
  has one project FK, and `!sprint` resolves within the *active*
  project. Stats and exports can group by project → sprint → task
  without dedup gymnastics.
- **Inbox project is always present** — legacy task rows that
  predate the migration, plus tasks created before the user picks
  a project, land in Inbox. The Inbox project cannot be deleted.
- **Filter state grows** — every screen now reads
  `core.filter_state.FilterState` (project + sprint), and the
  context header surfaces both. New screens added after this
  ADR must consult the filter state in their `refresh_view()`.
- **Plugin authors** get a richer model — sessions joined to
  tasks joined to sprints joined to projects — at the cost of
  needing to honour the FK chain on writes.

## Usage

- **Adding a new "scope"** (e.g. quarterly OKRs above project):
  add the new table with a project FK below it, not above. The
  rule is: planning scopes nest downward from project — never
  sideways.
- **Adding a new inline token**: extend `core/task_input.py` and
  the user-guide table. Keep "first wins" semantics so the parser
  is deterministic on weird input.
- **Adding a new screen**: subclass `AppScreen`
  (see [ADR-0003](0003-layered-screen-architecture.md)), read
  `app.filter_state` for the active project / sprint, and
  surface the active scope in the context header chip.

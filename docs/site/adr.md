# Architecture decision records

Each architectural decision in this project came with a short ADR
capturing the context, alternatives considered, and the consequences.
Files live at
[`docs/adr/`](https://github.com/prajwalmahajan101/pomban/tree/main/docs/adr)
in the repo.

| # | Decision |
|---|---|
| [0001](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0001-stack-choice.md) | Stack choice — Textual + SQLite + XDG paths |
| [0002](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0002-single-sqlite-connection.md) | Single SQLite connection — no writer thread |
| [0003](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0003-layered-screen-architecture.md) | Layered screen architecture and the `AppScreen` contract |
| [0004](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0004-working-hours-quiet.md) | Working-hours quiet — config-driven notification suppression |
| [0005](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0005-project-sprint-task-hierarchy.md) | Project → sprint → task hierarchy and inline assignment syntax |
| [0006](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0006-pomban-engine-facade.md) | `PombanEngine` facade for timer + session orchestration |

## When to write a new one

Add `docs/adr/NNNN-<slug>.md` whenever you change:

- A persistence schema (any `core/db.py` migration).
- A protocol between layers (`core/` ↔ `screens/`).
- A dependency choice (adding / removing a runtime dep).
- A user-visible behaviour that's not obvious from the code.

Pattern is **Context · Decision · Consequences · Usage**. The Usage
section is for the next contributor: how to extend this decision,
what patterns to follow, what to avoid.

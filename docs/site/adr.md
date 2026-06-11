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

## When to write a new one

Add `docs/adr/NNNN-<slug>.md` whenever you change:

- A persistence schema (any `core/db.py` migration).
- A protocol between layers (`core/` ↔ `screens/`).
- A dependency choice (adding / removing a runtime dep).
- A user-visible behaviour that's not obvious from the code.

Pattern is **Context · Decision · Consequences · Usage**. The Usage
section is for the next contributor: how to extend this decision,
what patterns to follow, what to avoid.

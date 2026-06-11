# Pomodoro Dashboard TUI

[![test](https://github.com/prajwalmahajan101/pomban/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/prajwalmahajan101/pomban/actions/workflows/test.yml)

A keyboard-driven Pomodoro timer with Kanban board, stats, themes, hooks, and plugins. Built with [Textual](https://textual.textualize.io/).

```
 ┌─ Timer ─────────────────────────┐  ┌─ Tasks ──────────┐
 │                                 │  │ [~] Write report │
 │            FOCUS                │  │ [ ] Fix bug      │
 │                                 │  │ [ ] Email Dana   │
 │           24:58                 │  │                  │
 │                                 │  │                  │
 │          ●●○○  ▶ running        │  │                  │
 │       on: Write report          │  │                  │
 └─────────────────────────────────┘  └──────────────────┘
  s start/pause   r reset   S skip   1/2/3/4 views   ? help   q quit
```

## Install

```bash
git clone <this-repo> pomodoro && cd pomodoro
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
pomodoro                    # launch the TUI
pomodoro export --since 7d  # markdown review to stdout
```

## Documentation

| Doc | When to read it |
|---|---|
| [docs/user-guide.md](docs/user-guide.md) | Start here. End-to-end walkthrough of every feature. |
| [docs/keybindings.md](docs/keybindings.md) | Complete keybinding reference (printable cheat sheet). |
| [docs/configuration.md](docs/configuration.md) | Every `config.toml` option, hooks, presets, themes. |
| [docs/development.md](docs/development.md) | Architecture, schema, plugin API, testing, contributing. |
| [examples/plugin-print-events/](examples/plugin-print-events/) | Minimal plugin you can copy as a template. |

## Highlights

- **One-task-at-a-time focus** with a session-end modal that asks "did you actually finish?"
- **Kanban board** (`2`) — three columns, vim-style navigation, drag-free card movement.
- **Stats screen** (`3`) — 7- and 30-day heatmap, top tasks, interruption stats.
- **History screen** (`4`) — every session, paged, with planned vs actual durations.
- **Presets** — switch between classic 25/5, deep-work 50/10, sprint 15/3, etc. with `p`.
- **Themes** — nord, gruvbox, dracula, catppuccin, tokyo-night. Cycle with `t`, persisted to config.
- **Hooks** — run any shell command on focus/break start/end (do-not-disturb scripts, etc.).
- **In-process plugins** — Python entry points; errors are sandboxed, never crash the app.
- **Resume on restart** — quit mid-session, get a "resume? y/n" prompt next launch.
- **Local-first** — single SQLite file, no accounts, optional git-sync for portability.

## Test

```bash
pytest -q          # 68 tests across engine, DB, screens, modals, plugins
```

## License

MIT — see [LICENSE](LICENSE).

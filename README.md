# pomban

[![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![test](https://github.com/prajwalmahajan101/pomban/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/prajwalmahajan101/pomban/actions/workflows/test.yml)

> A keyboard-driven Pomodoro TUI with kanban, projects, sprints, and
> local-first SQLite persistence. Built with
> [Textual](https://textual.textualize.io/).

![pomban dashboard](docs/screenshots/dashboard.svg)

```bash
pipx install pomban && pomban
```

## Why pomban?

- **vs CLI timers** — full task surface (kanban + projects + sprints +
  history + stats), not just a countdown.
- **vs phone Pomodoro apps** — keyboard-driven, distraction-free,
  themed, runs in the terminal you already have open. Your library
  is a single SQLite file, syncable via your own git remote.
- **vs a wall clock + sticky notes** — every session is logged. Per
  task, per project, per sprint, per day, per week.
- **vs a web Pomodoro app** — local-first, nothing leaves your
  machine, no account.

## Features

- **Pomodoro engine** — focus / short-break / long-break / lunch
  phases, configurable cycle length, auto-advance toggle (`Shift+T`),
  resume-on-restart prompt, lunch-window suggestion.
- **Kanban board** (`2`) — three columns, priorities, due dates
  (overdue render red), per-column WIP limits, board search (`/`),
  visual-mode bulk actions (`v`), card-detail screen (`i`).
- **Projects and Sprints** — full CRUD with archiving, completion
  states, and `@project` / `!sprint` inline task syntax.
- **Stats** (`3`) — daily / weekly / monthly buckets, top tasks,
  interruption counts.
- **History** (`4`) — every session with planned vs. actual duration.
- **Themes** — nord, gruvbox, dracula, catppuccin-mocha, tokyo-night.
  Cycle with `t`; persisted to `config.toml`.
- **Hooks and plugins** — `[hooks].on_focus_start` shell commands +
  Python entry-point plugins; the first-party `git_sync` plugin
  commits your library on exit so it can sync across devices.
- **Local-first** — single SQLite file at
  `~/.local/share/pomban/pomban.db`. Nothing leaves your machine.

## Install

The PyPI package will be named **`pomban`** (planned for the 0.1.0
release — see [ROADMAP.md](./ROADMAP.md)). Until then, install from
source.

### Recommended: pipx or uv tool

For end-user CLI tools, prefer an isolated install over `pip install`
into your system Python — that path is blocked on most modern Linux
distros by [PEP 668](https://peps.python.org/pep-0668/) anyway.

```bash
# pipx (most popular)
pipx install git+https://github.com/prajwalmahajan101/pomban

# OR uv tool (faster, same idea)
uv tool install git+https://github.com/prajwalmahajan101/pomban
```

Either gives you a global `pomban` command with its dependencies
sandboxed in their own venv.

### pip (inside a venv)

```bash
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows
pip install git+https://github.com/prajwalmahajan101/pomban
```

### From source

```bash
git clone https://github.com/prajwalmahajan101/pomban
cd pomban
pip install -e ".[dev]"
```

### Requirements

- Python ≥ 3.11
- A terminal with at least 80 columns. 100+ recommended.
- Linux desktop notifications need `notify-send`; sound needs
  `paplay`, `aplay`, or `ffplay` on `$PATH`. Both degrade silently
  if missing — the in-TUI bell still fires.

## Quick start

```bash
pomban                    # launch the TUI
```

Press `?` at any time for a context-aware help overlay. The most
common keys:

| Key | Action |
|---|---|
| `s` / `Space` | Start / pause / resume the timer |
| `r` | Reset |
| `Shift+S` / `S` | Skip to the next phase |
| `n` | Focus the "new task" input |
| `1`–`6` | Jump to Dashboard / Kanban / Stats / History / Projects / Sprints |
| `t` | Cycle theme |
| `?` | Help overlay |
| `q` | Quit (persists pending focus session) |

Full reference: [docs/site/keybindings.md](docs/site/keybindings.md).

### CLI

```bash
pomban                    # launch the TUI
pomban export --since 7d  # markdown review to stdout
pomban sprint export …    # per-sprint reports (see `--help`)
```

## Configuration

pomban reads `~/.config/pomban/config.toml` (XDG-compliant). The
file is optional — sane defaults ship. Top-level sections:

| Section | What it controls |
|---|---|
| `[timer]` | Focus / break minutes, cycle count, warning seconds, auto-advance |
| `[notifications]` | Desktop / sound / bell |
| `[ui]` | Theme |
| `[hooks]` | Shell commands on phase start / end |
| `[sync]` | The `git_sync` plugin |
| `[breaks]` | Lunch-break window |
| `[kanban]` | Per-column WIP limits |
| `[[preset]]` | One block per preset, switchable via `p` |

Full reference: [docs/site/configuration.md](docs/site/configuration.md).

### XDG paths

| Purpose | Path |
|---|---|
| Config | `$XDG_CONFIG_HOME/pomban/config.toml`, default `~/.config/pomban/config.toml` |
| Library DB | `$XDG_DATA_HOME/pomban/pomban.db`, default `~/.local/share/pomban/pomban.db` |
| Log | `$XDG_STATE_HOME/pomban/pomban.log`, default `~/.local/state/pomban/pomban.log` |

## Troubleshooting

**The bell rings but no desktop notification appears.**
On Linux, install a notification daemon and `notify-send` (`libnotify`
on most distros). On macOS, install `terminal-notifier`. The bell
itself always fires; the desktop notification is best-effort.

**`git_sync` complained "not a git repo".**
Run `git init && git remote add origin <your-url>` inside
`~/.local/share/pomban/`. pomban commits on exit but never
pushes — set up a `post-commit` hook or cron if you want auto-push.

**A focus session crashed mid-pomodoro; will I lose it?**
No. The session and remaining seconds are persisted at every phase
transition. On next launch you'll get a resume prompt.

**SQLite says "database is locked".**
pomban uses a single SQLite connection by design (see
[ADR-0002](docs/adr/0002-single-sqlite-connection.md)). If you opened
the DB in another tool while pomban was running, close that tool.

## Development

```bash
git clone https://github.com/prajwalmahajan101/pomban
cd pomban
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install

pytest -q
ruff format --check . && ruff check src/ tests/
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full convention list,
[ROADMAP.md](./ROADMAP.md) for what's coming, and
[RELEASE_PLAN.md](./RELEASE_PLAN.md) for how releases are cut.

## Project background

pomban is a solo, phase-driven project. The phase plan and current
status are in [ROADMAP.md](./ROADMAP.md); architectural decisions are
recorded under [docs/adr/](docs/adr/); the cumulative change history
is in [CHANGELOG.md](./CHANGELOG.md). Active and resolved code-review
findings live under [`.code_review/`](.code_review/).

## License

MIT — see [LICENSE](./LICENSE).

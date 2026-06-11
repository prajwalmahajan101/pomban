# pomban

A keyboard-driven Pomodoro TUI with kanban, projects, sprints, and
local-first SQLite persistence. Built with
[Textual](https://textual.textualize.io/).

```bash
pipx install git+https://github.com/prajwalmahajan101/pomban && pomban
```

![dashboard](https://raw.githubusercontent.com/prajwalmahajan101/pomban/main/docs/screenshots/dashboard.svg)

## What you get

- Pomodoro engine with focus / short-break / long-break / lunch
  phases, presets, themes, auto-advance, resume-on-restart.
- Kanban board with priorities, due dates, WIP limits, search, and
  bulk visual-mode actions.
- Projects and sprints — full CRUD with archiving, completion states,
  and inline `@project` / `!sprint` task syntax.
- Stats and history screens — daily / weekly / monthly buckets,
  planned vs. actual durations.
- Hooks (shell commands on phase start/end) and in-process Python
  plugins.
- Local-first — single SQLite file at
  `~/.local/share/pomban/library.db`. Nothing leaves your machine.

## Why pomban?

- **vs CLI timers** — full task surface (kanban + projects + sprints
  + history + stats), not just a countdown.
- **vs phone Pomodoro apps** — keyboard-driven, distraction-free,
  themed, runs in the terminal you already have open.
- **vs a wall clock + sticky notes** — every session is logged. Per
  task, per project, per sprint, per day, per week.
- **vs a web Pomodoro app** — local-first, nothing leaves your
  machine, no account.

## Get going

- [Install](install.md) — pipx, uv tool, or pip-in-venv.
- [Quick start](quickstart.md) — first session in 30 seconds.
- [User guide](user-guide.md) — end-to-end walkthrough.
- [Key bindings](keybindings.md) — full reference.
- [Configuration](configuration.md) — every `config.toml` option.
- [Troubleshooting](troubleshooting.md) — common fixes.
- [Architecture (ADRs)](adr.md) — why the project is shaped this way.
- [Roadmap](roadmap.md) — what's next.

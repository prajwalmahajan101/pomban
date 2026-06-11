# Quick start

After [installing](install.md):

```bash
pomodoro
```

You'll land on the Dashboard with an empty task list. Press `?` at
any time for a context-aware help overlay.

## First five minutes

1. **Add a task.** Press `n`, type `Write release notes ~2 #docs`,
   Enter. The `~2` is the pomodoro estimate; `#docs` is a tag.
2. **Start a focus session.** Select the task with `j`/`k`, press
   Enter (or `s` to start without picking one).
3. **Pause if you need to.** `s` again toggles pause / resume.
4. **End early.** `r` resets (counts as incomplete); `Shift+S`
   skips to the next phase (counts as completed).
5. **Switch screens.** `2` for the kanban board, `3` for stats,
   `4` for history.

That's the whole loop. Everything below is sugar.

## Kanban in 30 seconds

Press `2`. Three columns (To Do · Doing · Done), one focused at a
time:

- `h` / `l` (or `Tab`) move between columns.
- `n` adds a card to the focused column.
- `j` / `k` move within a column.
- `Enter` / `s` starts a focus session on the focused card.
- `c` marks it done; `o` reopens a Done card.
- `e` opens the edit modal; `i` opens the full card-detail view.
- `/` searches the board by text or `#tag`.

Cards sort by priority (high first), then due date (soonest first),
then manual order.

## Useful global keys

| Key | Action |
|---|---|
| `Shift+L` / `L` | Start a lunch break (long pause) immediately |
| `Shift+T` / `T` | Toggle auto-advance (skip end-of-phase modal) |
| `p` | Open the preset picker (modal) |
| `Shift+P` / `P` | Project filter picker |
| `Shift+F` / `F` | Sprint filter picker |
| `t` | Cycle theme (persisted to `config.toml`) |
| `?` | Help overlay |
| `q` | Quit (persists pending focus session for next launch) |

Full reference: [keybindings](keybindings.md).

## Inline task syntax

When you type a new task title, recognise these tokens:

`Wire OAuth flow @client-acme !v1.0-launch ~5 #backend #urgent`

| Token | Meaning |
|---|---|
| `#tag` | Add a tag (multiple allowed) |
| `@project` | Assign to project (auto-created if new). First `@` wins. |
| `!sprint` | Assign to sprint (auto-created as a 14-day shell if new). First `!` wins. |
| `~N` | Estimated pomodoros (integer). First `~N` wins. |

## What gets persisted

Quit (`q`) commits the current state:

- Open focus session and remaining seconds → next launch shows a
  **resume? y/n** prompt.
- Completed sessions, tasks, projects, sprints, kanban positions →
  `~/.local/share/pomodoro/library.db`.
- Theme + auto-advance flag → `~/.config/pomodoro/config.toml`.

If the [`git_sync` plugin](configuration.md#sync) is on, the
library DB is also committed (never pushed) on exit.

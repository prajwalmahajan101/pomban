# Keybindings — full reference

Press `?` in-app for a quick overlay. This page is the exhaustive list.

## Global (works everywhere)

| Key | Action |
|---|---|
| `q` | Quit (persists pending focus session if one is open) |
| `?` | Toggle help overlay |
| `t` | Cycle theme; persisted to `config.toml` |
| `p` | Open preset picker (modal) |
| `1` | Switch to **Dashboard** |
| `2` | Switch to **Kanban** |
| `3` | Switch to **Stats** |
| `4` | Switch to **History** |

## Dashboard

### Timer control

| Key | Action |
|---|---|
| `s` / `Space` | Start (from idle) / pause / resume |
| `r` | Reset — ends current session as incomplete, returns to idle |
| `Shift+S` / `S` | Skip — immediately jump to next phase |

### Task list

| Key | Action |
|---|---|
| `j` / `k` | Move cursor in task list |
| `Enter` | Start focus session on the selected task |
| `n` | Focus the "new task" input |
| `d` / `x` | Delete selected task |
| `c` | Mark selected task as **done** |

## Kanban

### Navigation

| Key | Action |
|---|---|
| `h` / `l` | Move cursor left/right between columns |
| `j` / `k` | Move cursor up/down within a column |

### Moving cards across columns

Multiple aliases — use whichever your terminal doesn't intercept.

| Key | Action |
|---|---|
| `Shift+H` / `H` / `<` / `,` | Move focused card to previous column |
| `Shift+L` / `L` / `>` / `.` | Move focused card to next column |

### Reordering within a column

| Key | Action |
|---|---|
| `Shift+J` / `J` / `]` | Move focused card down |
| `Shift+K` / `K` / `[` | Move focused card up |

### Card operations

| Key | Action |
|---|---|
| `n` | Focus the new-card input; adds to the **currently focused column** |
| `Enter` / `s` | Start a focus session on focused card |
| `c` | Mark focused card as **done** (moves to Done column) |
| `d` / `x` | Delete focused card |

## Session-end modal (after focus completes with a task)

| Key | Action |
|---|---|
| `c` | **Completed** — mark task done, end session, advance to break |
| `k` | **Keep** — leave task in Doing, end session, advance to break |
| `e` | (no-op label cue) — shows the +5/+10/+15 hint |
| `5` | Extend current focus by **+5 minutes** |
| `0` | Extend current focus by **+10 minutes** |
| `+` | Extend current focus by **+15 minutes** |
| `Esc` | Dismiss without choosing — engine stays paused |

## Session-end modal (after break, or focus with no task)

| Key | Action |
|---|---|
| `Enter` | Start the next phase |
| `e` then `5`/`0`/`+` | Extend break by +5/+10/+15 minutes |
| `Esc` | Dismiss |

## Resume prompt (shown on launch if a focus session was open)

| Key | Action |
|---|---|
| `y` | Resume the previous focus session at the saved time-remaining |
| `n` / `Esc` | Discard — close the session as `completed=0` |

## Help overlay

| Key | Action |
|---|---|
| any | Close the overlay |

## Why so many aliases?

Some terminals (notably Kitty) bind their own shortcuts to combinations like `Shift+H`. To keep the app usable everywhere, every shift-modified key has at least one symbol alias (`<`, `,`, `]`, `[`, etc.). If a binding doesn't fire, try a different alias from the same row.

To debug what your terminal sends, use Kitty's `kitty +kitten show_key` (or your terminal's equivalent).

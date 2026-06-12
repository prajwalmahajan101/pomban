# Keybindings — full reference

Press `?` in-app for a quick overlay. The overlay is generated from the **live**
bindings of the active screen and focused panel, so it always matches reality
(and changes with the focused panel). This page is the exhaustive list.

## Panels & focus (btop / lazygit style)

Each screen is split into **panels**. The focused panel is highlighted with an
accent border, and its keymap is the one shown in the footer — so the available
keys change depending on which panel is active.

| Key | Action |
|---|---|
| `Tab` / `Shift+Tab` | Cycle focus between panels (Dashboard panes; Kanban columns) |
| highlighted letter | Each panel title shows one highlighted letter — press it to focus that panel (btop-style). Dashboard: **T·i·mer** = `i`, **T·a·sks** = `a` |
| `1`–`7` | Jump directly to a section (Dashboard / Kanban / Stats / History / Projects / Sprints / Today) |

## Global (works everywhere)

| Key | Action |
|---|---|
| `q` | Quit (persists pending focus session if one is open) |
| `?` | Toggle help overlay |
| `t` | Cycle theme; persisted to `config.toml` |
| `Shift+T` / `T` | Toggle **auto-advance** (skip end-of-phase modal); persisted to `config.toml` |
| `p` | Open preset picker (modal) |
| `Shift+P` / `P` | Open **project** filter picker (All / Inbox / each project) |
| `Shift+F` / `F` | Open **sprint** filter picker (scoped to active project) |
| `Shift+L` / `L` | Start a **lunch break** (long pause — interrupts current phase) |
| `1` | Switch to **Dashboard** |
| `2` | Switch to **Kanban** |
| `3` | Switch to **Stats** |
| `4` | Switch to **History** |
| `5` | Switch to **Projects** management screen |
| `6` | Switch to **Sprints** management screen |
| `7` | Switch to **Today** digest |
| `Shift+R` | Open the **sprint runner** overlay (current sprint, pinned) |
| `b` | Log a **blocker** against the current focus session |

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
| `e` | Edit selected task (title / tags / estimate / project / due / priority) |
| `` ` `` (backtick) | Cycle the highlighted active-task chip (multi-task focus) |

## Kanban

The three columns are panels: the active column has an accent border, and its
footer keymap reflects what's valid there (e.g. **Done** offers *Reopen* but not
*Move →* or *Focus*).

### Navigation

| Key | Action |
|---|---|
| `h` / `l` | Move between columns (also `Tab` / `Shift+Tab`) |
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
| `Enter` / `s` | Start a focus session on focused card (To Do / Doing only) |
| `c` | Mark focused card as **done** (To Do / Doing → Done) |
| `o` | **Reopen** — move a Done card back to To Do (Done column only) |
| `e` | Edit focused card (title / tags / estimate / project / **due date** / **priority**) |
| `i` | Open the **card detail** view — full notes + metadata (`e` edit · `c` done · `p` cycle priority) |
| `d` / `x` | Delete focused card |

Per-column keymap (what the footer shows):

| Column | Available |
|---|---|
| **To Do** | Focus · Move → · New · Edit · Details · Delete |
| **Doing** | Focus · Move ← · Move → · New · Edit · Details · Delete |
| **Done** | Move ← · **Reopen** · New · Edit · Details · Delete |

### Search, WIP limits & bulk actions

| Key | Action |
|---|---|
| `/` | Filter the board by text or `#tag` (on top of project/sprint filters); `Esc` clears |
| `v` | Toggle **visual select**, then `Space` to pick cards |
| `Shift+H` / `Shift+L` | (visual) bulk-move all selected cards left / right |
| `c` / `d` | (visual) bulk **complete** / **delete** the selection |
| `g` | (visual) add a **tag** to all selected cards |
| `s` / `Enter` | (visual) start a focus session on the whole selection |

Cards sort within a column by **priority** (high first), then **due date**
(soonest first), then manual order. Overdue due-dates render red. Columns can
have **WIP limits** (`[kanban] wip_todo/wip_doing/wip_done`); a column over its
limit turns red with `⚠ n/limit` and moving into it warns (but isn't blocked).

## Session-end modal (after focus completes with a task)

| Key | Action |
|---|---|
| `c` | **Completed** — mark task done, end session, advance to break |
| `k` | **Keep** — leave task in Doing, end session, advance to break |
| `l` | **Lunch** — start a long pause (only suggested inside the configured `[breaks]` window) |
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

## Projects screen (`5`)

| Key | Action |
|---|---|
| `n` | Add a new project (focuses the input) |
| `r` | Rename the focused project |
| `c` | Cycle through colors for the focused project |
| `a` | Archive / unarchive the focused project |
| `d` / `x` | Delete the focused project (tasks move to Inbox) |
| `Enter` | Apply this project as a filter and switch to Kanban |

## Sprints screen (`6`)

| Key | Action |
|---|---|
| `n` | Add a new sprint (name, optional target as last word) |
| `a` | Activate the focused sprint (deactivates any other active sprint in same project) |
| `c` | Mark sprint as **completed** |
| `x` | Mark sprint as **cancelled** |
| `d` | Delete the sprint (tasks released back to project backlog) |
| `e` | Edit pomban target |
| `g` | Edit goal |
| `Enter` | Apply this sprint as a filter and switch to Kanban |

## Stats screen (`3`) — view cycle

| Key | Action |
|---|---|
| `d` | Daily view (14 buckets) |
| `w` | Weekly view (12 buckets) |
| `m` | Monthly view (12 buckets) |

## Help overlay

The overlay is built dynamically from the active screen + focused panel's live
bindings, so it never goes stale.

| Key | Action |
|---|---|
| `Esc` / `?` / `q` / any | Close the overlay |

## Inline task syntax (used in Dashboard + Kanban inputs)

`Wire OAuth flow @client-acme !v1.0-launch ~5 #backend #urgent`

| Token | Meaning |
|---|---|
| `#tag` | Add a tag (multiple allowed) |
| `@project` | Assign to project (auto-created if new). First `@` wins. |
| `!sprint` | Assign to sprint (auto-created as a 14-day shell if new). First `!` wins. |
| `~N` | Estimated pomodoros (integer). First `~N` wins. |

## Why so many aliases?

Some terminals (notably Kitty) bind their own shortcuts to combinations like `Shift+H`. To keep the app usable everywhere, every shift-modified key has at least one symbol alias (`<`, `,`, `]`, `[`, etc.). If a binding doesn't fire, try a different alias from the same row.

To debug what your terminal sends, use Kitty's `kitty +kitten show_key` (or your terminal's equivalent).

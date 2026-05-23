# User Guide

Everything a user needs, in the order you'll meet it.

## Contents

1. [Quickstart](#quickstart)
2. [The Pomodoro cycle](#the-pomodoro-cycle)
3. [Tasks](#tasks)
4. [The session-end modal](#the-session-end-modal)
5. [Pre-end "ending soon" warning](#pre-end-ending-soon-warning)
6. [Kanban board](#kanban-board)
7. [Stats](#stats)
8. [History](#history)
9. [Presets](#presets)
10. [Themes](#themes)
11. [Notifications](#notifications)
12. [Hooks (shell commands on phase change)](#hooks)
13. [Resume on restart](#resume-on-restart)
14. [Markdown export](#markdown-export)
15. [Data locations](#data-locations)

---

## Quickstart

```bash
pomodoro
```

1. Type a task title in the input box at the bottom right; press **Enter**.
2. Press **j**/**k** to highlight the task; press **Enter** (or **s**) to start a focus session on it.
3. Work until the timer hits zero. The session-end modal pops up and asks if you completed the task.
4. Pick **c** (yes, mark done) or **k** (not yet, keep in Doing). A break starts automatically.

That's the whole loop. Everything else is polish.

---

## The Pomodoro cycle

Phases run on a strict cycle:

```
        ┌────────────────────────────────────────────┐
        │                                            │
        ▼                                            │
   ┌─────────┐    s   ┌─────────┐ timer ┌─────────┐  │
   │  IDLE   │ ─────▶ │  FOCUS  │ ────▶ │  modal  │──┘ c/k → break
   └─────────┘        │  25min  │ ends  └─────────┘
                      └─────────┘
```

After every **N** focus sessions (default N=4), the short break is replaced by a **long break** (15min by default). N is configurable.

```
focus #1 → short
focus #2 → short
focus #3 → short
focus #4 → LONG
focus #5 → short
...
```

### Phase control

| Key | What it does |
|---|---|
| `s` / `Space` | Start (from idle) / pause / resume. |
| `r` | **Reset** the timer to idle. Logs the current session as incomplete. |
| `Shift+S` or `S` | **Skip** the current phase — immediately jump to the next one. Counts toward the long-break tally. |

You only ever explicitly start **focus** sessions. Breaks come automatically (or via skip).

---

## Tasks

Tasks have one of three statuses: `todo`, `doing`, `done`. They're stored in a single SQLite table and shared between Dashboard list and Kanban board — same data, two views.

### Adding tasks

On the Dashboard or Kanban, press **n** to focus the input box. Type the title and press **Enter**.

You can include inline tags with `#`:

```
Write quarterly report #docs #urgent
```

This creates a task with title `Write quarterly report` and tags `docs,urgent`. Tag colors are deterministic — the same tag always gets the same color across cards.

### Task lifecycle

```
[ ] todo  ──[start focus]──▶  [~] doing  ──[c on modal]──▶  [x] done
   ▲                              │
   └────────[H on Kanban]─────────┘
```

- **Dashboard list** hides `done` tasks. To see them, switch to Kanban (`2`) or History (`4`).
- Starting a focus session on a `todo` task auto-moves it to `doing`.
- Marking done from the session-end modal moves it to `done`.

### Manually changing status

- **Dashboard**: `c` marks the selected task `done`. There's no Dashboard shortcut to move done → todo.
- **Kanban**: `Shift+H`/`H`/`<`/`,` and `Shift+L`/`L`/`>`/`.` move the focused card across columns *in either direction*. So to "un-complete" a task: open Kanban → navigate to Done column → press `,` (move left) to send it back to Doing.

### Reordering and deleting

| Key | Action | Where |
|---|---|---|
| `d` / `x` | Delete focused task / card | Dashboard, Kanban |
| `Shift+J`/`J`/`]` | Move card down within column | Kanban |
| `Shift+K`/`K`/`[` | Move card up within column | Kanban |

---

## The session-end modal

When a focus session reaches zero, the engine **does not auto-advance**. A modal pops up:

```
┌─────────────────────────────────────────────┐
│  🍅 Focus session complete                  │
│                                             │
│  You worked on Write report.                │
│  Did you finish it?                         │
│                                             │
│    c   Yes — mark done & take a break       │
│    k   Not yet — keep in Doing & take break │
│    e   Extend focus  (5/0/+ = +5/+10/+15)   │
└─────────────────────────────────────────────┘
```

| Key | Action |
|---|---|
| `c` | Mark task **done**, end DB session with `completed=1`, advance to break. |
| `k` | **Keep** task in Doing, end DB session with `completed=1`, advance to break. |
| `e` then `5`/`0`/`+` | **Extend** focus by +5 / +10 / +15 min. Same DB session row stays open; `planned_seconds` is bumped. |
| `Esc` | Dismiss without choosing. Engine stays paused; you can pick later. |

For break-end the modal is simpler: `Enter` to start the next focus, or `e` to extend the break.

### What "extend" does exactly

- Engine: clears `awaiting_decision`, adds N seconds to `remaining`, resumes the same phase.
- DB: bumps `sessions.planned_seconds` on the still-open row. No new session row.

So a 30-minute focus that you extended twice by 5 min shows as a single 40-minute session in History.

---

## Pre-end "ending soon" warning

30 seconds before any phase ends, the app fires **one** soft cue:

- Terminal bell
- Brief screen-flash
- In-app toast: `30s left on focus`

No desktop popup (too noisy). The warning fires **exactly once per phase** — pause/resume doesn't re-fire it.

Threshold is configurable: `warning_seconds` in `[timer]`. Set to `0` to disable.

---

## Kanban board

Press **2** to switch to Kanban.

```
┌─ To Do (3) ──┐  ┌─ Doing (1) ──┐  ┌─ Done (12) ─┐
│ [ ] Write…   │  │ [~] Refactor │  │ [x] Ship…   │
│ [ ] Email…   │  │              │  │ [x] Review  │
│ [ ] Call…    │  │              │  │ ...         │
└──────────────┘  └──────────────┘  └─────────────┘
```

### Navigation

| Key | Action |
|---|---|
| `j` / `k` | Move cursor up/down within current column |
| `h` / `l` | Move cursor left/right across columns |

### Moving cards

| Key | Action |
|---|---|
| `Shift+H` / `H` / `<` / `,` | Move card to previous column |
| `Shift+L` / `L` / `>` / `.` | Move card to next column |
| `Shift+J` / `J` / `]` | Reorder card down within column |
| `Shift+K` / `K` / `[` | Reorder card up within column |

> Multiple aliases exist for the `Shift+`-modified keys because some terminals (Kitty, especially) intercept them. If `Shift+H` doesn't fire, try `H` alone, or `<`.

### Card operations

| Key | Action |
|---|---|
| `n` | New card — adds to the **currently focused column** |
| `Enter` / `s` | Start a focus session on the focused card |
| `c` | Mark card done (moves to Done column) |
| `d` / `x` | Delete card |
| `1` | Switch to Dashboard |

Starting a focus from Kanban automatically switches you to Dashboard so the timer is visible.

---

## Stats

Press **3**. Shows:

- **Last 7 days** heatmap — focus minutes per day, encoded as unicode block density (`·░▒▓█`).
- **Last 30 days** heatmap — same encoding over a wider window.
- **Top tasks** — 5 tasks with the most focused time, summed across all sessions.
- **Summary**:
  - Sessions today + minutes today
  - Current streak (consecutive days with ≥1 completed focus session)
  - 30-day total
  - Avg interruptions per focus session

Data refreshes on screen entry.

---

## History

Press **4**. Paged table of the last 100 sessions:

| Column | What |
|---|---|
| When | `YYYY-MM-DD HH:MM` of start |
| Kind | `focus`/`short_break`/`long_break` |
| Planned | Original duration including any extends |
| Actual | Real elapsed time |
| Done | ✓ if `completed=1`, · otherwise |
| Interr. | Pause count during the session |
| Task(s) | Comma-joined task titles linked via `session_tasks` |

A session is `completed=1` when the user picked **c** or **k** on the modal (or the simpler break modal). `completed=0` means it was reset, skipped, or discarded on resume.

---

## Presets

A preset bundles `focus_minutes`, `short_break_minutes`, `long_break_minutes`, and `cycles_before_long_break`.

Press **p** to open the preset picker. Selecting one applies on **the next session** (not the currently running one). To get a preset immediately: press `r` to reset, `p` to pick, `s` to start.

Built-in suggested presets (see `docs/configuration.md` for the file format):

| Name | Focus / Short / Long | N cycles |
|---|---|---|
| classic | 25 / 5 / 15 | 4 |
| deep-work | 50 / 10 / 30 | 3 |
| sprint | 15 / 3 / 10 | 4 |
| ultra-deep | 90 / 15 / 30 | 2 |
| micro | 5 / 2 / 5 | 4 |
| reading | 45 / 10 / 20 | 3 |

---

## Themes

Press **t** to cycle themes:

`nord` → `gruvbox` → `dracula` → `catppuccin-mocha` → `tokyo-night` → `textual-dark` → `textual-light` → `nord` ...

The active theme is written to `config.toml` (`ui.theme`) so it persists across restarts.

---

## Notifications

When a phase ends, up to three channels fire (each independently togglable in config):

1. **Desktop notification** via `notify-send` (Linux).
2. **Sound** via `paplay` / `aplay` / `ffplay` — first one available. Default sound is `/usr/share/sounds/freedesktop/stereo/complete.oga`.
3. **In-TUI bell + flash** — works in any terminal, no system deps.

Configurable under `[notifications]` (see `docs/configuration.md`).

---

## Hooks

Run any shell command on phase transitions. Configure under `[hooks]` in `config.toml`:

```toml
[hooks]
on_focus_start = "notify-send 'Do not disturb'"
on_focus_end   = "notify-send 'You can chat again'"
on_break_start = "spotify play \"Focus playlist\""
on_break_end   = "spotify pause"
```

Each command runs in `sh -c …` with these env vars:

| Var | Value |
|---|---|
| `POMODORO_PHASE` | `focus` / `short_break` / `long_break` |
| `POMODORO_EVENT` | `start` / `end` |
| `POMODORO_TASK_TITLE` | The active task's title (empty if no task) |

Hooks are **fire-and-forget** — they never block the UI. stdout/stderr are appended to `~/.local/state/pomodoro/hooks.log`. Failures (missing binary, non-zero exit) are silent and logged.

For more powerful in-process integration, use [plugins](development.md#plugins) instead.

---

## Resume on restart

If you quit (`q`) or crash during a focus session, the next launch shows:

```
┌─────────────────────────────────────────────┐
│  Resume previous focus session?             │
│                                             │
│    task:      Write report                  │
│    remaining: 12:34                         │
│                                             │
│    y resume — n discard (logs as incomplete)│
└─────────────────────────────────────────────┘
```

State stored in `config_kv`: `pending_session_id`, `pending_remaining_seconds`, `pending_phase`, `pending_task_id`.

- `y` → engine jumps back into the same phase with the saved `remaining`; same DB session row is reused.
- `n` → DB session closed with `completed=0`; pending state cleared.

Caveat: only the *focus* phase is currently persisted. If you quit during a break, the break is forgotten (you'll start fresh next launch).

---

## Markdown export

```bash
pomodoro export                    # last 7 days
pomodoro export --since 30d        # last 30 days
pomodoro export --since 14d > review-this-fortnight.md
```

Produces a Markdown document:

```markdown
# Pomodoro review — 2026-05-18 → 2026-05-24

- **32** focus sessions (13h 20m)
- Streak: **5** day(s)
- Avg interruptions / focus: **0.6**

## Top tasks
- Write report — 4h 10m
- Refactor auth — 3h 25m
- ...

## Daily breakdown
| Date | Minutes |
|------|---------|
| 2026-05-18 | 75 |
| 2026-05-19 | 100 |
| ...
```

---

## Data locations

| Path | Contents |
|---|---|
| `~/.local/share/pomodoro/pomodoro.db` | All tasks, sessions, interruptions, KV |
| `~/.config/pomodoro/config.toml` | User configuration |
| `~/.local/state/pomodoro/hooks.log` | stdout/stderr from shell hooks |
| `~/.local/state/pomodoro/plugins.log` | Errors from in-process plugins |

Override locations by setting `$XDG_DATA_HOME`, `$XDG_CONFIG_HOME`, `$XDG_STATE_HOME` — the app respects the XDG Base Directory spec.

To wipe and start fresh:

```bash
rm -rf ~/.local/share/pomodoro ~/.config/pomodoro ~/.local/state/pomodoro
```

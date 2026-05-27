# Configuration

All user configuration lives in a single TOML file:

```
~/.config/pomodoro/config.toml
```

The file is **optional**. If it doesn't exist, sensible defaults apply. If it's malformed (invalid TOML), defaults apply silently — the app never crashes on a bad config.

To override the location, set `$XDG_CONFIG_HOME`. The app writes back to this file when you cycle themes with `t` (so your theme choice persists).

## Full reference

```toml
# ───────────────────────────────────────────
[timer]
# Pomodoro durations and the long-break cadence.
focus_minutes            = 25
short_break_minutes      = 5
long_break_minutes       = 15
cycles_before_long_break = 4
warning_seconds          = 30    # "ending soon" cue; 0 disables

# ───────────────────────────────────────────
[notifications]
desktop        = true              # notify-send popup on phase end
sound          = true              # paplay/aplay/ffplay
bell_and_flash = true              # in-app terminal bell + screen flash
sound_file     = "/usr/share/sounds/freedesktop/stereo/complete.oga"

# ───────────────────────────────────────────
[ui]
# Theme name. Cycle in-app with `t`. Valid:
#   nord, gruvbox, dracula, catppuccin-mocha, tokyo-night,
#   textual-dark, textual-light
theme = "nord"
mouse = false                      # mouse support (rarely useful in a TUI)

# ───────────────────────────────────────────
[hooks]
# Shell commands run via `sh -c`. Each is optional.
# All run fire-and-forget. stdout/stderr land in
# ~/.local/state/pomodoro/hooks.log
#
# Env vars passed to every hook:
#   POMODORO_PHASE        — focus | short_break | long_break
#   POMODORO_EVENT        — start | end
#   POMODORO_TASK_TITLE   — title of active task, or empty
on_focus_start = "notify-send 'Do not disturb'"
on_focus_end   = "notify-send 'You can chat again'"
on_break_start = ""
on_break_end   = ""

# ───────────────────────────────────────────
[sync]
# If true, on app exit: `git add -A && git commit` inside the data dir
# (~/.local/share/pomodoro/). The directory must already be a git repo;
# pushing is up to you (cron job, post-commit hook, etc.).
enabled = false

# ───────────────────────────────────────────
[breaks]
# Lunch (LONG_PAUSE) and other long pauses. Press Shift+L any time to start
# a lunch break — interrupts the current phase and resumes after.
lunch_minutes      = 45
# If both window keys are set, the session-end modal (after a focus phase)
# adds an "[l] take lunch" button when the current time falls inside the
# window and you haven't logged a long_pause today. Empty strings disable.
lunch_window_start = ""   # e.g. "12:30"
lunch_window_end   = ""   # e.g. "13:30"

# ───────────────────────────────────────────
[music]
# Drive an external music player (e.g. cliamp) around phase transitions, and
# show an in-app control panel. If `enabled = false`, the section is a no-op.
enabled         = false
player          = "cliamp"   # binary in PATH
on_focus_start  = "play"
on_focus_end    = "pause"
on_break_start  = ""
on_break_end    = "play"
# In-app control panel (Dashboard strip)
show_panel      = true       # render the now-playing / control panel
visualizer      = false      # stream `cliamp visstream` into a sparkline
visualizer_fps  = 20
poll_seconds    = 1.0        # how often the panel re-reads `status --json`
volume_step_db  = 2.0        # +/- volume increment (dB)
# Auto-start a headless player on launch (no separate instance needed)
autostart       = true
daemon_args     = "--daemon" # args to run the player headless; "" disables
# Full-screen music view (press 7)
music_screen    = true       # register the dedicated Music section
seek_seconds    = 5          # +/- seek step (seconds) on the music screen
show_history    = true       # show "recently played" on the music screen

[kanban]
# Per-column work-in-progress limits; 0 = unlimited. A column over its limit is
# flagged red (warns on move, never hard-blocks).
wip_todo        = 0
wip_doing       = 0
wip_done        = 0

# ───────────────────────────────────────────
# Presets — repeat the [[preset]] block as many times as you want.
# Press `p` in-app to pick one. The chosen preset applies on the next session.

[[preset]]
name                     = "classic"
focus_minutes            = 25
short_break_minutes      = 5
long_break_minutes       = 15
cycles_before_long_break = 4

[[preset]]
name                     = "deep-work"
focus_minutes            = 50
short_break_minutes      = 10
long_break_minutes       = 30
cycles_before_long_break = 3
```

## Section-by-section detail

### `[timer]`

| Key | Type | Default | Notes |
|---|---|---|---|
| `focus_minutes` | int | 25 | Length of a focus session |
| `short_break_minutes` | int | 5 | |
| `long_break_minutes` | int | 15 | |
| `cycles_before_long_break` | int | 4 | Every Nth focus → long break instead of short |
| `warning_seconds` | int | 30 | Soft cue this many seconds before phase end; 0 to disable |
| `auto_advance` | bool | false | Skip the end-of-phase modal and roll straight into the next phase (classic Pomodoro flow). Toggle live with `T`. |

### `[notifications]`

| Key | Type | Default | Notes |
|---|---|---|---|
| `desktop` | bool | true | Requires `notify-send` on `$PATH` (Linux) |
| `sound` | bool | true | Uses `paplay`, `aplay`, or `ffplay` — first available |
| `bell_and_flash` | bool | true | In-TUI; always works regardless of system deps |
| `sound_file` | str | null | Falls back to `/usr/share/sounds/freedesktop/stereo/complete.oga`, then `bell.oga` |

### `[ui]`

| Key | Type | Default | Notes |
|---|---|---|---|
| `theme` | str | "nord" | Invalid value falls back to "nord" |
| `mouse` | bool | false | Reserved; mouse is not currently exposed in UI flows |

Valid themes:

- `nord`
- `gruvbox`
- `dracula`
- `catppuccin-mocha`
- `tokyo-night`
- `textual-dark`
- `textual-light`

### `[hooks]`

Each value is a shell command string, passed to `sh -c`. The command runs in a child process. The app does **not** wait for it.

| Key | Fires when |
|---|---|
| `on_focus_start` | A focus session begins (including resume + extend) |
| `on_focus_end` | A focus session completes (the moment the modal appears) |
| `on_break_start` | A short or long break begins |
| `on_break_end` | A short or long break completes |

#### Useful recipes

```toml
[hooks]
# Mute Slack at the start of focus
on_focus_start = "slack-status-update --status 'In focus' --emoji ':no_entry:'"
on_focus_end   = "slack-status-update --clear"

# Toggle DND on macOS-like setups
on_focus_start = "do-not-disturb on"
on_focus_end   = "do-not-disturb off"

# Play a focus playlist
on_focus_start = "playerctl --player=spotify play"
on_break_start = "playerctl --player=spotify pause"

# Log to a file for personal analytics
on_focus_end = "echo \"$(date -Is) finished $POMODORO_TASK_TITLE\" >> ~/focus.log"
```

If you need richer logic than a shell can express, use a [plugin](development.md#plugins) — it gets the same hooks in Python, no fork overhead.

### `[sync]`

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | bool | false | If true, run `git add -A && git commit` in the data dir on exit |

Setup:

```bash
cd ~/.local/share/pomodoro
git init
git remote add origin <your-git-url>
```

The app commits on exit but **does not push**. Set up a cron job or a `post-commit` hook to handle pushing if you want cross-machine sync.

### `[music]`

Drives an external music player around phase transitions. Each `on_*` value is a
subcommand passed to `player` (e.g. `cliamp play`). An empty value means "do nothing"
for that event. If the player binary isn't on `$PATH`, the app logs one line to
`~/.local/state/pomodoro/music.log` and carries on — it never crashes.

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | bool | false | Master switch; when false the whole section is a no-op |
| `player` | str | `"cliamp"` | Player binary; invoked as `player <subcommand>` |
| `on_focus_start` | str | `"play"` | Subcommand when a focus phase starts |
| `on_focus_end` | str | `"pause"` | Subcommand when a focus phase ends |
| `on_break_start` | str | `""` | Subcommand when a break/lunch starts |
| `on_break_end` | str | `"play"` | Subcommand when a break/lunch ends |
| `show_panel` | bool | true | Show the in-app now-playing / control panel on the Dashboard |
| `visualizer` | bool | false | Stream `cliamp visstream` (NDJSON) into a live sparkline |
| `visualizer_fps` | int | 20 | Visualizer frame rate |
| `poll_seconds` | float | 1.0 | How often the panel re-reads `status --json` |
| `volume_step_db` | float | 2.0 | Volume increment for the panel's `+`/`-` keys |
| `autostart` | bool | true | Spawn a headless player daemon on launch so no separate instance is needed |
| `daemon_args` | str | `"--daemon"` | Args to run the player headless; empty string disables auto-start |
| `music_screen` | bool | true | Register the full-screen Music section (press `7`) |
| `seek_seconds` | int | 5 | Seek step (seconds) for `[` / `]` on the music screen |
| `show_history` | bool | true | Show "recently played" (`history --json`) on the music screen |

**Auto-start.** On launch (when `enabled` and `autostart`), the app spawns
`cliamp --daemon` in the background — a headless IPC server — so the panel works
immediately without you starting cliamp in another terminal. It's idempotent: if
an instance is already running, nothing is spawned. The app only stops the daemon
**it** started (a pre-existing cliamp is left running). For a player without a
headless mode, set `daemon_args = ""`.

**In-app control panel.** When `enabled` and `show_panel`, the Dashboard shows a
now-playing strip read from `cliamp status --json`. Tab to it to focus it, then
`Space` play/pause, `n`/`p` next/prev, `+`/`-` volume, `Shift+V` toggle the
visualizer. The reads run off the UI thread, so a missing or slow player never
blocks the timer — the panel just shows "not running". The rich panel features
(`status`, `visstream`) are cliamp-specific; other players still get the global
`m` / `Shift+M` controls and the `on_*` phase subcommands.

Global keys: `m` toggles play/pause, `Shift+M` skips track. Lunch / long pauses
are treated as breaks (they fire `on_break_start` / `on_break_end`).
`python -m pomodoro --with-music` still launches cliamp side-by-side as a fallback.

**Full music section (`7`).** A dedicated screen adds a progress/seek bar
(`[`/`]`), shuffle (`z`), repeat (`x`), a saved-playlist browser (`Enter` loads),
and recently-played history — all cliamp-driven and polled off the UI thread.
Set `music_screen = false` to omit the screen entirely.

### `[kanban]`

Per-column work-in-progress (WIP) limits. `0` means unlimited. A column whose
task count exceeds its limit is highlighted red with a `⚠ n/limit` marker; moving
a card into a full column warns but is never blocked.

| Key | Type | Default | Notes |
|---|---|---|---|
| `wip_todo` | int | 0 | Max cards in **To Do** (0 = unlimited) |
| `wip_doing` | int | 0 | Max cards in **Doing** (0 = unlimited) |
| `wip_done` | int | 0 | Max cards in **Done** (0 = unlimited) |

### `[[preset]]`

Each `[[preset]]` block adds one entry to the preset picker.

| Key | Required | Default | Notes |
|---|---|---|---|
| `name` | yes | — | Display label |
| `focus_minutes` | yes | — | |
| `short_break_minutes` | no | 5 | |
| `long_break_minutes` | no | 15 | |
| `cycles_before_long_break` | no | 4 | |

Presets without `name` or `focus_minutes` are silently dropped.

## Behavior on edits

- Config is **read on app launch**. Editing while the app is running has no effect — restart.
- Cycling theme with `t` rewrites the file. Comments and ordering are **not preserved** on these writes (the file is regenerated section-by-section).
- If you want to keep custom comments / structure, put hand-edited content in a separate file and just keep `theme` managed by the app — or skip cycling and edit `ui.theme` by hand.

## Worked example: minimal personal config

```toml
[timer]
focus_minutes = 50
warning_seconds = 60

[ui]
theme = "gruvbox"

[hooks]
on_focus_start = "notify-send 🍅 'Focus' 'Lock in'"

[[preset]]
name = "deep"
focus_minutes = 50

[[preset]]
name = "sprint"
focus_minutes = 15
short_break_minutes = 3
```

Everything not listed uses defaults.

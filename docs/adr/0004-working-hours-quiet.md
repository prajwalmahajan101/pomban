# ADR 0004 — Working-hours quiet — config-driven notification suppression

Status: Accepted (2026-06-12)

## Context

pomban fires three notification channels on phase transitions:
desktop popup (`notify-send` / `terminal-notifier`), system sound
(`paplay` / `aplay` / `ffplay`), and an in-TUI bell + screen flash.
When the user runs the app on a personal machine outside their
"working hours" — late evenings, weekends, the laptop they left
running on standby — the desktop popup and sound become noise that
spills past the terminal. The bell is harmless; the popup is not.

Users wanted a way to silence the noisy channels during off-hours
without having to remember to flip a toggle per session. The fix
needs to be:

- Declarative (no per-launch UI flag).
- Hot-reloadable with the rest of `config.toml`.
- Visible to the user — if pomban is muting them, that state must
  be obvious from any screen.
- Plugin-friendly — third-party hooks that send their own
  notifications should be *able* to honour it, even if they aren't
  forced to.

A modal toggle was considered (a `Shift+Q` "quiet mode" key) but
rejected: it adds yet another piece of state to persist, and the
common case ("quiet outside 09:00–18:00 on weekdays") is
declarative, not interactive.

## Decision

**Quiet hours live in `[breaks]` as `working_hours_start` /
`working_hours_end` (`"HH:MM"` strings; empty disables).** The
gate runs in a single funnel — `notifications.within_working_hours`
— which `core/notifications.py` consults before invoking the
desktop popup or sound channel. The in-TUI bell + flash always
fire.

The context header carries a **quiet chip** whenever the current
clock time falls outside the window, so the user can see at a
glance that pomban is suppressing channels.

Wrapping at midnight is supported (e.g. `22:00`–`06:00`); equal
start/end strings mean "always quiet"; either string empty means
"never quiet" (gate disabled).

## Consequences

- One config edit covers the whole app — no per-screen plumbing.
- Plugins that emit their own notifications via the standard
  `notifications.notify(...)` helper inherit the gate for free.
  Plugins that shell out directly (e.g. their own `notify-send`
  calls in `[hooks]`) **do not** — the gate cannot reach them.
  This is a known, documented limitation: if you want hook
  notifications gated, wrap them in a shell guard or call into
  `pomban` from the hook.
- The bell + flash always fire, so the user never misses a phase
  change inside the TUI itself.
- Tests live in `tests/test_notifications.py` and cover the
  midnight-wrap, empty-string-disabled, and equal-bounds cases.

## Usage

- **Adding a new notification channel** (e.g. macOS
  `terminal-notifier` support): route the new channel through
  `notifications.notify(...)` so the gate applies automatically.
  Do not branch on `cfg.working_hours` in screen / widget code.
- **Surfacing the quiet state** in a new widget: read
  `within_working_hours(cfg)` from `core/notifications.py` rather
  than re-parsing the config strings.
- **Extending the rule** (per-day windows, calendar integration):
  keep the funnel — add the logic inside
  `within_working_hours` and keep the call site unchanged.

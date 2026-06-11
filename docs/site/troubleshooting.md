# Troubleshooting

Common fixes. If something here doesn't match what you're seeing,
open an [issue](https://github.com/prajwalmahajan101/pomban/issues).

## The bell rings but no desktop notification appears

pomban fires three things on phase change: a desktop notification,
a sound, and the in-TUI bell + screen flash. The latter always
works. The other two need OS-level tools:

- **Linux:** install `libnotify` so `notify-send` is on `$PATH`.
  Sound needs `paplay` (PulseAudio), `aplay` (ALSA), or `ffplay`
  (ffmpeg). First available wins.
- **macOS:** install `terminal-notifier` via Homebrew. Cross-platform
  support is planned — see the [roadmap](roadmap.md).
- **Windows:** desktop notifications are not wired up yet — they're
  on the Phase 5 list.

Confirm the gap with:

```bash
notify-send "test"        # Linux
paplay /usr/share/sounds/freedesktop/stereo/complete.oga
```

## "`git_sync` complained: not a git repo"

The `git_sync` plugin commits the SQLite library on exit so you can
sync across devices via your own git remote. It needs a git repo at
the data dir:

```bash
cd ~/.local/share/pomban
git init
git remote add origin <your-private-git-url>
git config user.email "you@example.com"
git config user.name "Your Name"
```

pomban **commits**, never **pushes** — set up a `post-commit` hook
or a cron job if you want auto-push.

## A focus session crashed mid-pomban; will I lose it?

No. The session row and `pending_remaining_seconds` are persisted at
every phase transition (and on `q`). On next launch you'll get a
resume prompt: `y` resumes from the saved remaining time, `n`
discards the session as `completed=0`.

## SQLite says "database is locked"

pomban uses a single SQLite connection by design (see
[ADR-0002](https://github.com/prajwalmahajan101/pomban/blob/main/docs/adr/0002-single-sqlite-connection.md)).
If you opened the DB in another tool (DB Browser, sqlite3 shell)
while pomban is running, close that tool. Don't run multiple
copies of `pomban` against the same data dir.

## The kanban board is unfamiliar — where's the cursor?

Each column is a panel. The active column has an accent border, and
its keymap is the one shown in the footer (so `c` means *complete*
on To Do/Doing, but *(no-op)* on Done). Move between columns with
`h`/`l` or `Tab`. The cursor inside a column moves with `j`/`k`.

## Help overlay shows a binding that doesn't fire

Some terminals (notably Kitty) bind their own shortcuts to
combinations like `Shift+H`. Every shift-modified key has at least
one symbol alias (`<`, `,`, `]`, `[`). If a binding doesn't fire,
check the [keybindings](keybindings.md) page for an alias.

To debug what your terminal sends:

```bash
kitty +kitten show_key                     # Kitty
infocmp $TERM | head                       # generic
```

## My theme reverted on next launch

Theme cycling (`t`) writes to `~/.config/pomban/config.toml`. If
the write failed (read-only home, missing parent dir), it goes into
`~/.local/state/pomban/pomban.log`. Check there.

## I want to see what the app is doing

Tail the structured log:

```bash
tail -F ~/.local/state/pomban/pomban.log
```

It's file-only (never stdout / stderr) so it can't corrupt the
alternate-screen TUI.

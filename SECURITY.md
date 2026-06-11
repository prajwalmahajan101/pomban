# Security Policy

## Supported versions

pomban follows semantic versioning. Security fixes land on the
latest minor; only the latest minor is supported.

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a vulnerability

Please report security issues **privately**, not in a public issue.

Use GitHub Private Vulnerability Reporting:
**https://github.com/prajwalmahajan101/pomban/security/advisories/new**

You'll get an acknowledgement within **5 business days**. Once a fix
is ready, we'll coordinate disclosure with you.

## What's in scope

pomban is a local-only TUI. It does not run a server, open a
network socket, or accept untrusted RPC. The realistic attack
surface is:

- **`config.toml` parsing** — the config loader uses stdlib `tomllib`.
  Unknown keys are filtered (see `_filter_kwargs` in `core/config.py`).
  A crash or unexpected behaviour triggered by a crafted config file
  is in scope.
- **`[hooks]` shell commands** — values from `[hooks]` are run via
  `sh -c` with `POMODORO_PHASE` / `POMODORO_TASK_TITLE` in the env.
  Task titles are user-controlled. The `git_sync` plugin passes
  repo path and commit message as `$1` / `$2` positional args
  (intentionally non-interpolated). A shell-injection finding
  outside that contract is in scope.
- **Markup in task titles / tags** — task text flows through Rich
  markup. Hostile sequences like `[/]` must not crash the board /
  timer / list renderers (see `tests/test_markup_safety.py`).
- **SQLite library tampering** — opening a maliciously crafted
  `~/.local/share/pomban/library.db`. In scope at the parser
  level; out of scope as a privilege boundary (the attacker already
  has filesystem access to your home directory).

## What's out of scope

- Anything that requires the attacker to already have shell access
  as your user.
- Vulnerabilities in upstream libraries (report those upstream); we
  bump dependencies promptly when CVEs surface.
- The terminal emulator itself.
- Operating-system-level CVEs in `sqlite3`, `paplay`, `notify-send`,
  or other tools we shell out to.

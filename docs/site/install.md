# Install

pomban is a CLI tool. Install it the same way you'd install any
modern Python CLI: into an isolated environment, not into your
system Python.

## Recommended: pipx or uv tool

```bash
# pipx (most popular)
pipx install git+https://github.com/prajwalmahajan101/pomban

# OR uv tool (faster, same idea)
uv tool install git+https://github.com/prajwalmahajan101/pomban
```

Either gives you a global `pomban` command with its dependencies
sandboxed in their own venv. PyPI distribution
(`pipx install pomban`) is planned for the 0.1.0 release — see the
[roadmap](roadmap.md).

## PEP 668 — why not bare `pip install`?

Most modern Linux distros (Debian/Ubuntu 23.04+, Fedora 38+, Arch)
ship Python with a [PEP 668](https://peps.python.org/pep-0668/)
marker that forbids `pip install` into the system interpreter.
`pipx` / `uv tool` / a venv are the supported paths. If you must
use `pip` directly, do it inside a venv.

## pip (inside a venv)

```bash
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows
pip install git+https://github.com/prajwalmahajan101/pomban
```

## From source

```bash
git clone https://github.com/prajwalmahajan101/pomban
cd pomban
pip install -e ".[dev]"
```

See [development](development.md) for the full contributor setup
(pre-commit, linters, the test gate).

## Requirements

- Python ≥ 3.11
- A terminal with at least 80 columns. 100+ recommended.
- Linux desktop notifications: `notify-send` (libnotify) on `$PATH`.
- Sound: `paplay`, `aplay`, or `ffplay` on `$PATH`. First available wins.
- Both desktop notifications and sound degrade silently if missing —
  the in-TUI bell still fires.

## Verify

```bash
pomban                  # launches the TUI; press q to quit
```

If you get `command not found`, your shell hasn't picked up the
pipx / uv tool bin directory yet. `pipx ensurepath` (or
`uv tool update-shell`) followed by a new shell fixes it.

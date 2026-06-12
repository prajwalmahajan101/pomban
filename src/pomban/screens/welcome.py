"""Startup help — full first-run walkthrough modal + per-launch tip overlay.

Two surfaces, both gated by ``[ui].show_startup_tips`` and individually
dismissible:

* :class:`WelcomeModal` — pushed on the very first launch (no
  ``welcome_seen`` KV row). A single multi-section overlay covering the
  product mental model and the main keymap so a new user has the same
  context the README gives, without leaving the TUI. Esc / Enter / Space /
  ``?`` / ``q`` dismiss; "don't show this again" is implicit (the
  ``welcome_seen`` flag is written either way so it only ever fires once).

* :class:`StartupTipModal` — pushed on every subsequent launch. One
  short rotating tip plus a footer reminding the user to set
  ``show_startup_tips = false`` in ``config.toml`` to disable. Rotates
  through ``TIPS`` using a ``tip_index`` KV row so the same tip doesn't
  show two launches in a row.

Both modals are pure read overlays; they never write anything to the user's
library DB beyond the small KV flags above.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

WELCOME_BODY = (
    "[b]Welcome to pomban[/]  "
    "[dim]· local-first personal productivity platform[/]\n"
    "\n"
    "pomban models work the way you actually do it:\n"
    "  • [b]Projects[/] own [b]sprints[/] own [b]tasks[/] own [b]focus sessions[/].\n"
    "  • One SQLite library on your machine. Nothing leaves it.\n"
    "  • Every screen is one key away from every other screen.\n"
    "\n"
    "[b]The five-second tour[/]\n"
    "\n"
    "[b]1[/] [b]Dashboard[/] — timer + task list for the active filter.\n"
    "    [b]n[/] new task · [b]s[/]/[b]Space[/] start/pause · [b]r[/] reset\n"
    "    [b]Enter[/] focus selected · [b]b[/] log blocker mid-session\n"
    "\n"
    "[b]2[/] [b]Kanban[/] — To Do · Doing · Done with WIP limits.\n"
    "    [b]h[/]/[b]l[/] cols · [b]j[/]/[b]k[/] cards · [b]Shift+H/L[/] move\n"
    "    [b]v[/] visual select · [b]/[/] search · [b]i[/] card detail\n"
    "\n"
    "[b]3[/] [b]Stats[/] · [b]4[/] [b]History[/] · [b]7[/] [b]Today[/] digest\n"
    "\n"
    "[b]5[/] [b]Projects[/] · [b]6[/] [b]Sprints[/]\n"
    "    [b]n[/] new project · [b]s[/] new-sprint modal\n"
    "\n"
    "[b]Inline task syntax[/] — type these tokens in any new-task input:\n"
    "    [b]@project[/]  [b]!sprint[/]  [b]#tag[/]  [b]~5[/] (estimate)\n"
    "\n"
    "[b]Global keys[/]\n"
    "    [b]?[/] help (context-aware per screen)\n"
    "    [b]t[/] theme · [b]p[/] preset · [b]Shift+R[/] sprint runner\n"
    "    [b]Shift+L[/] lunch · [b]Shift+T[/] auto-advance · [b]q[/] quit\n"
    "\n"
    "[dim]Press any key to start. This walkthrough only shows on first launch.\n"
    "Toggle later via `show_startup_tips` in config.toml.[/]"
)


TIPS: tuple[str, ...] = (
    "[b]Tip[/] Press [b]?[/] on any screen for a context-aware help overlay.",
    "[b]Tip[/] Inline tokens — type [b]@project[/] [b]!sprint[/] [b]#tag[/] [b]~5[/] when creating a task.",
    "[b]Tip[/] [b]Shift+R[/] opens the sprint runner overlay — the active sprint goal stays pinned wherever you go.",
    "[b]Tip[/] On Kanban, [b]v[/] enters visual mode; [b]Space[/] picks cards then [b]Shift+H/L[/] bulk-moves.",
    "[b]Tip[/] [b]b[/] during a focus session logs a one-line blocker without breaking the timer.",
    "[b]Tip[/] [b]7[/] opens the Today digest — sessions, top tasks, interruptions, all in one screenful.",
    "[b]Tip[/] [b]pomban export --format markdown --since 7d[/] writes a weekly review to stdout.",
    "[b]Tip[/] Set [b][breaks].working_hours_start[/] / [b]_end[/] in config to silence desktop popups off-hours.",
    "[b]Tip[/] [b]p[/] cycles presets (classic 25/5, deep-work 50/10, sprint 15/3) without leaving the dashboard.",
    "[b]Tip[/] [b]i[/] on a kanban card opens the full card-detail view with notes and metadata.",
    "[b]Tip[/] Pressing [b]Esc[/] in a search closes it and brings focus back to the board.",
    "[b]Tip[/] Disable these tips by setting [b][ui].show_startup_tips = false[/] in your config.toml.",
)


class WelcomeModal(ModalScreen[None]):
    DEFAULT_CSS = """
    WelcomeModal { align: center middle; }
    WelcomeModal > Center > VerticalScroll {
        width: 78; max-height: 90%;
        background: $surface;
        border: round $accent;
        padding: 1 2;
    }
    """
    BINDINGS = [
        Binding("escape,enter,space,q,question_mark", "dismiss", "Continue"),
    ]

    def compose(self) -> ComposeResult:
        with Center(), VerticalScroll():
            yield Static(WELCOME_BODY)

    def on_key(self) -> None:
        # Any key dismisses; mirror the help-modal convention.
        self.dismiss()


class StartupTipModal(ModalScreen[None]):
    DEFAULT_CSS = """
    StartupTipModal { align: center middle; }
    StartupTipModal > Center {
        width: 70; height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    """
    BINDINGS = [Binding("escape,enter,space,q", "dismiss", "Dismiss")]

    def __init__(self, tip: str) -> None:
        super().__init__()
        self._tip = tip

    def compose(self) -> ComposeResult:
        body = (
            f"{self._tip}\n"
            "\n"
            "[dim]Press any key. Disable tips: set "
            "[b][ui].show_startup_tips = false[/] in config.toml.[/]"
        )
        with Center():
            yield Static(body)

    def on_key(self) -> None:
        self.dismiss()


def pick_next_tip(seen_index: int) -> tuple[str, int]:
    """Pure helper: return (tip, next_index) so a caller can persist the index.

    Wraps around. Exposed at module level so tests don't need to fire up
    Textual just to check rotation logic.
    """
    if not TIPS:
        return ("", 0)
    idx = seen_index % len(TIPS)
    return (TIPS[idx], (idx + 1) % len(TIPS))

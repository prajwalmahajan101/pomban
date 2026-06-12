"""Help overlay rendered from the *live* key bindings of the active screen.

Previously this was a hand-maintained string that drifted out of sync with the
real BINDINGS (it omitted half the keys). Now ``action_help`` snapshots the
active screen's bindings (app + screen + focused widget) and passes them here,
so the overlay can never go stale and is automatically context-sensitive to the
focused panel.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center
from textual.screen import ModalScreen
from textual.widgets import Static

# Friendly display names for a few raw key identifiers.
_KEY_DISPLAY = {
    "question_mark": "?",
    "space": "space",
    "escape": "esc",
    "grave_accent": "`",
}


def _pretty_key(key: str) -> str:
    return " / ".join(_KEY_DISPLAY.get(k, k) for k in key.split(","))


class HelpScreen(ModalScreen):
    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > Center {
        width: 64;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape,?,q,space", "dismiss", "Close")]

    def __init__(
        self,
        bindings: list[tuple[str, str]] | None = None,
        intro: str | None = None,
        title: str | None = None,
    ) -> None:
        super().__init__()
        # NB: avoid names like `_bindings` / `_render` — they shadow Textual internals.
        self._help_rows = bindings or []
        self._help_intro = intro
        self._help_title = title or "Pomodoro — keybindings"

    def compose(self) -> ComposeResult:
        with Center():
            yield Static(self._help_markup())

    def _help_markup(self) -> str:
        lines = [f"[b]{self._help_title}[/]", ""]
        if self._help_intro:
            lines.append(self._help_intro)
            lines.append("")
            lines.append("[dim]" + "─" * 40 + "[/]")
            lines.append("[b]Keymap[/]")
            lines.append("")
        if self._help_rows:
            width = max(len(_pretty_key(k)) for k, _ in self._help_rows)
            for key, desc in self._help_rows:
                lines.append(f"  [b]{_pretty_key(key):<{width}}[/]  {desc}")
        else:
            lines.append("  [dim]No keybindings available.[/]")
        lines += [
            "",
            "[dim]Data stored at ~/.local/share/pomban/pomban.db[/]",
            "[dim]Press esc / ? / q to close[/]",
        ]
        return "\n".join(lines)

    def on_key(self) -> None:
        self.dismiss()

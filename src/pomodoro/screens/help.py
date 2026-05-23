from textual.app import ComposeResult
from textual.containers import Center
from textual.screen import ModalScreen
from textual.widgets import Static


HELP_TEXT = """[b]Pomodoro — keybindings[/]

  [b]s[/] / [b]space[/]     Start or pause the timer
  [b]r[/]              Reset current session
  [b]S[/]              Skip current phase
  [b]enter[/]          Start a focus session on selected task
  [b]n[/]              New task (focus input)
  [b]d[/] / [b]x[/]         Delete selected task
  [b]c[/]              Mark selected task done
  [b]j[/] / [b]k[/]         Navigate task list
  [b]?[/]              Toggle this help
  [b]q[/]              Quit

[dim]Data stored at ~/.local/share/pomodoro/pomodoro.db[/]

[dim]Press any key to close[/]"""


class HelpScreen(ModalScreen):
    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > Center {
        width: 60;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape,?,q,space", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Center():
            yield Static(HELP_TEXT)

    def on_key(self) -> None:
        self.dismiss()

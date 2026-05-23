from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


def _fmt(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    return f"{m:02d}:{s:02d}"


class ResumePrompt(ModalScreen[bool]):
    DEFAULT_CSS = """
    ResumePrompt { align: center middle; }
    ResumePrompt > Center > Vertical {
        width: 64; height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    """
    BINDINGS = [
        Binding("y", "resume", "Resume"),
        Binding("n", "discard", "Discard"),
        Binding("escape", "discard", "Discard", show=False),
    ]

    def __init__(self, task_title: str | None, remaining_seconds: int) -> None:
        super().__init__()
        self.task_title = task_title
        self.remaining_seconds = remaining_seconds

    def compose(self) -> ComposeResult:
        body = f"[b]Resume previous focus session?[/]\n\n"
        if self.task_title:
            body += f"  task: [b]{self.task_title}[/]\n"
        body += f"  remaining: [b]{_fmt(self.remaining_seconds)}[/]\n\n"
        body += "  [b]y[/] resume — [b]n[/] discard (logs as incomplete)"
        with Center():
            with Vertical():
                yield Static(body)

    def action_resume(self) -> None:
        self.dismiss(True)

    def action_discard(self) -> None:
        self.dismiss(False)

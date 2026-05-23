from __future__ import annotations

from textual.widget import Widget
from textual.widgets import Static

from pomodoro.core.models import Task

TAG_PALETTE = ["red", "green", "yellow", "blue", "magenta", "cyan", "bright_red", "bright_blue"]
STATUS_MARK = {"todo": "[ ]", "doing": "[~]", "done": "[x]"}


def tag_color(tag: str) -> str:
    return TAG_PALETTE[hash(tag) % len(TAG_PALETTE)]


def render_chips(tags: str) -> str:
    if not tags:
        return ""
    chips = []
    for raw in tags.split(","):
        t = raw.strip()
        if not t:
            continue
        chips.append(f"[{tag_color(t)}]#{t}[/]")
    return " ".join(chips)


class TaskCard(Static):
    DEFAULT_CSS = """
    TaskCard {
        border: round $primary-darken-2;
        padding: 0 1;
        margin: 0 0 1 0;
        height: auto;
    }
    TaskCard.-focused {
        border: round $accent;
        background: $boost;
    }
    """

    def __init__(self, task: Task) -> None:
        super().__init__()
        self.task_data = task
        self.update_render()

    def update_render(self) -> None:
        t = self.task_data
        mark = STATUS_MARK[t.status]
        line1 = f"{mark} [b]{t.title}[/]"
        chips = render_chips(t.tags)
        est = f" [dim]🍅×{t.estimated_pomodoros}[/]" if t.estimated_pomodoros else ""
        body = f"{line1}{est}"
        if chips:
            body += f"\n  {chips}"
        self.update(body)

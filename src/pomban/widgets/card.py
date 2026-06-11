from __future__ import annotations

from datetime import date

from rich.markup import escape
from textual.widgets import Static

from pomban.core.colors import adapt, stable_index
from pomban.core.models import Task

TAG_PALETTE = ["red", "green", "yellow", "blue", "magenta", "cyan", "bright_red", "bright_blue"]
STATUS_MARK = {"todo": "[ ]", "doing": "[~]", "done": "[x]"}


def tag_color(tag: str) -> str:
    # Stable across launches (crc32, not salted hash()), adapted for NO_COLOR / 16-color.
    return adapt(TAG_PALETTE[stable_index(tag, len(TAG_PALETTE))])


def render_chips(tags: str) -> str:
    if not tags:
        return ""
    chips = []
    for raw in tags.split(","):
        t = raw.strip()
        if not t:
            continue
        c = tag_color(t)  # "" under NO_COLOR
        tag = escape(t)  # user text: don't let '[' / '[/]' break markup
        chips.append(f"[{c}]#{tag}[/]" if c else f"#{tag}")
    return " ".join(chips)


def render_project_badge(name: str | None, color: str | None) -> str:
    """Render a small colored project badge. Pass name=None for Inbox."""
    label = escape(name) if name else "Inbox"
    c = adapt(color or "white")
    # `reverse` is a style, not a color, so it survives NO_COLOR on its own.
    return f"[reverse {c}] {label} [/]" if c else f"[reverse] {label} [/]"


def render_sprint_chip(name: str | None) -> str:
    if not name:
        return ""
    c = adapt("bright_yellow")
    label = escape(name)
    return f"[{c}]▸ {label}[/]" if c else f"▸ {label}"


# priority → (glyph, color). 0 (none) renders nothing.
PRIORITY_GLYPH = {1: ("▲", "blue"), 2: ("▲", "yellow"), 3: ("▲", "red")}
PRIORITY_LABELS = {0: "", 1: "low", 2: "med", 3: "high"}


def render_priority(priority: int) -> str:
    spec = PRIORITY_GLYPH.get(priority or 0)
    if not spec:
        return ""
    glyph, color = spec
    c = adapt(color)
    return f"[{c}]{glyph}[/]" if c else glyph


def render_due(due_date: str, today: str | None = None) -> str:
    """`⏰ MM-DD`, red when overdue (vs today), dim otherwise. '' when no date."""
    if not due_date:
        return ""
    today = today or date.today().isoformat()
    overdue = due_date < today  # our own ISO 'YYYY-MM-DD'; lexicographic == chronological
    label = escape(due_date[5:] if len(due_date) >= 5 else due_date)  # MM-DD
    if overdue:
        c = adapt("red")
        return f"[{c}]⏰ {label}[/]" if c else f"(!) {label}"
    return f"[dim]⏰ {label}[/]" if not _no_color() else f"~ {label}"


def _no_color() -> bool:
    # local import keeps the module's import surface unchanged
    from pomban.core.colors import no_color

    return no_color()


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
    TaskCard.-selected {
        border-left: thick $accent;
    }
    """

    def __init__(
        self,
        task: Task,
        project_name: str | None = None,
        project_color: str | None = None,
        sprint_name: str | None = None,
        actual_pomodoros: int = 0,
    ) -> None:
        super().__init__()
        self.task_data = task
        self.project_name = project_name
        self.project_color = project_color
        self.sprint_name = sprint_name
        self.actual_pomodoros = actual_pomodoros
        self.update_render()

    def update_render(self) -> None:
        t = self.task_data
        mark = STATUS_MARK[t.status]
        badge = render_project_badge(self.project_name, self.project_color)
        prio = render_priority(t.priority)
        prefix = f"{prio} " if prio else ""
        line1 = f"{prefix}{badge} {mark} [b]{escape(t.title)}[/]"
        chips = render_chips(t.tags)
        # Estimate display: 🍅 actual/estimated when estimated > 0, plain 🍅×N otherwise
        if t.estimated_pomodoros:
            actual = self.actual_pomodoros
            est = t.estimated_pomodoros
            color = "red" if actual > est else "dim"
            est_str = f" [{color}]🍅 {actual}/{est}[/]"
        else:
            est_str = ""
        notes_glyph = " [dim]📝[/]" if (t.notes or "").strip() else ""
        due = render_due(t.due_date)
        due_str = f" {due}" if due else ""
        sprint = render_sprint_chip(self.sprint_name)
        body = f"{line1}{est_str}{due_str}{notes_glyph}"
        extras = []
        if chips:
            extras.append(chips)
        if sprint:
            extras.append(sprint)
        if extras:
            body += "\n  " + "  ".join(extras)
        self.update(body)

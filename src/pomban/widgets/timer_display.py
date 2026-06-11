from __future__ import annotations

from rich.markup import escape
from textual.reactive import reactive
from textual.widgets import Static

from pomban.core.timer_engine import Phase

PHASE_LABEL = {
    Phase.IDLE: "Idle — press [b]s[/b] to start",
    Phase.FOCUS: "FOCUS",
    Phase.SHORT_BREAK: "Short break",
    Phase.LONG_BREAK: "Long break",
}

PHASE_COLOR = {
    Phase.IDLE: "dim",
    Phase.FOCUS: "bold red",
    Phase.SHORT_BREAK: "bold green",
    Phase.LONG_BREAK: "bold cyan",
}


def _fmt(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    return f"{m:02d}:{s:02d}"


class TimerDisplay(Static):
    remaining: reactive[int] = reactive(0)
    phase: reactive[Phase] = reactive(Phase.IDLE)
    running: reactive[bool] = reactive(False)
    cycles: reactive[int] = reactive(0)
    active_task: reactive[str] = reactive("")
    active_tasks: reactive[list[str]] = reactive(list)
    active_index: reactive[int] = reactive(0)

    DEFAULT_CSS = """
    TimerDisplay {
        content-align: center middle;
        height: 100%;
        padding: 1 2;
    }
    """

    def render(self) -> str:
        label = PHASE_LABEL[self.phase]
        color = PHASE_COLOR[self.phase]
        time_str = _fmt(self.remaining) if self.phase != Phase.IDLE else "--:--"
        cycles_in_round = self.cycles % 4
        dots = "".join("●" if i < cycles_in_round else "○" for i in range(4))
        state = "▶ running" if self.running else ("⏸ paused" if self.phase != Phase.IDLE else "")
        if len(self.active_tasks) > 1:
            chips = []
            for i, name in enumerate(self.active_tasks):
                nm = escape(name)
                chips.append(f"[reverse] {nm} [/]" if i == self.active_index else f"[dim] {nm} [/]")
            task_line = "[dim]on:[/dim] " + " · ".join(chips) + "  [dim](Tab)[/]"
        else:
            task_line = (
                f"[dim]on:[/dim] [b]{escape(self.active_task)}[/b]" if self.active_task else ""
            )
        return (
            f"[{color}]{label}[/]\n\n[bold]{time_str}[/]\n\n{dots}   [dim]{state}[/]\n{task_line}"
        )

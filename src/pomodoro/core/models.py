from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TaskStatus = Literal["todo", "doing", "done"]
SessionKind = Literal["focus", "short_break", "long_break"]


@dataclass
class Task:
    id: int
    title: str
    status: TaskStatus = "todo"
    tags: str = ""
    estimated_pomodoros: int = 0
    position: int = 0


@dataclass
class Session:
    id: int
    kind: SessionKind
    started_at: str
    ended_at: str | None
    planned_seconds: int
    actual_seconds: int
    completed: bool
    interruption_count: int = 0

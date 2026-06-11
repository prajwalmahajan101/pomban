from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TaskStatus = Literal["todo", "doing", "done"]
SessionKind = Literal["focus", "short_break", "long_break", "long_pause"]
SprintStatus = Literal["planned", "active", "completed", "cancelled"]


@dataclass
class Task:
    id: int
    title: str
    status: TaskStatus = "todo"
    tags: str = ""
    estimated_pomodoros: int = 0
    position: int = 0
    project_id: int | None = None
    sprint_id: int | None = None
    notes: str = ""
    due_date: str = ""  # ISO 'YYYY-MM-DD' or '' (none)
    priority: int = 0  # 0=none, 1=low, 2=med, 3=high


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


@dataclass
class Project:
    id: int
    name: str
    color: str = "cyan"
    archived: bool = False


@dataclass
class Sprint:
    id: int
    project_id: int | None
    name: str
    goal: str = ""
    start_date: str = ""
    end_date: str = ""
    pomodoro_target: int = 0
    status: SprintStatus = "planned"
    retrospective: str = ""

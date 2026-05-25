"""Project filter value object.

Replaces the old magic encoding where the active project filter was an
``int | None`` with ``None`` meaning "All", ``-2`` meaning "Inbox", and any
other int meaning a specific project. That sentinel leaked into the app and
five screens; this type makes the three states explicit and owns the
translation to the DB filter and to/from persisted config-kv strings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Mode = Literal["all", "inbox", "project"]


@dataclass(frozen=True)
class ProjectFilter:
    mode: Mode = "all"
    project_id: int | None = None

    # ---- constructors ----
    @classmethod
    def all(cls) -> "ProjectFilter":
        return cls("all", None)

    @classmethod
    def inbox(cls) -> "ProjectFilter":
        return cls("inbox", None)

    @classmethod
    def project(cls, project_id: int) -> "ProjectFilter":
        return cls("project", int(project_id))

    # ---- predicates ----
    @property
    def is_all(self) -> bool:
        return self.mode == "all"

    @property
    def is_inbox(self) -> bool:
        return self.mode == "inbox"

    @property
    def is_project(self) -> bool:
        return self.mode == "project"

    @property
    def scoped_project_id(self) -> int | None:
        """The concrete project id when a real project is selected, else None.

        Used by screens that scope analytics to a project (stats, history,
        sprints) — Inbox and All both scope to None there.
        """
        return self.project_id if self.mode == "project" else None

    # ---- DB boundary ----
    def for_db(self):
        """Translate to the value db.list_tasks expects as ``project_filter``.

        ``_NO`` (no filter) for All, ``None`` for Inbox (project_id IS NULL),
        and the int id for a specific project.
        """
        from pomodoro.core.db import _NO
        if self.mode == "all":
            return _NO
        if self.mode == "inbox":
            return None
        return self.project_id

    # ---- persistence ----
    def to_kv(self) -> str | None:
        """Encode for config_kv. None means "don't store" (absence == All)."""
        if self.mode == "all":
            return None
        if self.mode == "inbox":
            return "inbox"
        return str(self.project_id)

    @classmethod
    def from_kv(cls, value: str | None) -> "ProjectFilter":
        """Decode a persisted value. Tolerates the legacy ``-2`` = Inbox code."""
        if not value:
            return cls.all()
        if value in ("inbox", "-2"):
            return cls.inbox()
        try:
            return cls.project(int(value))
        except ValueError:
            return cls.all()

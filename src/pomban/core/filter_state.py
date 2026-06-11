"""Project + sprint filter state, with its own config_kv persistence.

Consolidates what ``PomodoroApp`` used to hold as loose attributes plus a cluster
of methods: the active :class:`ProjectFilter`, the active sprint id, their
persistence, and the project label/color lookups. UI-free — the app wraps the
mutators with a screen refresh and keeps thin delegating accessors so screens and
tests still use ``app.project_filter`` / ``app.active_sprint_id`` unchanged.
"""

from __future__ import annotations

from pomban.core.filters import ProjectFilter


class FilterState:
    PROJECT_KEY = "ui.active_project"
    SPRINT_KEY = "ui.active_sprint"

    def __init__(self, db) -> None:
        self.db = db
        self.project: ProjectFilter = ProjectFilter.from_kv(db.kv_get(self.PROJECT_KEY))
        self.sprint_id: int | None = self._load_int(self.SPRINT_KEY)

    # ---- persistence ----
    def _load_int(self, key: str) -> int | None:
        val = self.db.kv_get(key)
        if not val:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    def _save(self, key: str, value) -> None:
        if value is None:
            self.db.kv_delete(key)
        else:
            self.db.kv_set(key, str(value))

    def _clear_sprint(self) -> None:
        self.sprint_id = None
        self._save(self.SPRINT_KEY, None)

    # ---- mutators ----
    def set_project(self, pf: ProjectFilter) -> None:
        self.project = pf
        # Switching to All/Inbox, or to a different project, may invalidate the
        # active sprint (sprints are scoped to a project).
        scope_pid = pf.scoped_project_id
        if scope_pid is None:
            if self.sprint_id is not None:
                self._clear_sprint()
        elif self.sprint_id is not None:
            try:
                sp = self.db.get_sprint(self.sprint_id)
                if sp.project_id != scope_pid:
                    self._clear_sprint()
            except Exception:
                self._clear_sprint()
        self._save(self.PROJECT_KEY, pf.to_kv())

    def set_sprint(self, sprint_id: int | None) -> None:
        self.sprint_id = sprint_id
        self._save(self.SPRINT_KEY, sprint_id)

    # ---- queries ----
    def for_db(self):
        return self.project.for_db()

    def project_label(self) -> str | None:
        pf = self.project
        if pf.is_all:
            return None
        if pf.is_inbox:
            return "Inbox"
        try:
            return self.db.get_project(pf.project_id).name
        except Exception:
            return None

    def project_color(self) -> str:
        if not self.project.is_project:
            return "white"
        try:
            return self.db.get_project(self.project.project_id).color
        except Exception:
            return "white"

"""Pure Pomodoro timer state machine. No UI, no I/O — testable with a fake clock."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Phase(str, Enum):
    IDLE = "idle"
    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


class Event(str, Enum):
    PHASE_COMPLETED = "phase_completed"
    PHASE_STARTED = "phase_started"
    PHASE_ENDING_SOON = "phase_ending_soon"


@dataclass(frozen=True)
class Settings:
    focus_seconds: int = 25 * 60
    short_break_seconds: int = 5 * 60
    long_break_seconds: int = 15 * 60
    cycles_before_long_break: int = 4
    warning_seconds: int = 30


@dataclass
class TimerEngine:
    settings: Settings = field(default_factory=Settings)
    phase: Phase = Phase.IDLE
    remaining: int = 0
    running: bool = False
    completed_focus_cycles: int = 0
    awaiting_decision: bool = False
    _last_tick: float | None = None
    _carry: float = 0.0
    _warning_fired: bool = False

    def start(self, now: float) -> list[Event]:
        if self.phase == Phase.IDLE:
            return self._enter(Phase.FOCUS, now)
        if self.awaiting_decision:
            # Treat start-after-completion as confirm + advance.
            return self.confirm_advance(now)
        if not self.running:
            self.running = True
            self._last_tick = now
            self._carry = 0.0
        return []

    def pause(self, now: float) -> None:
        if self.running:
            self._accumulate(now)
            self.running = False

    def toggle(self, now: float) -> list[Event]:
        if self.awaiting_decision:
            return self.confirm_advance(now)
        if self.running:
            self.pause(now)
            return []
        return self.start(now)

    def reset(self) -> None:
        self.phase = Phase.IDLE
        self.remaining = 0
        self.running = False
        self.completed_focus_cycles = 0
        self.awaiting_decision = False
        self._last_tick = None
        self._carry = 0.0
        self._warning_fired = False

    def skip(self, now: float) -> list[Event]:
        if self.phase == Phase.IDLE:
            return []
        if not self.awaiting_decision:
            events = self._complete()
        else:
            events = []
        events += self.confirm_advance(now)
        return events

    def extend(self, seconds: int, now: float) -> list[Event]:
        """Add time to current phase. If awaiting_decision, resume same phase."""
        if self.phase == Phase.IDLE or seconds <= 0:
            return []
        self.remaining += seconds
        if self.awaiting_decision:
            self.awaiting_decision = False
            self.running = True
            self._last_tick = now
            self._carry = 0.0
            self._warning_fired = self.remaining <= self.settings.warning_seconds
        return []

    def confirm_advance(self, now: float) -> list[Event]:
        """User has acknowledged phase completion — advance to next phase."""
        if not self.awaiting_decision:
            return []
        self.awaiting_decision = False
        completed_phase = self.phase
        if completed_phase == Phase.FOCUS:
            if self.completed_focus_cycles % self.settings.cycles_before_long_break == 0:
                return self._enter(Phase.LONG_BREAK, now)
            return self._enter(Phase.SHORT_BREAK, now)
        return self._enter(Phase.FOCUS, now)

    def tick(self, now: float) -> list[Event]:
        if not self.running:
            return []
        self._accumulate(now)
        events: list[Event] = []
        if (
            not self._warning_fired
            and 0 < self.remaining <= self.settings.warning_seconds
        ):
            self._warning_fired = True
            events.append(Event.PHASE_ENDING_SOON)
        if self.remaining <= 0:
            events += self._complete()
        return events

    # ---------- internals ----------
    def _complete(self) -> list[Event]:
        """Mark current phase complete; do NOT auto-advance."""
        self.running = False
        self.awaiting_decision = True
        if self.phase == Phase.FOCUS:
            self.completed_focus_cycles += 1
        return [Event.PHASE_COMPLETED]

    def _accumulate(self, now: float) -> None:
        if self._last_tick is None:
            self._last_tick = now
            return
        delta = now - self._last_tick + self._carry
        whole = int(delta)
        self._carry = delta - whole
        self._last_tick = now
        if whole > 0:
            self.remaining = max(0, self.remaining - whole)

    def _duration_for(self, phase: Phase) -> int:
        if phase == Phase.FOCUS:
            return self.settings.focus_seconds
        if phase == Phase.SHORT_BREAK:
            return self.settings.short_break_seconds
        if phase == Phase.LONG_BREAK:
            return self.settings.long_break_seconds
        return 0

    def _enter(self, phase: Phase, now: float) -> list[Event]:
        self.phase = phase
        self.remaining = self._duration_for(phase)
        self.running = True
        self.awaiting_decision = False
        self._last_tick = now
        self._carry = 0.0
        self._warning_fired = False
        return [Event.PHASE_STARTED]

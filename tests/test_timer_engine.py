from pomban.core.timer_engine import Event, Phase, Settings, TimerEngine


def make() -> TimerEngine:
    return TimerEngine(
        settings=Settings(
            focus_seconds=10,
            short_break_seconds=4,
            long_break_seconds=8,
            cycles_before_long_break=4,
            warning_seconds=2,
        )
    )


def test_starts_in_idle():
    e = make()
    assert e.phase == Phase.IDLE
    assert not e.running


def test_start_enters_focus():
    e = make()
    events = e.start(0.0)
    assert Event.PHASE_STARTED in events
    assert e.phase == Phase.FOCUS
    assert e.remaining == 10
    assert e.running


def test_tick_decrements():
    e = make()
    e.start(0.0)
    e.tick(3.0)
    assert e.remaining == 7


def test_pause_holds_remaining():
    e = make()
    e.start(0.0)
    e.tick(3.0)
    e.pause(3.0)
    e.tick(100.0)
    assert e.remaining == 7
    assert not e.running


def test_resume_after_pause():
    e = make()
    e.start(0.0)
    e.tick(3.0)
    e.pause(3.0)
    e.start(50.0)
    e.tick(52.0)
    assert e.remaining == 5


def test_phase_complete_does_not_auto_advance():
    e = make()
    e.start(0.0)
    events = e.tick(10.0)
    assert Event.PHASE_COMPLETED in events
    assert e.phase == Phase.FOCUS
    assert e.awaiting_decision
    assert not e.running
    assert e.completed_focus_cycles == 1


def test_confirm_advance_enters_short_break():
    e = make()
    e.start(0.0)
    e.tick(10.0)
    events = e.confirm_advance(10.0)
    assert Event.PHASE_STARTED in events
    assert e.phase == Phase.SHORT_BREAK
    assert e.remaining == 4
    assert not e.awaiting_decision
    assert e.running


def test_extend_resumes_focus_with_added_time():
    e = make()
    e.start(0.0)
    e.tick(10.0)
    assert e.awaiting_decision
    e.extend(60, 10.0)
    assert e.phase == Phase.FOCUS
    assert e.remaining == 60
    assert e.running
    assert not e.awaiting_decision


def test_extend_during_running_phase():
    e = make()
    e.start(0.0)
    e.tick(3.0)
    e.extend(5, 3.0)
    assert e.remaining == 12
    assert e.running


def test_ending_soon_fires_once():
    e = make()
    e.start(0.0)
    # warning at 2s, focus_seconds=10 → fires when remaining reaches 2.
    all_events: list[Event] = []
    all_events += e.tick(8.0)
    all_events += e.tick(9.0)
    fired = sum(1 for ev in all_events if ev == Event.PHASE_ENDING_SOON)
    assert fired == 1, all_events


def test_ending_soon_resets_per_phase():
    e = make()
    e.start(0.0)
    # finish focus
    e.tick(10.0)
    e.confirm_advance(10.0)
    # in short_break (4s), warning at 2s
    events = e.tick(12.0)
    assert Event.PHASE_ENDING_SOON in events


def test_long_break_after_n_cycles():
    e = make()
    now = 0.0
    e.start(now)
    for cycle in range(1, 5):
        now += 10
        e.tick(now)  # focus complete
        assert e.awaiting_decision
        e.confirm_advance(now)
        if cycle < 4:
            assert e.phase == Phase.SHORT_BREAK
            now += 4
            e.tick(now)
            e.confirm_advance(now)
            assert e.phase == Phase.FOCUS
        else:
            assert e.phase == Phase.LONG_BREAK


def test_skip_advances_phase():
    e = make()
    e.start(0.0)
    e.skip(1.0)
    assert e.phase == Phase.SHORT_BREAK
    assert e.remaining == 4


def test_skip_after_completion_still_advances():
    e = make()
    e.start(0.0)
    e.tick(10.0)  # awaiting_decision
    e.skip(10.0)
    assert e.phase == Phase.SHORT_BREAK
    assert not e.awaiting_decision


def test_reset_clears_state():
    e = make()
    e.start(0.0)
    e.tick(5.0)
    e.reset()
    assert e.phase == Phase.IDLE
    assert e.remaining == 0
    assert not e.running
    assert not e.awaiting_decision
    assert e.completed_focus_cycles == 0


def test_sub_second_carry():
    e = make()
    e.start(0.0)
    e.tick(0.4)
    assert e.remaining == 10
    e.tick(0.8)
    assert e.remaining == 10
    e.tick(1.1)
    assert e.remaining == 9


def test_restore_sets_phase_and_remaining():
    e = make()
    e.restore(Phase.FOCUS, remaining=120, running=True, now=0.0)
    assert e.phase == Phase.FOCUS
    assert e.remaining == 120
    assert e.running
    # Ticking decrements from the restored value, not the phase default.
    e.tick(5.0)
    assert e.remaining == 115


def test_restore_paused_has_no_last_tick():
    e = make()
    e.restore(Phase.SHORT_BREAK, remaining=3, running=False, now=2.0)
    assert not e.running
    # A tick while paused is a no-op.
    assert e.tick(10.0) == []
    assert e.remaining == 3


def test_restore_below_warning_does_not_refire_warning():
    e = make()  # warning_seconds=2
    e.restore(Phase.FOCUS, remaining=1, running=True, now=0.0)
    events = e.tick(0.1)
    assert Event.PHASE_ENDING_SOON not in events


def test_enter_long_pause():
    e = make()
    e.start(0.0)
    e.enter_long_pause(2700, now=1.0)
    assert e.phase == Phase.LONG_PAUSE
    assert e.remaining == 2700
    assert e.running
    # LONG_PAUSE completion does not consume a focus cycle.
    e.restore(Phase.LONG_PAUSE, remaining=1, running=True, now=2.0)
    events = e.tick(4.0)
    assert Event.PHASE_COMPLETED in events
    assert e.completed_focus_cycles == 0


def test_long_pause_resumes_saved_phase():
    e = make()
    e.start(0.0)  # FOCUS
    # Take lunch with SHORT_BREAK as the interrupted phase (real flow: no restore()).
    e.enter_long_pause(2, now=1.0, resume_phase=Phase.SHORT_BREAK)
    assert e.phase == Phase.LONG_PAUSE
    e.tick(5.0)  # pause elapses → completes → awaiting_decision
    e.confirm_advance(5.0)
    assert e.phase == Phase.SHORT_BREAK  # resumed the break, not FOCUS
    assert e.remaining == 4  # short_break_seconds from make()


def test_long_pause_defaults_to_focus():
    e = make()
    e.start(0.0)
    e.enter_long_pause(2, now=1.0)  # no resume_phase → FOCUS
    e.tick(5.0)
    e.confirm_advance(5.0)
    assert e.phase == Phase.FOCUS

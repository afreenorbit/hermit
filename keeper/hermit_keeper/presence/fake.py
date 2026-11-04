"""Scripted presence for tests and the simulation. Owner: Afreen.

Driven by a timeline of ``(t_seconds_from_start, present)`` against a
``FakeClock``, so a whole day of someone being at and away from their laptop
runs in milliseconds::

    clock = FakeClock()
    presence = ScriptedPresence(clock, [(0, True), (3600, False), (7200, True)])

``idle_seconds`` returns 0 while present, and otherwise the time since they
stopped being present — which is exactly what the real platform sources report,
so the state machine cannot tell the difference.
"""

from __future__ import annotations

from ..clock import FakeClock


class ScriptedPresence:
    """Args:
    clock: the same ``FakeClock`` the keepers run on.
    timeline: ``(t_seconds, present)`` pairs, relative to the clock's time
        when this object was built. Order does not matter; it is sorted.
        A timeline that does not start at ``t=0`` is treated as absent
        until its first entry.
    """

    def __init__(self, clock: FakeClock, timeline: list[tuple[float, bool]]) -> None:
        self._clock = clock
        self._start = clock.now()
        self._timeline = sorted(timeline, key=lambda entry: entry[0])

    def _elapsed(self) -> float:
        return (self._clock.now() - self._start).total_seconds()

    def present(self) -> bool:
        """Whether the human is at the laptop right now."""
        state = False
        for at, is_present in self._timeline:
            if at <= self._elapsed():
                state = is_present
            else:
                break
        return state

    async def idle_seconds(self) -> float:
        """Seconds since the last input: 0 while present."""
        now = self._elapsed()
        state = False
        changed_at = 0.0
        for at, is_present in self._timeline:
            if at <= now:
                if is_present != state:
                    changed_at = at
                state = is_present
            else:
                break
        return 0.0 if state else now - changed_at

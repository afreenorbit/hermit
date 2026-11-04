"""ScriptedPresence — a timeline of (t_seconds, present) against a FakeClock. Owner: A."""

from __future__ import annotations

from ..clock import FakeClock


class ScriptedPresence:
    def __init__(self, clock: FakeClock, timeline: list[tuple[float, bool]]) -> None:
        self._clock = clock
        self._timeline = sorted(timeline)
        self._start = clock.now()

    async def idle_seconds(self) -> float:
        raise NotImplementedError("TODO(A): Phase 1.3")

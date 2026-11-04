"""Time, injected.

Real code takes a ``Clock``; tests and the simulation pass ``FakeClock`` and
drive time forward by hand, so a two-day journey runs in two seconds.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
    async def sleep(self, seconds: float) -> None: ...


class RealClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class FakeClock:
    """Manually advanced clock. ``sleep`` resolves only when time moves."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 11, 5, 0, 0, 0, tzinfo=UTC)
        self._waiters: list[tuple[datetime, asyncio.Future[None]]] = []

    def now(self) -> datetime:
        return self._now

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        self._waiters.append((self._now + timedelta(seconds=seconds), fut))
        await fut

    async def advance(self, seconds: float) -> None:
        """Move time forward and wake everything whose deadline has passed."""
        self._now += timedelta(seconds=seconds)
        due = [(t, f) for t, f in self._waiters if t <= self._now]
        self._waiters = [(t, f) for t, f in self._waiters if t > self._now]
        for _, fut in due:
            if not fut.done():
                fut.set_result(None)
        await asyncio.sleep(0)  # let woken tasks run

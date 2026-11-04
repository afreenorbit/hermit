"""In-memory soul lease shared by many keepers in one process. Owner: Afreen.

This is the single most important fake in the project. It stands in for Switch's
exclusive leased role, which is the thing that makes "only one Hermit exists"
true. Everything else can be wired against it: the team builds before Switch is
confirmed, the simulation runs on it, and the one-soul invariant is proved
against it in ``tests/unit/test_soul_invariant.py``.

One instance is shared by every keeper in a test or sim run, the same way one
Switch server is shared by every laptop::

    lease = FakeSoulLease()
    afreen = Keeper("afreen", lease=lease)
    abhishek = Keeper("abhishek", lease=lease)

Real Switch replaces this with ``lease/gateway.py`` (or, if Phase 0 says we
cannot claim a role from outside the agent, ``agent_instructed.py`` /
``task_lock.py``). The protocol in ``lease/base.py`` does not change.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ..clock import Clock, RealClock
from .base import ClaimResult


class FakeSoulLease:
    """An exclusive lease with at most one holder.

    Args:
        clock: used only by :meth:`expire` to model a delayed expiry. Pass the
            same ``FakeClock`` the keepers use so the delay is simulated, not
            slept through.
        expiry_delay_s: how long Switch takes to notice a dead session and free
            the role. Lid-slam realism: the soul is not free the instant the lid
            closes. Phase 0 measures the real number; until then this is the
            knob the sim uses.
    """

    def __init__(self, clock: Clock | None = None, expiry_delay_s: float = 8.0) -> None:
        self._clock: Clock = clock or RealClock()
        self._expiry_delay_s = expiry_delay_s
        self._holder: str | None = None
        self._lock = asyncio.Lock()
        self._watchers: list[asyncio.Queue[str | None]] = []
        #: Every holder the lease has had, oldest first. Handy in tests.
        self.history: list[str | None] = []

    # -- reads ---------------------------------------------------------------

    async def holder(self) -> str | None:
        return self._holder

    # -- writes --------------------------------------------------------------

    async def claim(self, agent: str) -> ClaimResult:
        """Take the soul if it is free.

        Atomic: the lock is what makes two keepers racing for a freed soul
        produce exactly one winner. Claiming while you already hold it is a
        no-op that succeeds, so a retry after a dropped response is safe.
        """
        async with self._lock:
            if self._holder is None:
                self._holder = agent
                await self._announce(agent)
                return ClaimResult(ok=True, holder=agent)
            return ClaimResult(ok=self._holder == agent, holder=self._holder)

    async def release(self, agent: str) -> None:
        """Give up the soul. Releasing one you do not hold is ignored.

        That last part matters: a keeper that lost its lease while HOLDING must
        not be able to knock the new holder off by finishing its own goodbye.
        """
        async with self._lock:
            if self._holder == agent:
                self._holder = None
                await self._announce(None)

    async def expire(self, agent: str, after_s: float | None = None) -> None:
        """Simulate a session dying without a graceful release (a lid slam).

        Waits ``after_s`` (default ``expiry_delay_s``) on the injected clock,
        then frees the soul if ``agent`` still holds it. Under a ``FakeClock``
        nothing really waits — the sim advances time and this resolves.
        """
        delay = self._expiry_delay_s if after_s is None else after_s
        if delay > 0:
            await self._clock.sleep(delay)
        async with self._lock:
            if self._holder == agent:
                self._holder = None
                await self._announce(None)

    # -- watching ------------------------------------------------------------

    def watch(self) -> AsyncIterator[str | None]:
        """Yield the holder every time it changes, including ``None`` on free.

        The queue is registered synchronously, before the first ``await``, so a
        change that happens immediately after calling ``watch()`` is not missed.
        """
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._watchers.append(queue)

        async def _stream() -> AsyncIterator[str | None]:
            try:
                while True:
                    yield await queue.get()
            finally:
                if queue in self._watchers:
                    self._watchers.remove(queue)

        return _stream()

    # -- internals -----------------------------------------------------------

    async def _announce(self, holder: str | None) -> None:
        self.history.append(holder)
        for queue in list(self._watchers):
            queue.put_nowait(holder)

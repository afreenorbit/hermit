"""In-memory soul lease shared by many keepers in one process. Owner: A.

This is what lets the whole team build before Switch is confirmed, and what the
simulation runs on. ``claim`` must be atomic under an asyncio lock.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .base import ClaimResult


class FakeSoulLease:
    def __init__(self) -> None:
        self._holder: str | None = None
        self._lock = asyncio.Lock()
        self._watchers: list[asyncio.Queue[str | None]] = []

    async def holder(self) -> str | None:
        return self._holder

    async def claim(self, agent: str) -> ClaimResult:
        raise NotImplementedError("TODO(A): Phase 1.3")

    async def release(self, agent: str) -> None:
        raise NotImplementedError("TODO(A): Phase 1.3")

    async def expire(self, holder: str, after_s: float = 0.0) -> None:
        """Simulate a session dying (lid slam) without a graceful release."""
        raise NotImplementedError("TODO(A): Phase 1.3")

    def watch(self) -> AsyncIterator[str | None]:
        raise NotImplementedError("TODO(A): Phase 1.3")

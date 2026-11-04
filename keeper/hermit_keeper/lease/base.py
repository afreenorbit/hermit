"""SoulLease — the one exclusive thing. Owner: A.

Hermit *is* whoever holds the ``soul`` role in Switch. Exactly one holder at a
time is the project's core invariant; ``tests/unit/test_soul_invariant.py``
proves it with hypothesis.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import BaseModel


class ClaimResult(BaseModel):
    ok: bool
    holder: str | None  # current holder after the attempt


class SoulLease(Protocol):
    async def holder(self) -> str | None: ...
    async def claim(self, agent: str) -> ClaimResult: ...
    async def release(self, agent: str) -> None: ...
    def watch(self) -> AsyncIterator[str | None]:
        """Yields the holder every time it changes (including None when freed)."""
        ...

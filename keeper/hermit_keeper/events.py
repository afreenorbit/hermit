"""Event envelope and the in-process event bus.

The envelope here must stay identical to ``shared/schemas/event.schema.json``.
``tests/contract/`` round-trips fixtures through both to keep them honest.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .ids import new_id


class EventType(StrEnum):
    PRESENCE_CHANGED = "PRESENCE_CHANGED"
    SOUL_FREE = "SOUL_FREE"
    SOUL_CLAIMED = "SOUL_CLAIMED"
    SOUL_CLAIM_REJECTED = "SOUL_CLAIM_REJECTED"
    DEPARTURE_STARTED = "DEPARTURE_STARTED"
    SOUL_RELEASED = "SOUL_RELEASED"
    ARRIVAL_ANNOUNCED = "ARRIVAL_ANNOUNCED"
    FAVOR_LEFT = "FAVOR_LEFT"
    FAVOR_ASSIGNED = "FAVOR_ASSIGNED"
    FAVOR_COMPLETED = "FAVOR_COMPLETED"
    SHELL_PIECE_ADDED = "SHELL_PIECE_ADDED"
    BEDTIME_EVICTION = "BEDTIME_EVICTION"
    OVERLAP_SUGGESTED = "OVERLAP_SUGGESTED"
    NUDGE_SENT = "NUDGE_SENT"
    ERROR = "ERROR"


class Event(BaseModel):
    v: int = 1
    id: str = Field(default_factory=lambda: new_id("evt"))
    type: EventType
    host: str
    ts: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class EventBus:
    """Fan-out bus. Subscribers get their own queue; slow ones never block."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []

    async def publish(self, event: Event) -> None:
        for q in list(self._subscribers):
            q.put_nowait(event)

    async def subscribe(self) -> AsyncIterator[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers.remove(q)

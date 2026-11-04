"""PresenceSource — "is the human at this laptop?"  Owner: A."""

from __future__ import annotations

from typing import Protocol


class PresenceSource(Protocol):
    async def idle_seconds(self) -> float:
        """Seconds since the last keyboard/mouse input on this machine."""
        ...

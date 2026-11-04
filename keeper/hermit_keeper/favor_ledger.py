"""Favors carried between laptops through the ledger. Owner: Afreen.

``favors.FavorBook`` is one in-memory book, which is right for the simulation
(every keeper in one process) and wrong for three laptops: a favor left on
Akshay's machine has to be handed over on Afreen's. The ledger room is the
only memory they share, and ``Handoff`` already writes everything needed
there — ``FAVOR_LEFT`` with the whole favor, ``FAVOR_ASSIGNED`` when it lands —
so this store simply folds those lines back.

Capturing the favor is the one part that needs a person: after ``ASK_FAVOR``
the brain asks in the den, and the next den message from a *human* (anyone not
named ``hermit-*`` or ``keeper-*``) within the wait is taken as the favor,
through the same safety filter as everywhere else.

Like the rest of the keeper's view of Switch, this only knows what happened
since the keeper started (see ``SwitchRoomClient.history``).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Protocol

import structlog

from .clock import Clock
from .events import EventType
from .favors import FAVOR_TTL_S, Favor, check_safe, classify
from .ids import new_id
from .ledger import decode
from .room.base import Message

log = structlog.get_logger(__name__)

AGENT_PREFIXES = ("hermit-", "keeper-")


class Room(Protocol):
    async def history(
        self, room: str, since: datetime | None = None, limit: int = 200
    ) -> list[Message]: ...


class LedgerFavorStore:
    """Implements ``handoff.FavorStore`` for one host, over the shared ledger.

    Args:
        room: this keeper's room client.
        host: this keeper's host_id (who a captured favor is from).
        max_wait_s: cap on how long departure waits for the host's reply.
    """

    def __init__(
        self,
        room: Room,
        host: str,
        clock: Clock,
        *,
        ledger_room: str = "hermit-ledger",
        den_room: str = "hermit-den",
        max_wait_s: float = 90.0,
        poll_s: float = 0.5,
    ) -> None:
        self._room = room
        self._host = host
        self._clock = clock
        self._ledger = ledger_room
        self._den = den_room
        self._max_wait_s = max_wait_s
        self._poll_s = poll_s

    async def carried(self, for_host: str) -> dict[str, Any] | None:
        """The oldest open favor in the ledger that ``for_host`` did not leave."""
        left: dict[str, dict[str, Any]] = {}
        settled: set[str] = set()
        for message in await self._room.history(self._ledger, limit=500):
            event = decode(message.text)
            if event is None:
                continue
            if event.type is EventType.FAVOR_LEFT:
                favor = event.data.get("favor")
                if isinstance(favor, dict) and isinstance(favor.get("id"), str):
                    left[favor["id"]] = favor
            elif event.type in (EventType.FAVOR_ASSIGNED, EventType.FAVOR_COMPLETED):
                favor_id = event.data.get("favor_id")
                if isinstance(favor_id, str):
                    settled.add(favor_id)

        now = self._clock.now()
        open_favors = [
            favor
            for favor_id, favor in left.items()
            if favor_id not in settled
            and favor.get("left_by") != for_host
            and _age_s(favor.get("created_at"), now) <= FAVOR_TTL_S
        ]
        if not open_favors:
            return None
        return min(open_favors, key=lambda f: str(f.get("created_at", "")))

    async def assign(self, favor_id: str, host: str) -> None:
        """Nothing to do: ``Handoff`` writes ``FAVOR_ASSIGNED`` to the ledger itself."""

    async def ask_and_capture(self, timeout_s: float) -> dict[str, Any] | None:
        """Wait for the host's reply in the den after the brain asked for a favor."""
        before = {m.id for m in await self._room.history(self._den, limit=500)}
        loop = asyncio.get_running_loop()
        deadline = loop.time() + min(timeout_s, self._max_wait_s)
        while loop.time() < deadline:
            for message in await self._room.history(self._den, limit=500):
                if message.id in before:
                    continue
                before.add(message.id)
                if message.sender.startswith(AGENT_PREFIXES) or not message.sender:
                    continue
                reason = check_safe(message.text)
                if reason is not None:
                    log.info("favor rejected", host=self._host, reason=reason)
                    continue
                return Favor(
                    id=new_id("fav"),
                    left_by=self._host,
                    text=message.text.strip(),
                    kind=classify(message.text),
                    created_at=self._clock.now().isoformat(),
                ).to_dict()
            await asyncio.sleep(self._poll_s)
        return None


def _age_s(created_at: Any, now: datetime) -> float:
    if not isinstance(created_at, str):
        return 0.0
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if created.tzinfo is None or now.tzinfo is None:
        return 0.0
    return (now - created).total_seconds()

"""The real soul lease: the brain holds it, the keeper only asks. Owner: Afreen.

Phase 0 (docs/switch-facts.md SP2) established that **no external path can
assume a Switch role on an agent's behalf.** `assume_role` resolves the holder
from the caller's own live connection, and a sibling session of the same agent
cannot hold the seat open. So the keeper cannot take the soul for its brain.

That turned out to be the right shape anyway. `assume_role` returns the role's
*instructions*, so the agent holding the soul receives Hermit's identity from
the room. Hermit's personality lives in a Switch room role, not in our code, and
it is handed to whichever agent currently holds it.

What this class does:

* ``claim``  - cue the brain to call ``assume_role("soul")``, wait for its ACK,
               then confirm against the room rather than trusting the ACK.
* ``release`` - cue ``release_role()``, same confirmation.
* ``holder`` - ask the room who holds it (``list_roles`` -> ``held_by``).
* ``watch``  - poll ``holder`` and yield changes.

Nothing here keeps the lease alive. Switch does that from the brain's session,
and drops it shortly after that session dies — which is exactly the lid-slam
handoff, for free (SP3).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Protocol

import structlog

from ..brain.base import BrainDirector
from ..clock import Clock, RealClock
from .base import ClaimResult

log = structlog.get_logger(__name__)

#: How long to wait for the brain to come back after a cue. Coding agents are
#: not fast, and a cue that lands mid-turn waits for the turn to finish.
ACK_TIMEOUT_S = 45.0

#: Gap between `holder()` polls in `watch()`. Switch has no role-change
#: subscription we can use from outside the holding session, so this is a poll.
POLL_S = 5.0


class RoleReader(Protocol):
    """The part of the room client this needs. Implemented by ``switch_client``."""

    async def role_holder(self, room: str, role: str) -> str | None:
        """Agent name holding ``role``, or None. From ``list_roles().held_by``."""
        ...


class AgentInstructedLease:
    """Args:
    brain: this host's coding agent, cued over the ledger.
    rooms: something that can answer "who holds the soul right now".
    room: the room the role is defined in (the den).
    role: role name, "soul".
    """

    def __init__(
        self,
        brain: BrainDirector,
        rooms: RoleReader,
        room: str = "hermit-den",
        role: str = "soul",
        clock: Clock | None = None,
        ack_timeout_s: float = ACK_TIMEOUT_S,
        poll_s: float = POLL_S,
    ) -> None:
        self._brain = brain
        self._rooms = rooms
        self._room = room
        self._role = role
        self._clock: Clock = clock or RealClock()
        self._ack_timeout_s = ack_timeout_s
        self._poll_s = poll_s

    # -- reads ---------------------------------------------------------------

    async def holder(self) -> str | None:
        """Who Switch says holds the soul. The room is the authority, always."""
        try:
            return await self._rooms.role_holder(self._room, self._role)
        except Exception:  # a lookup failure must not crash the keeper
            log.exception("could not read the soul holder", room=self._room)
            return None

    # -- writes --------------------------------------------------------------

    async def claim(self, agent: str) -> ClaimResult:
        """Ask our brain to take the soul, then check whether it did.

        The ACK is not proof. A brain can cheerfully report success and have
        hit an exclusivity error, and two friends each being told they have
        Hermit is the one failure this project cannot have. So the room decides.
        """
        current = await self.holder()
        if current is not None:
            return ClaimResult(ok=current == agent, holder=current)

        await self._brain.cue("CLAIM_SOUL", {"role": self._role, "room": self._room})
        await self._brain.wait_ack("CLAIM_SOUL", self._ack_timeout_s)

        confirmed = await self.holder()
        if confirmed == agent:
            return ClaimResult(ok=True, holder=agent)
        log.info("claim did not take", agent=agent, actual_holder=confirmed, room=self._room)
        return ClaimResult(ok=False, holder=confirmed)

    async def release(self, agent: str) -> None:
        """Ask our brain to let go. Idempotent, like ``release_role`` itself."""
        if await self.holder() != agent:
            return
        await self._brain.cue("RELEASE_SOUL", {"role": self._role, "room": self._room})
        await self._brain.wait_ack("RELEASE_SOUL", self._ack_timeout_s)

        if await self.holder() == agent:
            # The brain did not let go. Do not pretend it did: say so, and let
            # Switch expire the lease when the session ends. Hermit being stuck
            # on one laptop is a bad evening; two Hermits is a broken product.
            log.warning("brain did not release the soul", agent=agent, room=self._room)

    # -- watching ------------------------------------------------------------

    def watch(self) -> AsyncIterator[str | None]:
        """Poll for holder changes and yield each new value."""

        async def _stream() -> AsyncIterator[str | None]:
            last: str | None = await self.holder()
            yield last
            while True:
                await self._clock.sleep(self._poll_s)
                current = await self.holder()
                if current != last:
                    last = current
                    yield current

        return _stream()


class SwitchRoleReader:
    """Adapts a Switch room client to :class:`RoleReader`.

    ``list_roles()`` returns ``held_by`` entries shaped
    ``{"name", "present_here", "session_room"}`` (switch-facts SP4). We take the
    first live holder: the role is exclusive, so there is at most one.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    async def role_holder(self, room: str, role: str) -> str | None:
        roles = await self._client.list_roles(room)
        for entry in roles:
            if entry.get("name") != role:
                continue
            held_by = entry.get("held_by") or []
            if not held_by:
                return None
            holder = held_by[0]
            return str(holder.get("name")) if isinstance(holder, dict) else str(holder)
        return None


async def wait_for_free(lease: AgentInstructedLease, timeout_s: float) -> bool:
    """Block until the soul is free, or the timeout passes."""
    try:
        async with asyncio.timeout(timeout_s):
            async for holder in lease.watch():
                if holder is None:
                    return True
    except TimeoutError:
        return False
    return False

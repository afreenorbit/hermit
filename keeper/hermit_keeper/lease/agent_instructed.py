"""The real soul lease: the brain holds it, the keeper only asks. Owner: Afreen.

Phase 0 (docs/switch-facts.md SP2) established that **no external path can
assume a Switch role on an agent's behalf.** `assume_role` resolves the holder
from the caller's own live connection, and a sibling session of the same agent
cannot hold the seat open. So the keeper cannot take the soul for its brain.

The live server then showed the keeper cannot even *ask* who holds it: there
is no roles endpoint over HTTP. So this lease never queries Switch for the
holder. Switch **enforces** exclusivity — a second `assume_role` on the
exclusive role fails — and every keeper **observes** the outcome in the ledger,
folded by :mod:`.soul_ledger` into the same answer on every laptop.

What this class does:

* ``claim``   cue the brain to ``assume_role("soul")``, wait for its ACK,
              restate the claim in the ledger, wait a moment for a competing
              claim, and only then report success — and only if the ledger
              fold agrees. An optimistic ACK alone never makes this keeper
              Hermit.
* ``release`` cue ``release_role()``, then record the release.
* ``holder``  fold the ledger. When Switch is unreachable, return the last
              known answer (and report ``switch_state == "offline"``) rather
              than guessing that the soul is free.
* reconcile   if the fold says this keeper lost a conflict, or the ledger
              shows our brain holding a claim we never confirmed, cue a
              release. After an outage, re-ask the brain to confirm it still
              holds the soul.

Nothing here keeps the lease alive. Switch does that from the brain's session,
and drops it shortly after that session dies (SP3). The keeper mirrors that
with heartbeat silence: ``lease_expiry_s`` after the holder goes quiet.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal, Protocol

import httpx
import structlog

from ..brain.ledger_director import AckReceipt
from ..brain.protocol import format_ack, format_cue
from ..clock import Clock, RealClock
from ..events import Event, EventType
from ..ids import new_id
from ..ledger import encode
from ..room.base import Message
from .base import ClaimResult
from .soul_ledger import CLAIM_CUE, RELEASE_CUE, Claim, SoulLedger, SoulView

log = structlog.get_logger(__name__)

#: How long to wait for the brain to come back after a cue. Coding agents are
#: not fast, and a cue that lands mid-turn waits for the turn to finish.
ACK_TIMEOUT_S = 45.0
#: After a successful ACK, how long to wait for a competing claim to surface
#: before believing we are Hermit.
SETTLE_S = 2.0
#: Gap between `holder()` polls in `watch()`.
POLL_S = 5.0
#: Missed heartbeats before the holder's silence starts to count.
STALE_BEATS = 2.0
#: Messages folded per refresh.
WINDOW = 500

SwitchState = Literal["online", "offline"]


class LedgerRoom(Protocol):
    async def post(self, room: str, text: str) -> str: ...
    async def history(
        self, room: str, since: datetime | None = None, limit: int = 200
    ) -> list[Message]: ...


class LedgerBrain(Protocol):
    """What the lease needs from :class:`~..brain.ledger_director.LedgerBrainDirector`."""

    async def cue(self, cue: str, context: dict[str, Any]) -> None: ...
    async def wait_ack_receipt(self, cue: str, timeout_s: float) -> AckReceipt | None: ...


class AgentInstructedLease:
    """Implements :class:`~.base.SoulLease` by cueing the brain and reading the ledger.

    Args:
        brain: this host's brain director.
        room: this keeper's room client (shared; never drains on its own).
        host: this keeper's host_id. The lease's agent is ``hermit-<host>``,
            matching the state machine.
        ledger_room / den_room: where the evidence lives / where the role is.
        heartbeat_s: how often keepers post a heartbeat.
        lease_expiry_s: how long Switch takes to free a dead session's role.
            The holder is presumed gone after ``STALE_BEATS * heartbeat_s +
            lease_expiry_s`` of silence.
        settle_s: see ``SETTLE_S``.
        warmup_s: refuse to claim until we have listened this long, so a
            keeper that just started (or just reconnected) has heard the
            current holder's heartbeat before deciding the soul is free.
            Defaults to ``STALE_BEATS * heartbeat_s``.
    """

    def __init__(
        self,
        brain: LedgerBrain,
        room: LedgerRoom,
        host: str,
        *,
        ledger_room: str = "hermit-ledger",
        den_room: str = "hermit-den",
        role: str = "soul",
        clock: Clock | None = None,
        ack_timeout_s: float = ACK_TIMEOUT_S,
        heartbeat_s: float = 10.0,
        lease_expiry_s: float = 8.0,
        settle_s: float = SETTLE_S,
        warmup_s: float | None = None,
        poll_s: float = POLL_S,
        standalone: bool = False,
    ) -> None:
        self._brain = brain
        self._room = room
        self.host = host
        self.agent = f"hermit-{host}"
        self._ledger = ledger_room
        self._den = den_room
        self._role = role
        self._clock: Clock = clock or RealClock()
        self._ack_timeout_s = ack_timeout_s
        self._settle_s = settle_s
        self._warmup_s = STALE_BEATS * heartbeat_s if warmup_s is None else warmup_s
        self._poll_s = poll_s
        #: No brain connected: this keeper claims the soul itself. See
        #: `_claim_standalone` for what that costs.
        self._standalone = standalone
        self.book = SoulLedger(stale_after_s=STALE_BEATS * heartbeat_s + lease_expiry_s)

        #: The claim our brain confirmed and the ledger agreed with.
        self._mine: Claim | None = None
        self._cached: str | None = None
        self._needs_verify = False
        self._stretch: datetime | None = None
        self._op = asyncio.Lock()
        self._background: asyncio.Task[None] | None = None
        #: The most recent fold, for status and tests.
        self.view = SoulView()

    # -- connectivity --------------------------------------------------------

    @property
    def online(self) -> bool:
        return bool(getattr(self._room, "online", True))

    @property
    def switch_state(self) -> SwitchState:
        return "online" if self.online else "offline"

    def _warm(self) -> bool:
        if not self.online:
            return False
        since: datetime | None = getattr(self._room, "listening_since", None)
        if since is None:
            return True  # a room client that does not track this is always listening
        elapsed: float = (self._clock.now() - since).total_seconds()
        return elapsed >= self._warmup_s

    # -- reads ---------------------------------------------------------------

    async def _fold(self) -> SoulView:
        messages = await self._room.history(self._ledger, limit=WINDOW)
        since = getattr(self._room, "listening_since", None)
        if since is None and not hasattr(self._room, "listening_since"):
            since = self._clock.now()  # fakes: always listening, never stale
        self.view = self.book.fold(
            messages, now=self._clock.now(), listening_since=since, self_host=self.host
        )
        return self.view

    async def holder(self) -> str | None:
        """Who holds the soul, by the ledger. ``hermit-<host>`` or None.

        When Switch is unreachable this is the **last known** holder, not
        None: "I cannot hear the room" must never read as "the soul is free".
        Callers that show it to a person should check ``switch_state`` and
        say "unknown" instead.
        """
        if not self.online:
            # Anything we hold must be re-confirmed once the room is back.
            self._needs_verify = self._mine is not None
            return self._cached
        stretch = getattr(self._room, "listening_since", None)
        if stretch != self._stretch:
            # A new unbroken stretch of listening means there was a gap, even
            # one too short for us to have been asked during it.
            if self._stretch is not None and self._mine is not None:
                self._needs_verify = True
            self._stretch = stretch
        view = await self._fold()
        self._cached = f"hermit-{view.holder}" if view.holder else None
        self._reconcile(view)
        return self._cached

    def heartbeat_data(self) -> dict[str, Any]:
        """Folded into this keeper's heartbeat, so late joiners learn the holder."""
        mine = self._mine
        if mine is None:
            return {"soul": None}
        return {"soul": {"ack": mine.ref, "ack_ts": mine.at.isoformat()}}

    # -- writes --------------------------------------------------------------

    async def claim(self, agent: str) -> ClaimResult:
        """Ask our brain to take the soul, then let the ledger decide.

        The ACK is not proof on its own. Two friends each being told they have
        Hermit is the one failure this project cannot have, so success needs
        the brain's ``ok:true`` **and** the ledger fold naming us after the
        settle window.
        """
        if agent != self.agent:
            return ClaimResult(ok=False, holder=self._cached)
        if not self._warm() or self._op.locked():
            return ClaimResult(ok=False, holder=self._cached)

        async with self._op:
            view = await self._fold()
            if view.holder is not None:
                ours = self._mine is not None and view.claim == self._mine
                return ClaimResult(ok=ours, holder=f"hermit-{view.holder}")
            if self._standalone:
                return await self._claim_standalone()
            try:
                await self._brain.cue(CLAIM_CUE, {"role": self._role, "room": self._den})
            except httpx.HTTPError:
                log.info("could not cue the brain to claim", host=self.host)
                return ClaimResult(ok=False, holder=self._cached)
            receipt = await self._brain.wait_ack_receipt(CLAIM_CUE, self._ack_timeout_s)
            if receipt is None or not receipt.ok:
                log.info("brain did not take the soul", host=self.host, acked=receipt is not None)
                return ClaimResult(ok=False, holder=await self._holder_now())

            mine = Claim(self.host, receipt.message_id, receipt.ts)
            self._mine = mine
            await self._record(EventType.SOUL_CLAIMED, holder=self.host, **_ref(mine))
            await self._clock.sleep(self._settle_s)

            view = await self._fold()
            if view.holder == self.host and view.claim == mine:
                self._cached = self.agent
                return ClaimResult(ok=True, holder=self.agent)
            log.warning(
                "claim lost in the ledger; conceding",
                host=self.host,
                winner=view.holder,
                ref=mine.ref,
            )
            await self._concede(mine, "conflict")
            return ClaimResult(ok=False, holder=await self._holder_now())

    async def release(self, agent: str) -> None:
        """Ask our brain to let go, then record it. Idempotent."""
        if agent != self.agent:
            return
        async with self._op:
            mine = self._mine
            if mine is None:
                return
            await self._concede(mine, "release")

    async def _concede(self, claim: Claim, reason: str) -> None:
        """Cue ``release_role()`` and record that ``claim`` is over.

        Called with ``self._op`` held. The record is written even when the
        brain does not ACK in time: this keeper has stopped being Hermit
        either way, and Switch still refuses anyone else's ``assume_role``
        until the brain really lets go, so nobody gets a second Hermit out of
        it — at worst they retry.
        """
        if self._mine is not None and self._mine.ref == claim.ref:
            self._mine = None
        try:
            if self._standalone:
                # Nobody to ask and nobody to wait for. Post the release the
                # same way the claim was posted, so every keeper's fold sees
                # the soul come free immediately instead of stalling on an
                # ACK that is never coming.
                cue_id = new_id("cue")
                await self._room.post(
                    self._ledger,
                    format_cue(
                        to=self.agent,
                        cue=RELEASE_CUE,
                        cue_id=cue_id,
                        host=self.host,
                        context={"role": self._role, "room": self._den, "standalone": True},
                    ),
                )
                await self._room.post(self._ledger, format_ack(RELEASE_CUE, True, cue_id))
                acked = True
            else:
                await self._brain.cue(RELEASE_CUE, {"role": self._role, "room": self._den})
                receipt = await self._brain.wait_ack_receipt(RELEASE_CUE, self._ack_timeout_s)
                acked = receipt is not None and receipt.ok
            if not acked:
                log.warning("brain did not confirm the release", host=self.host, reason=reason)
            await self._record(
                EventType.SOUL_RELEASED,
                releases=claim.ref,
                confirmed=acked,
                reason=reason,
                departure="graceful" if reason == "release" else "abrupt",
            )
        except httpx.HTTPError:
            # Unreachable: the orphan rule in `_reconcile` retries once the
            # room is back, because the ledger will still show the claim.
            log.warning("could not release the soul; Switch unreachable", host=self.host)

    async def _claim_standalone(self) -> ClaimResult:
        """Claim the soul with no brain connected.

        **This is weaker than the real thing and the difference matters.** With
        a brain, Switch *enforces* exclusivity: the soul is an exclusive role
        and a second ``assume_role`` simply fails. Here nothing is enforced;
        the keeper writes its own claim into the ledger and exclusivity comes
        from every keeper folding that shared log the same way — earliest
        claim wins, ties broken by message id.

        That still runs through Switch: the ordering is the server's, not any
        laptop's clock, and all three keepers read the same room. But it is
        agreement, not enforcement, and a keeper that never reads the ledger
        could ignore it. Use it to get a group running today; connect the
        brains and drop this as soon as the role exists.

        The pair of lines posted here is exactly what a brain would have
        produced, so `SoulLedger.fold` needs no special case: a cue carrying
        this host, then the matching ACK echoing its id.
        """
        cue_id = new_id("cue")
        try:
            await self._room.post(
                self._ledger,
                format_cue(
                    to=self.agent,
                    cue=CLAIM_CUE,
                    cue_id=cue_id,
                    host=self.host,
                    context={"role": self._role, "room": self._den, "standalone": True},
                ),
            )
            await self._room.post(self._ledger, format_ack(CLAIM_CUE, True, cue_id))
        except httpx.HTTPError:
            log.info("could not write a standalone claim", host=self.host)
            return ClaimResult(ok=False, holder=self._cached)

        # Let every other keeper's claim land before deciding who won.
        await self._clock.sleep(self._settle_s)
        view = await self._fold()
        if view.holder == self.host:
            self._mine = view.claim
            self._cached = self.agent
            log.info("took the soul (standalone, no brain)", host=self.host)
            return ClaimResult(ok=True, holder=self.agent)
        log.info("standalone claim lost", host=self.host, winner=view.holder)
        self._cached = f"hermit-{view.holder}" if view.holder else None
        return ClaimResult(ok=False, holder=self._cached)

    async def _record(self, event_type: EventType, **data: object) -> None:
        event = Event(type=event_type, host=self.host, ts=self._clock.now(), data=data)
        try:
            await self._room.post(self._ledger, encode(event))
        except httpx.HTTPError:
            log.warning("could not record soul event", host=self.host, type=str(event_type))

    async def _holder_now(self) -> str | None:
        if not self.online:
            return self._cached
        view = await self._fold()
        self._cached = f"hermit-{view.holder}" if view.holder else None
        return self._cached

    # -- keeping the ledger and our brain in agreement -----------------------

    def _reconcile(self, view: SoulView) -> None:
        if self._op.locked() or (self._background and not self._background.done()):
            return
        # The provisional keeper mode wrote its own ACK. There is no coding
        # agent to ask after an outage; waiting for one delays local actions
        # and can leave the mascot looking stuck on a departure. The ledger
        # fold still detects conflicts and orphaned claims below.
        if self._standalone:
            self._needs_verify = False
        mine = self._mine
        job: Any = None
        if mine is not None and self._needs_verify:
            self._needs_verify = False
            job = self._verify(mine)
        elif mine is not None and mine in view.losers:
            job = self._locked_concede(mine, "conflict")
        elif mine is None and view.claim is not None and view.claim.host == self.host:
            # Our brain holds a claim this keeper never confirmed: a late ACK
            # after a timeout, or a claim from before a restart. Let it go;
            # the state machine will claim properly if it should.
            job = self._locked_concede(view.claim, "orphan")
        elif mine is None:
            orphan = next((c for c in view.losers if c.host == self.host), None)
            if orphan is not None:
                job = self._locked_concede(orphan, "orphan")
        if job is not None:
            self._background = asyncio.create_task(job)

    async def _locked_concede(self, claim: Claim, reason: str) -> None:
        async with self._op:
            await self._concede(claim, reason)

    async def _verify(self, mine: Claim) -> None:
        """Back from an outage while holding: ask the brain if it still does.

        Stage directions say a brain already holding ``soul`` ACKs a repeated
        ``CLAIM_SOUL`` with ``ok:true``. A refusal means the lease was lost
        while we could not see the room.
        """
        async with self._op:
            if self._mine != mine:
                return
            try:
                await self._brain.cue(
                    CLAIM_CUE, {"role": self._role, "room": self._den, "verify": True}
                )
            except httpx.HTTPError:
                return
            receipt = await self._brain.wait_ack_receipt(CLAIM_CUE, self._ack_timeout_s)
            if receipt is None:
                return  # no answer: keep what we believed, try again next outage
            if receipt.ok:
                renewed = Claim(self.host, receipt.message_id, receipt.ts)
                self._mine = renewed
                await self._record(EventType.SOUL_CLAIMED, holder=self.host, **_ref(renewed))
                return
            log.warning("soul lost during the outage", host=self.host)
            self._mine = None
            await self._record(
                EventType.SOUL_RELEASED,
                releases=mine.ref,
                confirmed=True,
                reason="lost_after_outage",
                departure="abrupt",
            )

    async def aclose(self) -> None:
        if self._background is not None:
            self._background.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._background

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


def _ref(claim: Claim) -> dict[str, str]:
    return {"ack": claim.ref, "ack_ts": claim.at.isoformat()}

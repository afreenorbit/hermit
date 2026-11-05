"""The keeper state machine. Owner: Afreen. Spec: plan.md 3.2.

         ASLEEP --present >= debounce--> AWAKE_WAITING
         AWAKE_WAITING --soul free & eligible--> CLAIMING
         CLAIMING --ok--> HOLDING       CLAIMING --rejected--> AWAKE_WAITING
         HOLDING --idle & dwell, or bedtime, or manual--> DEPARTING --> ASLEEP
         HOLDING --lease lost--> ASLEEP (no goodbye)
         bedtime --> BEDTIME_LOCK, which never claims

The invariant this exists to protect: **at most one host is in HOLDING across
the whole group at any instant.** The exclusive Switch role is the real
enforcement; everything here is about not fighting it — backing off politely,
not thrashing, and never speaking as Hermit without the lease.

Driven by :meth:`tick`, not by background tasks, so the simulation can run a
day in milliseconds and tests are deterministic.
"""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import StrEnum

from .clock import Clock
from .events import Event, EventBus, EventType
from .lease.base import SoulLease
from .presence.composite import CompositePresence


class State(StrEnum):
    ASLEEP = "ASLEEP"
    AWAKE_WAITING = "AWAKE_WAITING"
    CLAIMING = "CLAIMING"
    HOLDING = "HOLDING"
    DEPARTING = "DEPARTING"
    BEDTIME_LOCK = "BEDTIME_LOCK"


#: States in which this host is speaking as Hermit.
SPEAKING_STATES = frozenset({State.HOLDING, State.DEPARTING})

Hook = Callable[[], Awaitable[None]]
DepartHook = Callable[[str], Awaitable[None]]


async def _noop() -> None:
    return None


async def _noop_depart(_reason: str) -> None:
    return None


class KeeperStateMachine:
    """One host's half of the handoff.

    Args:
        host: this host's ``host_id``.
        agent: the agent name that holds the lease, ``hermit-<host>``.
        lease: the soul. Fake in tests and the sim, Switch in real life.
        presence: already-debounced presence for this host.
        clock: injected so a day can run in milliseconds.
        bus: where this keeper's events go.
        is_bedtime: ``(local_now) -> bool``. Injected rather than imported so
            this file does not reach into ``bedtime.py``, which Abhishek owns.
        min_dwell_s: no *voluntary* departure before this. A lid close still
            ends it, through lease expiry — that path does not come through
            here at all.
        claim_delay_s: how long to wait after seeing a free soul before
            grabbing it. Fairness lives here: pass a shorter delay for hosts
            who hosted least recently, and the ping-pong between two always-on
            laptops stops.
        on_claimed / on_departing: handoff hooks (``handoff.py``).
    """

    def __init__(
        self,
        host: str,
        agent: str,
        lease: SoulLease,
        presence: CompositePresence,
        clock: Clock,
        bus: EventBus | None = None,
        *,
        is_bedtime: Callable[[datetime], bool] | None = None,
        min_dwell_s: float = 600.0,
        claim_delay_s: float = 0.0,
        yield_s: float = 300.0,
        others_available: Callable[[], bool] | None = None,
        claim_jitter_s: float = 3.0,
        backoff_s: float = 30.0,
        on_claimed: Hook | None = None,
        on_departing: DepartHook | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.host = host
        self.agent = agent
        self.state = State.ASLEEP

        self._lease = lease
        self._presence = presence
        self._clock = clock
        self._bus = bus or EventBus()
        self._is_bedtime = is_bedtime or (lambda _now: False)

        self._min_dwell_s = min_dwell_s
        self._claim_delay_s = claim_delay_s
        #: After handing Hermit on, stand aside this long while anyone else
        #: could take it. Bounded, so Hermit is never stranded.
        self._yield_s = yield_s
        #: "Is another laptop awake and able to host?" Supplied by the runtime
        #: from the group view; without it we assume we are alone.
        self._others_available = others_available or (lambda: False)
        self._yield_until: float = 0.0
        self._claim_jitter_s = claim_jitter_s
        self._backoff_s = backoff_s
        self._on_claimed = on_claimed or _noop
        self._on_departing = on_departing or _noop_depart
        self._rng = rng or random.Random()

        self._held_since: float | None = None
        self._free_seen_at: float | None = None
        self._backoff_until: float = 0.0
        self._departure_reason: str | None = None
        #: Set when the host asks to leave through the API.
        self.manual_depart = False
        #: Set when the host asks to TAKE Hermit through the API. Skips the
        #: fairness delay and the stand-aside: someone pressing the button has
        #: said what they want more clearly than any heuristic can infer.
        self.manual_claim = False

    # -- reads ---------------------------------------------------------------

    @property
    def holding(self) -> bool:
        return self.state is State.HOLDING

    @property
    def dwell_s(self) -> float:
        if self._held_since is None:
            return 0.0
        return self._now() - self._held_since

    def _now(self) -> float:
        return self._clock.now().timestamp()

    # -- the tick ------------------------------------------------------------

    async def tick(self) -> State:
        """Advance one step. Safe to call as often as you like."""
        changed = await self._presence.tick()
        if changed:
            await self._emit(
                EventType.PRESENCE_CHANGED,
                present=self._presence.present,
                reason=str(self._presence.reason),
            )

        # Losing the lease beats every other transition: if we are not the
        # holder we must stop being Hermit immediately, with no goodbye.
        if self.state in SPEAKING_STATES and await self._lease.holder() != self.agent:
            self._held_since = None
            self.state = State.ASLEEP if not self._presence.present else State.AWAKE_WAITING
            await self._emit(
                EventType.SOUL_FREE, previous_holder=self.host, freed_by="lease_expiry"
            )
            return self.state

        handler = {
            State.ASLEEP: self._tick_asleep,
            State.AWAKE_WAITING: self._tick_waiting,
            State.CLAIMING: self._tick_claiming,
            State.HOLDING: self._tick_holding,
            State.DEPARTING: self._tick_departing,
            State.BEDTIME_LOCK: self._tick_bedtime_lock,
        }[self.state]
        await handler()
        return self.state

    # -- per-state -----------------------------------------------------------

    async def _tick_asleep(self) -> None:
        # Pressing the button is proof somebody is at this laptop, so it does
        # not have to wait for presence to settle first. Bedtime still wins:
        # Hermit refuses to be a reason to stay up, button or no button.
        if self.manual_claim and not self._is_bedtime(self._clock.now()):
            self.state = State.AWAKE_WAITING
            return
        if self._presence.settled():
            self.state = (
                State.BEDTIME_LOCK if self._is_bedtime(self._clock.now()) else State.AWAKE_WAITING
            )

    async def _tick_waiting(self) -> None:
        if not self._presence.present:
            self.state = State.ASLEEP
            self._free_seen_at = None
            return
        if self._is_bedtime(self._clock.now()):
            self.state = State.BEDTIME_LOCK
            return
        if self.manual_claim:
            holder = await self._lease.holder()
            if holder is None:
                self.manual_claim = False
                self._free_seen_at = None
                self._yield_until = 0.0
                self._backoff_until = 0.0
                self.state = State.CLAIMING
                return
            # Taken already. Drop the request rather than queue it, so a
            # forgotten press cannot grab Hermit off someone minutes later.
            self.manual_claim = False

        if self._now() < self._backoff_until:
            return

        holder = await self._lease.holder()
        if holder is not None:
            self._free_seen_at = None
            # Somebody else took it: we have handed over for real, so the
            # stand-aside has done its job and normal fairness resumes.
            self._yield_until = 0.0
            return

        if self._now() < self._yield_until:
            if self._others_available():
                return
            # Nobody else can host. Standing aside now would just leave
            # Hermit nowhere, so take it back rather than strand it.
            self._yield_until = 0.0

        # The soul is free. Wait out the fairness delay before reaching for it,
        # so the host who hosted least recently gets first go.
        if self._free_seen_at is None:
            self._free_seen_at = self._now()
            return
        waited = self._now() - self._free_seen_at
        if waited >= self._claim_delay_s + self._rng.uniform(0, self._claim_jitter_s):
            self.state = State.CLAIMING

    async def _tick_claiming(self) -> None:
        result = await self._lease.claim(self.agent)
        self._free_seen_at = None
        if result.ok:
            self._held_since = self._now()
            self.state = State.HOLDING
            await self._emit(EventType.SOUL_CLAIMED, holder=self.host)
            await self._on_claimed()
            return
        self._backoff_until = self._now() + self._backoff_s
        self.state = State.AWAKE_WAITING
        await self._emit(EventType.SOUL_CLAIM_REJECTED, holder=result.holder)

    async def _tick_holding(self) -> None:
        reason = self._departure_reason_now()
        if reason is None:
            return
        self.state = State.DEPARTING
        self._departure_reason = reason
        await self._emit(EventType.DEPARTURE_STARTED, reason=reason)

    async def _tick_departing(self) -> None:
        reason = self._departure_reason or "idle"
        await self._on_departing(reason)
        await self._lease.release(self.agent)
        departure = (
            "bedtime" if reason == "bedtime" else ("manual" if reason == "manual" else "graceful")
        )
        await self._emit(EventType.SOUL_RELEASED, departure=departure)

        self._held_since = None
        self._departure_reason = None
        self.manual_depart = False
        if reason == "bedtime":
            self.state = State.BEDTIME_LOCK
        elif self._presence.present:
            self.state = State.AWAKE_WAITING
            self._backoff_until = self._now() + self._backoff_s
            # You just said "go". Taking it straight back because you happen
            # to be the most eligible makes the button look broken, so stand
            # aside for a while — but only while somebody else could actually
            # take it, or Hermit would have nowhere to go.
            self._yield_until = self._now() + self._yield_s
        else:
            self.state = State.ASLEEP

    async def _tick_bedtime_lock(self) -> None:
        """Wait out bedtime. Never claim, however awake the host is.

        This is the rule that makes Hermit worth trusting: it refuses to be a
        reason to stay up.
        """
        if not self._is_bedtime(self._clock.now()):
            self.state = State.AWAKE_WAITING if self._presence.present else State.ASLEEP

    # -- internals -----------------------------------------------------------

    def _departure_reason_now(self) -> str | None:
        if self.manual_depart:
            return "manual"
        if self._is_bedtime(self._clock.now()):
            return "bedtime"
        # Min dwell protects only voluntary departures: Hermit should not bounce
        # off a host who stepped away for a moment.
        if not self._presence.present and self.dwell_s >= self._min_dwell_s:
            return "idle"
        return None

    async def _emit(self, event_type: EventType, **data: object) -> None:
        await self._bus.publish(
            Event(type=event_type, host=self.host, ts=self._clock.now(), data=data)
        )

"""Arrive and depart sequences. Owner: Afreen. Spec: plan.md 3.3.

The state machine decides *when* Hermit moves. This decides *what happens* when
it does: gather the context, assign the favor that was carried here, cue the
brain, and write the ledger line so the journey can always be rebuilt from the
room.

Everything Abhishek owns — favors, weather, the window folder — is reached
through the small protocols below rather than imported. That keeps this file out
of ``favors.py`` and ``context/``, lets both halves be written at once, and
means the whole sequence can be tested with three tiny stubs.
"""

from __future__ import annotations

from typing import Any, Protocol

import structlog

from .brain.base import BrainDirector
from .clock import Clock
from .events import Event, EventBus, EventType
from .ids import new_id
from .ledger import decode, encode
from .room.base import RoomClient

log = structlog.get_logger(__name__)

#: How long the host gets to answer "leave something for the next person?"
#: before Hermit leaves anyway. Nobody should be held hostage by a crab.
FAVOR_WAIT_S = 90.0


class FavorStore(Protocol):
    """Implemented by ``favors.py`` (Abhishek). Phase 4.1."""

    async def carried(self, for_host: str) -> dict[str, Any] | None:
        """The open favor Hermit is carrying into ``for_host``, if any."""
        ...

    async def assign(self, favor_id: str, host: str) -> None: ...

    async def ask_and_capture(self, timeout_s: float) -> dict[str, Any] | None:
        """Wait for the host to leave a favor. ``None`` if they don't."""
        ...


class ContextProvider(Protocol):
    """Implemented by ``context/`` (Abhishek). Phase 4.3."""

    async def arrival_context(self) -> dict[str, Any]:
        """City, local time, weather, window file *names* — never contents."""
        ...


class Handoff:
    """Args:
    host: this host's ``host_id``.
    room: a room client for posting to the den and the ledger.
    brain: this host's coding agent.
    clock / bus: injected as everywhere else.
    favors / context: Abhishek's modules, or stubs. Both optional so this
        works end to end before Phase 4 lands.
    """

    def __init__(
        self,
        host: str,
        room: RoomClient,
        brain: BrainDirector,
        clock: Clock,
        bus: EventBus | None = None,
        *,
        favors: FavorStore | None = None,
        context: ContextProvider | None = None,
        den_room: str = "hermit-den",
        ledger_room: str = "hermit-ledger",
    ) -> None:
        self.host = host
        self._room = room
        self._brain = brain
        self._clock = clock
        self._bus = bus or EventBus()
        self._favors = favors
        self._context = context
        self._den = den_room
        self._ledger = ledger_room

        #: Last known previous stop. Read from the ledger, not from local
        #: memory: a keeper has never seen the stops that happened on other
        #: laptops, and the room is the only thing that has.
        self.previous_host: str | None = None
        self.previous_departure: str | None = None
        #: The current stop, set on arrival. Phase 4 turns this into a shell piece.
        self.stop_id: str | None = None

    # -- arrival -------------------------------------------------------------

    async def on_claimed(self) -> None:
        """Hermit just landed here."""
        self.stop_id = new_id("stop")
        self.previous_host, self.previous_departure = await self._read_previous_stop()
        context: dict[str, Any] = {
            "stop_id": self.stop_id,
            "previous_host": self.previous_host,
            "previous_departure": self.previous_departure,
            "local_time": self._clock.now().isoformat(),
        }
        if self._context is not None:
            context.update(await self._context.arrival_context())

        favor = await self._favors.carried(self.host) if self._favors is not None else None
        if favor is not None:
            await self._favors.assign(favor["id"], self.host)  # type: ignore[union-attr]
            context["favor"] = favor
            await self._write(EventType.FAVOR_ASSIGNED, favor_id=favor["id"], assignee=self.host)

        await self._brain.cue("ARRIVE", context)
        await self._write(
            EventType.ARRIVAL_ANNOUNCED,
            stop_id=self.stop_id,
            weather=context.get("weather"),
            favor_id=favor["id"] if favor else None,
            previous_host=self.previous_host,
            previous_departure=self.previous_departure,
        )

    # -- departure -----------------------------------------------------------

    async def on_departing(self, reason: str) -> None:
        """Hermit is leaving. Ask for a favor, say goodbye, then let go.

        Called by the state machine, which releases the lease immediately
        afterwards. An abrupt departure never reaches this code at all — the
        machine is gone and Switch's lease expiry does the work.
        """
        favor = None
        if self._favors is not None:
            await self._brain.cue("ASK_FAVOR", {"next_host_known": False})
            favor = await self._favors.ask_and_capture(FAVOR_WAIT_S)
            if favor is not None:
                await self._brain.cue("FAVOR_CAPTURED", {"text": favor["text"]})
                await self._write(EventType.FAVOR_LEFT, favor=favor)
            else:
                log.info("no favor left", host=self.host, reason=reason)

        await self._brain.cue("DEPART", {"reason": reason})
        departure = {"bedtime": "bedtime", "manual": "manual"}.get(reason, "graceful")
        await self._write(EventType.SOUL_RELEASED, stop_id=self.stop_id, departure=departure)

    # -- internals -----------------------------------------------------------

    async def _read_previous_stop(self) -> tuple[str | None, str | None]:
        """Who had Hermit before this, and how did they leave?

        The ledger is the only shared memory the group has, so this is where
        "I was just with Abhishek" comes from. It is also how an **abrupt**
        departure is detected: a host who announced an arrival but never wrote
        a ``SOUL_RELEASED`` did not say goodbye — their lid came down and
        Switch's lease expiry freed the soul. Phase 4 turns that into a cracked
        shell piece.
        """
        messages = await self._room.history(self._ledger, limit=500)
        events = [e for e in (decode(m.text) for m in messages) if e is not None]

        for index in range(len(events) - 1, -1, -1):
            event = events[index]
            if event.type is not EventType.ARRIVAL_ANNOUNCED or event.host == self.host:
                continue
            released = next(
                (
                    later
                    for later in events[index + 1 :]
                    if later.type is EventType.SOUL_RELEASED and later.host == event.host
                ),
                None,
            )
            if released is None:
                return event.host, "abrupt"
            departure = released.data.get("departure", "graceful")
            return event.host, str(departure)
        return None, None

    async def _write(self, event_type: EventType, **data: object) -> None:
        """One event: on the bus for the critter, in the ledger for the journey."""
        event = Event(type=event_type, host=self.host, ts=self._clock.now(), data=data)
        await self._bus.publish(event)
        await self._room.post(self._ledger, encode(event))

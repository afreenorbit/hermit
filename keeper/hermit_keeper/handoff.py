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

from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from .brain.base import BrainDirector
from .clock import Clock
from .events import Event, EventBus, EventType
from .ids import new_id
from .ledger import decode, encode
from .room.base import RoomClient
from .shell_model import ShellPiece, describe, hurry_line, make_piece

log = structlog.get_logger(__name__)

#: How long the host gets to answer "leave something for the next person?"
#: before Hermit leaves anyway. Nobody should be held hostage by a crab.
FAVOR_WAIT_S = 90.0

#: How long to wait for a favor when no brain is connected to ask on our
#: behalf. Short on purpose: the ask still happens and a human can still
#: answer in the den, but the departure does not stall on it.
NO_BRAIN_FAVOR_WAIT_S = 3.0

_PROVIDERS = ("claude-code", "codex", "opencode", "other")


@dataclass(frozen=True)
class PreviousStop:
    """The stop before this one, as the ledger remembers it."""

    host: str | None = None
    departure: str | None = None
    stop_id: str | None = None
    #: How long Hermit was there, as far as the ledger can tell. For an abrupt
    #: stop this runs to that host's last line in the ledger.
    dwell_s: float = 0.0
    #: Nobody else arrived in between: that stop handed Hermit straight here.
    immediate: bool = False
    #: Somebody already turned this abrupt stop into a cracked piece.
    already_cracked: bool = False

    @property
    def needs_cracked_piece(self) -> bool:
        return (
            self.departure == "abrupt"
            and self.immediate
            and not self.already_cracked
            and self.stop_id is not None
        )


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
        brain_is_live: bool = True,
        den_room: str = "hermit-den",
        ledger_room: str = "hermit-ledger",
        brain_provider: str | None = None,
    ) -> None:
        self.host = host
        self._room = room
        self._brain = brain
        #: False when no coding agent is connected to answer cues.
        self._brain_is_live = brain_is_live
        self._clock = clock
        self._bus = bus or EventBus()
        self._favors = favors
        self._context = context
        self._den = den_room
        self._ledger = ledger_room
        #: Which brain voices Hermit here. Only the cracked piece needs it.
        self._provider = brain_provider

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
        previous = await self._read_previous_stop()
        self.previous_host, self.previous_departure = previous.host, previous.departure
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

        # S3: a lid slam is told, not hidden. The next host hears it, and the
        # shell keeps a cracked piece so the map shows it too.
        cracked = self._cracked_piece(previous, context) if previous.needs_cracked_piece else None
        if previous.departure == "abrupt" and previous.immediate:
            context["left_in_a_hurry"] = True
            context["hurry_line"] = hurry_line(previous.host)
        if cracked is not None:
            hour = context.get("local_hour")
            context["cracked_piece"] = describe(cracked, hour if isinstance(hour, int) else None)

        await self._brain.cue("ARRIVE", context)
        await self._write(
            EventType.ARRIVAL_ANNOUNCED,
            stop_id=self.stop_id,
            weather=context.get("weather"),
            favor_id=favor["id"] if favor else None,
            previous_host=self.previous_host,
            previous_departure=self.previous_departure,
        )
        if cracked is not None:
            # Written after ARRIVAL_ANNOUNCED so the export pins it to this stop.
            await self._write(
                EventType.SHELL_PIECE_ADDED,
                piece=cracked.to_dict(),
                cracked_for_stop=previous.stop_id,
                previous_host=previous.host,
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
            # With no brain in the room nobody will ever answer, and a
            # 90-second stall in DEPARTING looks exactly like a hang. Ask, but
            # do not hold the handoff open waiting for a reply that cannot come.
            wait_s = FAVOR_WAIT_S if self._brain_is_live else NO_BRAIN_FAVOR_WAIT_S
            favor = await self._favors.ask_and_capture(wait_s)
            if favor is not None:
                await self._brain.cue("FAVOR_CAPTURED", {"text": favor["text"]})
                await self._write(EventType.FAVOR_LEFT, favor=favor)
            else:
                log.info("no favor left", host=self.host, reason=reason)

        await self._brain.cue("DEPART", {"reason": reason})
        departure = {"bedtime": "bedtime", "manual": "manual"}.get(reason, "graceful")
        await self._write(EventType.SOUL_RELEASED, stop_id=self.stop_id, departure=departure)

    # -- internals -----------------------------------------------------------

    async def _read_previous_stop(self) -> PreviousStop:
        """Who had Hermit before this, and how did they leave?

        The ledger is the only shared memory the group has, so this is where
        "I was just with Abhishek" comes from. It is also how an **abrupt**
        departure is detected: a host who announced an arrival but never wrote
        a ``SOUL_RELEASED`` did not say goodbye — their lid came down and
        Switch's lease expiry freed the soul. That becomes "I left in a hurry"
        and a cracked shell piece (S3).
        """
        messages = await self._room.history(self._ledger, limit=500)
        events = [e for e in (decode(m.text) for m in messages) if e is not None]
        arrivals = [i for i, e in enumerate(events) if e.type is EventType.ARRIVAL_ANNOUNCED]

        for index in reversed(arrivals):
            event = events[index]
            if event.host == self.host:
                continue
            later = events[index + 1 :]
            raw_stop = event.data.get("stop_id")
            stop_id = raw_stop if isinstance(raw_stop, str) else None
            immediate = index == arrivals[-1]
            released = next(
                (e for e in later if e.type is EventType.SOUL_RELEASED and e.host == event.host),
                None,
            )
            if released is not None:
                return PreviousStop(
                    host=event.host,
                    departure=str(released.data.get("departure", "graceful")),
                    stop_id=stop_id,
                    dwell_s=(released.ts - event.ts).total_seconds(),
                    immediate=immediate,
                )
            # No goodbye. The stop lasted until that host's last line.
            last_line = max((e.ts for e in later if e.host == event.host), default=event.ts)
            return PreviousStop(
                host=event.host,
                departure="abrupt",
                stop_id=stop_id,
                dwell_s=(last_line - event.ts).total_seconds(),
                immediate=immediate,
                already_cracked=any(
                    e.type is EventType.SHELL_PIECE_ADDED
                    and e.data.get("cracked_for_stop") == stop_id
                    for e in later
                ),
            )
        return PreviousStop()

    def _cracked_piece(self, previous: PreviousStop, context: dict[str, Any]) -> ShellPiece:
        """S3: the piece a lid slam leaves. Made here, cracked at one edge."""
        provider = (
            self._provider
            or context.get("brain_provider")
            or getattr(self._brain, "provider", None)
        )
        weather = context.get("weather")
        weather = weather if isinstance(weather, dict) else {}
        return make_piece(
            host=self.host,
            city=str(context.get("city") or "somewhere"),
            brain_provider=provider if provider in _PROVIDERS else "other",
            dwell_s=previous.dwell_s,
            departure="abrupt",
            created_at=self._clock.now(),
            temp_c=weather.get("temp_c"),
            weather_code=weather.get("code"),
        )

    async def _write(self, event_type: EventType, **data: object) -> None:
        """One event: on the bus for the critter, in the ledger for the journey."""
        event = Event(type=event_type, host=self.host, ts=self._clock.now(), data=data)
        await self._bus.publish(event)
        await self._room.post(self._ledger, encode(event))

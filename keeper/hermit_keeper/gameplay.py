"""Gameplay for a real keeper: favors, context, bedtime and the journal. Owner: Abhishek.

The simulation wires Phase 4 together by hand inside ``sim/runner.py``, with one
``FavorBook`` object shared by every simulated laptop. A real keeper has no such
luxury: three laptops, three processes, and the only thing they share is the
Switch room. This module is the real-world version of that wiring.

Three things it does that the sim never had to:

1. **Favors are rebuilt from the ledger.** A favor Afreen leaves lives in her
   keeper's memory until it reaches the room as a ``FAVOR_LEFT`` line. Every
   keeper folds those lines (and ``FAVOR_ASSIGNED`` / ``FAVOR_COMPLETED``) into
   its own book, so Abhishek's keeper can carry Afreen's favor without ever
   having seen her laptop. The fold is idempotent, keyed by event id.
2. **Favors are captured from the den.** After ``ASK_FAVOR`` the keeper watches
   the den for the host's next *human* message. An unsafe one is refused and the
   brain asks once more; the host is never nagged beyond that.
3. **Favors are completed from the den.** Once a carried favor is delivered, the
   host's next human message in the den is them doing it. That completes the
   favor, makes a shell piece, and writes both to the ledger and the bus so the
   critter grows its shell and the journey export can find it.

Privacy, deliberately: the arrival context carries the *number* of files in the
window folder, never their names. Cues travel through the ledger, which every
friend in the group can read, and the brain runs on the same laptop as the
folder — it can look for itself if the host asks.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import structlog

from .bedtime import is_bedtime
from .brain.base import BrainDirector
from .clock import Clock
from .context.weather import Weather
from .context.window import list_names
from .events import Event, EventBus, EventType
from .favors import Favor, FavorBook, check_safe, suggestions
from .journal import Journal
from .ledger import decode, encode
from .room.base import Message, RoomClient
from .shell_model import describe, make_piece

log = structlog.get_logger(__name__)

#: How often the den is re-read while waiting for a human. Cheap: the real
#: client answers ``history()`` from its local buffer.
POLL_S = 2.0

#: How often the favor book re-reads the ledger in the background. The real
#: room client only buffers the most recent few hundred lines per room, and
#: heartbeats fill that in well under an hour, so a keeper that only synced on
#: arrival would miss favors left long before. Syncing often keeps it current.
SYNC_S = 30.0

#: Cap on how long departure waits for a favor, whatever ``Handoff`` asks for.
#: The wait blocks a tick, and a tick blocked longer than ``presence.sleep_gap_s``
#: (90 s by default) would be read as the laptop having been asleep.
MAX_WAIT_S = 60.0

#: After this many refused favors, Hermit stops asking. Being asked to "try
#: again" a third time is nagging, and Hermit does not nag.
MAX_FAVOR_ATTEMPTS = 2

#: Senders that are machinery, not people. Brains are ``hermit-<host>`` and
#: keepers are ``keeper-<host>`` (plan §3.1); everything else in the den is a
#: friend, typing from a laptop or from Discord on a phone.
AGENT_PREFIXES = ("hermit-", "keeper-")


def is_human(message: Message, humans: set[str] | None = None) -> bool:
    """Is this den message from a person (and, if we know them, the right one)?"""
    if message.sender.startswith(AGENT_PREFIXES):
        return False
    if message.text.startswith(("HERMIT/1 ", "HERMIT-CUE/1", "HERMIT-ACK/1")):
        return False
    return humans is None or message.sender in humans


# -- favors ---------------------------------------------------------------------


@dataclass
class _Stop:
    """What a completion needs to know about the stop it happens in."""

    favor_id: str
    arrived_at: datetime
    city: str
    weather: dict[str, Any] | None


class LedgerFavors:
    """The real ``FavorStore`` for :class:`~hermit_keeper.handoff.Handoff`.

    Args:
        host: this keeper's ``host_id``.
        room: the keeper's room client. Read with ``history()`` only, so it
            never competes with the real client's single event-queue drain.
        brain: cued to re-ask after a refused favor and to celebrate a
            completed one.
        humans: den sender names that belong to this host's human. ``None``
            accepts any non-agent sender, which is right for a group where
            only the host is likely to answer within the window.
        snapshot: optional JSON file the book is saved to after every change
            and loaded from at start, so a restarted keeper still carries the
            favors it had folded before.
    """

    def __init__(
        self,
        host: str,
        room: RoomClient,
        brain: BrainDirector,
        clock: Clock,
        bus: EventBus | None = None,
        *,
        city: str = "",
        brain_provider: str = "other",
        local_hour: Callable[[], int] | None = None,
        den_room: str = "hermit-den",
        ledger_room: str = "hermit-ledger",
        humans: Iterable[str] | None = None,
        snapshot: Path | None = None,
        poll_s: float = POLL_S,
        sync_s: float = SYNC_S,
        max_wait_s: float = MAX_WAIT_S,
    ) -> None:
        self.host = host
        self._room = room
        self._brain = brain
        self._clock = clock
        self._bus = bus or EventBus()
        self._city = city
        self._provider = brain_provider
        self._local_hour = local_hour or (lambda: self._clock.now().hour)
        self._den = den_room
        self._ledger = ledger_room
        self._humans = set(humans) if humans is not None else None
        self._snapshot = snapshot
        self._poll_s = poll_s
        self._sync_s = sync_s
        self._max_wait_s = max_wait_s

        self.book = FavorBook(clock, room=den_room)
        self.shell_pieces: dict[str, dict[str, Any]] = {}
        self._seen_events: set[str] = set()
        self._stop: _Stop | None = None
        self._watcher: asyncio.Task[None] | None = None
        self._asked = 0
        self._load_snapshot()

    # -- the ledger fold -----------------------------------------------------

    async def sync(self) -> int:
        """Fold new favor lines from the ledger into the book. Returns how many."""
        try:
            messages = await self._room.history(self._ledger, limit=1000)
        except Exception:
            log.debug("favor sync could not read the ledger", host=self.host)
            return 0
        applied = 0
        for message in messages:
            event = decode(message.text)
            if event is not None:
                if event.type is EventType.SHELL_PIECE_ADDED:
                    piece = event.data.get("piece")
                    if isinstance(piece, dict) and isinstance(piece.get("id"), str):
                        if piece["id"] not in self.shell_pieces:
                            self.shell_pieces[piece["id"]] = piece
                            applied += 1
                elif self.apply(event):
                    applied += 1
        if applied:
            self._save_snapshot()
        return applied

    def apply(self, event: Event) -> bool:
        """Apply one ledger event to the book. Idempotent by event id."""
        if event.id in self._seen_events:
            return False
        if event.type not in (
            EventType.FAVOR_LEFT,
            EventType.FAVOR_ASSIGNED,
            EventType.FAVOR_COMPLETED,
        ):
            return False
        self._seen_events.add(event.id)
        data = event.data

        if event.type is EventType.FAVOR_LEFT:
            favor = _favor_from(data.get("favor"))
            if favor is None or favor.id in self.book.favors:
                return favor is not None
            self.book.favors[favor.id] = favor
            return True

        existing = self.book.favors.get(str(data.get("favor_id", "")))
        if existing is None:
            return False
        if event.type is EventType.FAVOR_ASSIGNED and existing.status == "open":
            existing.assignee = str(data.get("assignee") or event.host)
            existing.status = "assigned"
        elif event.type is EventType.FAVOR_COMPLETED and existing.status != "done":
            existing.status = "done"
            existing.assignee = existing.assignee or str(data.get("completed_by") or event.host)
            existing.completed_at = _iso(event.ts)
        return True

    async def run(self) -> None:
        """Keep the book current in the background until cancelled."""
        try:
            while True:
                await self.sync()
                await self._clock.sleep(self._sync_s)
        finally:
            self._cancel_watcher()

    # -- FavorStore: arrival -------------------------------------------------

    async def carried(self, for_host: str) -> dict[str, Any] | None:
        await self.sync()
        return await self.book.carried(for_host)

    async def pending_for(self, host: str) -> dict[str, Any] | None:
        """The favor delivered to this host, if one still needs doing."""
        await self.sync()
        for favor in self.book.favors.values():
            if favor.assignee == host and favor.status == "assigned":
                return favor.to_dict()
        return None

    async def shell(self) -> dict[str, Any]:
        await self.sync()
        return {"pieces": list(self.shell_pieces.values())}

    async def leave(self, text: str) -> dict[str, Any] | None:
        """Leave a favor explicitly from the desktop before Hermit departs."""
        await self.sync()
        if any(f.left_by == self.host and f.status == "open" for f in self.book.favors.values()):
            return None
        favor = await self.book.leave(self.host, text)
        if favor is None:
            return None
        await self._write(EventType.FAVOR_LEFT, favor=favor.to_dict())
        self._save_snapshot()
        return favor.to_dict()

    async def has_open_from(self, host: str) -> bool:
        await self.sync()
        return any(f.left_by == host and f.status == "open" for f in self.book.favors.values())

    async def assign(self, favor_id: str, host: str) -> None:
        """Called on arrival. Starts listening for the host doing the favor."""
        await self.book.assign(favor_id, host)
        self._save_snapshot()
        if host != self.host:
            return
        self._stop = _Stop(
            favor_id=favor_id,
            arrived_at=self._clock.now(),
            city=self._city,
            weather=None,
        )
        self._cancel_watcher()
        self._watcher = asyncio.create_task(self._watch_for_completion(favor_id))

    def note_weather(self, weather: dict[str, Any] | None) -> None:
        """The arrival weather, so the shell piece remembers the sky."""
        if self._stop is not None:
            self._stop.weather = weather

    # -- FavorStore: departure -----------------------------------------------

    async def ask_and_capture(self, timeout_s: float) -> dict[str, Any] | None:
        """Wait for the host to leave a favor in the den. ``None`` if they don't.

        Messages are told apart by id rather than timestamp: Switch stamps
        messages with the server's clock, and a laptop whose clock is a few
        seconds off would otherwise miss a reply that came straight back.
        """
        self._cancel_watcher()  # Hermit is leaving; the favor here is over.
        self._asked = 1
        try:
            seen = {m.id for m in await self._room.history(self._den, limit=500)}
        except Exception:
            log.info("favor capture could not read the den", host=self.host)
            return None
        deadline = self._clock.now().timestamp() + min(timeout_s, self._max_wait_s)

        while self._clock.now().timestamp() < deadline:
            await self._clock.sleep(self._poll_s)
            try:
                messages = await self._room.history(self._den, limit=500)
            except Exception:
                continue
            for message in messages:
                if message.id in seen:
                    continue
                seen.add(message.id)
                if not is_human(message, self._humans):
                    continue
                reason = check_safe(message.text)
                if reason is None:
                    favor = await self.book.leave(self.host, message.text)
                    self._save_snapshot()
                    return favor.to_dict() if favor else None
                if self._asked >= MAX_FAVOR_ATTEMPTS:
                    log.info("favor refused twice, letting it go", host=self.host)
                    return None
                self._asked += 1
                # The reason category only, never the text: the cue is a
                # ledger line every friend can read.
                await self._brain.cue(
                    "ASK_FAVOR",
                    {
                        "retry": True,
                        "refused_because": reason,
                        "suggestions": suggestions(len(self.book.favors) + self._asked),
                    },
                )
        return None

    # -- completion ----------------------------------------------------------

    async def _watch_for_completion(self, favor_id: str) -> None:
        """The host's next human message in the den is them doing the favor."""
        try:
            seen = {m.id for m in await self._room.history(self._den, limit=500)}
            while True:
                await self._clock.sleep(self._poll_s)
                favor = self.book.favors.get(favor_id)
                if favor is None or favor.status not in ("open", "assigned"):
                    return
                for message in await self._room.history(self._den, limit=500):
                    if message.id in seen:
                        continue
                    seen.add(message.id)
                    if is_human(message, self._humans) and message.text.strip():
                        await self.complete(favor_id)
                        return
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("favor completion watcher failed", host=self.host)

    async def complete(self, favor_id: str) -> dict[str, Any] | None:
        """Mark a favor done and grow the shell. Returns the new piece.

        Also the entry point for an explicit "I did it" (a critter button or a
        CLI command), so it is public and idempotent.
        """
        done = await self.book.complete(favor_id, self.host)
        if done is None:
            return None
        stop = self._stop if self._stop and self._stop.favor_id == favor_id else None
        now = self._clock.now()
        weather = stop.weather if stop else None
        made = make_piece(
            host=self.host,
            city=stop.city if stop else self._city,
            brain_provider=self._provider,
            dwell_s=(now - stop.arrived_at).total_seconds() if stop else 0,
            departure="graceful",
            created_at=now,
            favor_id=favor_id,
            temp_c=(weather or {}).get("temp_c"),
            weather_code=(weather or {}).get("code"),
        )
        piece = made.to_dict()
        await self._write(EventType.FAVOR_COMPLETED, favor_id=favor_id, completed_by=self.host)
        await self._write(EventType.SHELL_PIECE_ADDED, piece=piece)
        self.shell_pieces[piece["id"]] = piece
        self._save_snapshot()

        line = describe(made, local_hour=self._local_hour())
        await self._brain.cue("COMPLETE_FAVOR", {"favor_id": favor_id, "piece": line})
        return piece

    async def close(self) -> None:
        self._cancel_watcher()

    # -- internals -----------------------------------------------------------

    def _cancel_watcher(self) -> None:
        if self._watcher is not None and not self._watcher.done():
            self._watcher.cancel()
        self._watcher = None

    async def _write(self, event_type: EventType, **data: object) -> None:
        event = Event(type=event_type, host=self.host, ts=self._clock.now(), data=data)
        self._seen_events.add(event.id)
        await self._bus.publish(event)
        try:
            await self._room.post(self._ledger, encode(event))
        except Exception:
            log.warning("could not write favor line to the ledger", type=str(event_type))
            raise

    def _load_snapshot(self) -> None:
        if self._snapshot is None or not self._snapshot.exists():
            return
        try:
            raw = json.loads(self._snapshot.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for item in raw.get("favors", []):
            favor = _favor_from(item)
            if favor is not None:
                self.book.favors[favor.id] = favor
        for piece in raw.get("shell_pieces", []):
            if isinstance(piece, dict) and isinstance(piece.get("id"), str):
                self.shell_pieces[piece["id"]] = piece
        self._seen_events.update(str(e) for e in raw.get("seen_events", []))

    def _save_snapshot(self) -> None:
        if self._snapshot is None:
            return
        payload = {
            "favors": [f.to_dict() for f in self.book.favors.values()],
            "shell_pieces": list(self.shell_pieces.values()),
            "seen_events": sorted(self._seen_events)[-5000:],
        }
        with contextlib.suppress(OSError):
            self._snapshot.parent.mkdir(parents=True, exist_ok=True)
            self._snapshot.write_text(json.dumps(payload), encoding="utf-8")


_FAVOR_FIELDS = {f.name for f in fields(Favor)}


def _favor_from(raw: Any) -> Favor | None:
    if not isinstance(raw, dict):
        return None
    try:
        return Favor(**{k: v for k, v in raw.items() if k in _FAVOR_FIELDS})
    except TypeError:
        return None


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


# -- context --------------------------------------------------------------------


class LiveContext:
    """The real ``ContextProvider``: where Hermit landed and what the sky is doing."""

    def __init__(
        self,
        city: str,
        timezone: str,
        window_dir: str,
        weather: Weather | None,
        clock: Clock,
        favors: LedgerFavors | None = None,
    ) -> None:
        self._city = city
        self._zone = ZoneInfo(timezone)
        self._window_dir = window_dir
        self._weather = weather
        self._clock = clock
        self._favors = favors

    def local_now(self) -> datetime:
        return self._clock.now().astimezone(self._zone)

    async def arrival_context(self) -> dict[str, Any]:
        weather = await self._weather.current() if self._weather is not None else None
        if self._favors is not None:
            self._favors.note_weather(weather)
        local = self.local_now()
        context: dict[str, Any] = {
            "city": self._city,
            "local_time": local.isoformat(),
            "local_hour": local.hour,
            "weather": weather,
            # A count, never names: cues are ledger lines the whole group reads.
            "window_file_count": len(list_names(self._window_dir)),
        }
        if weather is not None:
            context["temp_c"] = weather["temp_c"]
        return context


# -- the journal ----------------------------------------------------------------


async def journal_events(bus: EventBus, journal: Journal) -> None:
    """Mirror every event this keeper emits to ``~/.hermit/journey.jsonl``."""
    async for event in bus.subscribe():
        journal.append(event)


# -- assembly -------------------------------------------------------------------


@dataclass
class Gameplay:
    """Everything Phase 4 adds to a keeper, ready to hand to ``KeeperRuntime``."""

    favors: LedgerFavors
    context: LiveContext
    is_bedtime: Callable[[datetime], bool]
    journal: Journal | None
    bus: EventBus
    _tasks: list[asyncio.Task[None]] = field(default_factory=list)

    def runtime_kwargs(self) -> dict[str, Any]:
        """``KeeperRuntime(..., **gameplay.runtime_kwargs())``."""
        return {"favors": self.favors, "context": self.context, "is_bedtime": self.is_bedtime}

    def companions(self) -> list[Callable[[], Coroutine[Any, Any, None]]]:
        """Background jobs for ``KeeperRuntime(companions=...)``: they start and
        stop with the keeper's tick loop."""
        jobs: list[Callable[[], Coroutine[Any, Any, None]]] = [self.favors.run]
        journal = self.journal
        if journal is not None:
            jobs.append(lambda: journal_events(self.bus, journal))
        return jobs

    def start(self) -> None:
        """Run the companions without a runtime (tests, scripts)."""
        self._tasks = [asyncio.create_task(job()) for job in self.companions()]

    async def stop(self) -> None:
        await self.favors.close()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []


def build_gameplay(
    config: Any,
    room: RoomClient,
    brain: BrainDirector,
    clock: Clock,
    bus: EventBus,
    *,
    state_dir: Path | None = None,
    persist: bool = True,
    weather: bool = True,
    weather_client: Any = None,
    poll_s: float = POLL_S,
    favor_wait_s: float = MAX_WAIT_S,
) -> Gameplay:
    """Assemble favors, context, bedtime and the journal for one real keeper.

    ``config`` is a :class:`~hermit_keeper.config.HostConfig`. Typed loosely so
    this module does not have to change when that one grows.

    ``persist=False`` keeps everything in memory: no favor snapshot and no
    journal, which is what tests and the one-machine stand-in demo want.
    ``weather=False`` never calls Open-Meteo.
    """
    home = state_dir or Path.home() / ".hermit"
    zone = ZoneInfo(config.timezone)
    humans = getattr(config, "human_names", None)
    favors = LedgerFavors(
        config.host_id,
        room,
        brain,
        clock,
        bus,
        city=config.city,
        brain_provider=config.brain_provider,
        local_hour=lambda: clock.now().astimezone(zone).hour,
        den_room=config.switch.den_room,
        ledger_room=config.switch.ledger_room,
        humans=humans,
        snapshot=home / f"favors-{config.host_id}.json" if persist else None,
        poll_s=poll_s,
        max_wait_s=favor_wait_s,
    )
    context = LiveContext(
        config.city,
        config.timezone,
        config.window_dir,
        Weather(config.lat, config.lon, clock, client=weather_client) if weather else None,
        clock,
        favors=favors,
    )
    start, end = config.bedtime.start, config.bedtime.end

    def bedtime_now(now: datetime) -> bool:
        # The state machine hands us UTC; bedtime is in the host's own hours.
        return is_bedtime(now.astimezone(zone), start, end)

    return Gameplay(
        favors=favors,
        context=context,
        is_bedtime=bedtime_now,
        journal=Journal(home / "journey.jsonl") if persist else None,
        bus=bus,
    )

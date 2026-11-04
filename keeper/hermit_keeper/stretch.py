"""Runs the opt-in stretch features (S1 overlap, S2 nudge) inside a keeper.

``overlap.py`` and ``nudge.py`` are pure; this is the impure part around them:
it reads the shared ledger for the group's memory, decides *when* to ask them,
cues the brain and writes the result back to the ledger.

The same class runs in the real keeper (``runtime.py``) and in the fake sim,
so the sim exercises exactly the code the pilot runs.

Two rules keep it from becoming a notification machine:

* **Only the soul holder acts.** Hermit can only speak where it is, and there
  is exactly one holder, so three laptops never suggest the same thing three
  times.
* **The ledger is the memory.** Every suggestion and nudge is written there,
  and every keeper reads them back, so the rate limits hold across laptops and
  across whoever holds the soul next.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from .brain.base import BrainDirector
from .clock import Clock
from .events import Event, EventBus, EventType
from .favors import suggestions
from .ids import new_id
from .ledger import decode, encode
from .nudge import NudgeParams, choose_nudge
from .overlap import (
    HostSchedule,
    OverlapParams,
    PresenceHistory,
    choose_suggestion,
    find_windows,
    local_span,
)
from .room.base import RoomClient

log = structlog.get_logger(__name__)

#: How often the holder re-evaluates. Routines move in half-hours; there is no
#: point doing this every tick.
CHECK_EVERY_S = 300.0

#: Re-read this much before the cursor, so lines posted in the same second as
#: the last read are not missed. Duplicates are dropped by event id.
_REREAD_S = 2.0

_PRESENCE_EVENTS = (EventType.HOST_HEARTBEAT, EventType.PRESENCE_CHANGED)
_HOSTING_EVENTS = (EventType.ARRIVAL_ANNOUNCED, EventType.SOUL_CLAIMED, EventType.SOUL_RELEASED)


class StretchRunner:
    """Args:
    host: this keeper's host id.
    overlap / nudge: the feature flags. With both off, ``tick`` does nothing.
    schedule: this host's timezone and bedtime.
    schedules: other hosts' schedules, if known. The real keeper only knows its
        own config, so the others fall back to ``schedule``'s timezone with the
        default 01:00-06:00 bedtime. The sim knows everyone's.
    known_hosts: the group, so a friend who has never checked in can still be
        found quiet.
    """

    def __init__(
        self,
        host: str,
        room: RoomClient,
        brain: BrainDirector,
        clock: Clock,
        bus: EventBus | None = None,
        *,
        overlap: bool = False,
        nudge: bool = False,
        ledger_room: str = "hermit-ledger",
        schedule: HostSchedule | None = None,
        schedules: Mapping[str, HostSchedule] | None = None,
        known_hosts: list[str] | None = None,
        overlap_params: OverlapParams | None = None,
        nudge_params: NudgeParams | None = None,
        check_every_s: float = CHECK_EVERY_S,
    ) -> None:
        self.host = host
        self.overlap = overlap
        self.nudge = nudge
        self._room = room
        self._brain = brain
        self._clock = clock
        self._bus = bus or EventBus()
        self._ledger = ledger_room
        self.schedule = schedule or HostSchedule()
        self._schedules: dict[str, HostSchedule] = dict(schedules or {})
        self._schedules.setdefault(host, self.schedule)
        self.overlap_params = overlap_params or OverlapParams()
        self.nudge_params = nudge_params or NudgeParams()
        self.check_every_s = check_every_s

        self.presence = PresenceHistory(self.overlap_params.stale_after_s)
        self.hosts: set[str] = set(known_hosts or []) | {host}
        self.last_hosted: dict[str, float] = {}
        self.past_overlaps: list[tuple[tuple[str, ...], float]] = []
        self.past_nudges: list[tuple[str, float]] = []
        self.history_start = clock.now().timestamp()

        self._last_check: float | None = None
        self._cursor: datetime | None = None
        self._seen: dict[str, datetime] = {}

    @property
    def enabled(self) -> bool:
        return self.overlap or self.nudge

    # -- the tick ------------------------------------------------------------

    async def tick(self, *, holding: bool, present: bool) -> list[Event]:
        """Call once per keeper tick. Returns whatever it emitted."""
        if not self.enabled:
            return []
        now = self._clock.now().timestamp()
        # Our own presence comes straight from the keyboard, every tick: it is
        # the one host whose history we never have to read back.
        self.presence.observe(self.host, now, present)
        if holding:
            self.last_hosted[self.host] = now

        if self._last_check is not None and now - self._last_check < self.check_every_s:
            return []
        self._last_check = now
        await self.read_ledger()
        if not holding:
            return []

        emitted: list[Event] = []
        if self.overlap:
            event = await self._maybe_suggest_overlap(now)
            if event is not None:
                emitted.append(event)
        if self.nudge:
            event = await self._maybe_nudge(now)
            if event is not None:
                emitted.append(event)
        return emitted

    # -- the group's memory --------------------------------------------------

    async def read_ledger(self) -> None:
        since = self._cursor - timedelta(seconds=_REREAD_S) if self._cursor else None
        try:
            messages = await self._room.history(self._ledger, since=since, limit=500)
        except Exception:
            log.debug("stretch could not read the ledger", host=self.host)
            return
        for message in messages:
            event = decode(message.text)
            if event is None or event.id in self._seen:
                continue
            self._seen[event.id] = message.ts
            self.observe(event)
            if self._cursor is None or message.ts > self._cursor:
                self._cursor = message.ts
        if self._cursor is not None:
            horizon = self._cursor - timedelta(seconds=10 * _REREAD_S)
            self._seen = {k: v for k, v in self._seen.items() if v >= horizon}

    def observe(self, event: Event) -> None:
        """Fold one ledger event into what the stretch features remember."""
        ts = event.ts.timestamp()
        self.hosts.add(event.host)
        self.history_start = min(self.history_start, ts)
        data = event.data

        if event.type in _PRESENCE_EVENTS and event.host != self.host:
            present = data.get("present")
            if isinstance(present, bool):
                self.presence.observe(event.host, ts, present)
        elif event.type in _HOSTING_EVENTS:
            self.last_hosted[event.host] = max(ts, self.last_hosted.get(event.host, ts))
        elif event.type is EventType.OVERLAP_SUGGESTED:
            hosts = data.get("hosts")
            if isinstance(hosts, list):
                self._remember_overlap(tuple(str(h) for h in hosts), ts)
        elif event.type is EventType.NUDGE_SENT:
            target = data.get("target_host")
            if isinstance(target, str):
                self._remember_nudge(target, ts)

    def _remember_overlap(self, hosts: tuple[str, ...], ts: float) -> None:
        if (hosts, ts) not in self.past_overlaps:
            self.past_overlaps.append((hosts, ts))

    def _remember_nudge(self, target: str, ts: float) -> None:
        if (target, ts) not in self.past_nudges:
            self.past_nudges.append((target, ts))

    # -- S1 ------------------------------------------------------------------

    async def _maybe_suggest_overlap(self, now: float) -> Event | None:
        history = {h: self.presence.intervals(h, now) for h in self.presence.hosts()}
        windows = find_windows(
            history,
            now,
            self._schedules,
            self.overlap_params,
            history_start=self.history_start,
            default_schedule=HostSchedule(timezone=self.schedule.timezone),
        )
        window = choose_suggestion(
            windows, now, self.past_overlaps, self.overlap_params, involving=self.host
        )
        if window is None:
            return None
        other = window.hosts[0] if window.hosts[1] == self.host else window.hosts[1]
        ovl_id = new_id("ovl")
        self._remember_overlap(window.hosts, now)
        event = await self._write(
            EventType.OVERLAP_SUGGESTED,
            ovl_id=ovl_id,
            hosts=list(window.hosts),
            window_start=_iso(window.start_dt()),
            window_end=_iso(window.end_dt()),
        )
        await self._brain.cue(
            "SUGGEST_OVERLAP",
            {
                "ovl_id": ovl_id,
                "hosts": list(window.hosts),
                "other_host": other,
                "window_start": _iso(window.start_dt()),
                "window_end": _iso(window.end_dt()),
                "window_local": local_span(window, self.schedule.timezone),
            },
        )
        log.info("overlap suggested", host=self.host, other=other)
        return event

    # -- S2 ------------------------------------------------------------------

    async def _maybe_nudge(self, now: float) -> Event | None:
        friend = choose_nudge(
            self.hosts,
            self.last_hosted,
            self.history_start,
            now,
            self.past_nudges,
            holder=self.host,
            params=self.nudge_params,
        )
        if friend is None:
            return None
        self._remember_nudge(friend.host, now)
        event = await self._write(
            EventType.NUDGE_SENT,
            target_host=friend.host,
            days_since_hosted=friend.days,
            quiet_since=_iso(datetime.fromtimestamp(friend.quiet_since, tz=UTC)),
        )
        await self._brain.cue(
            "NUDGE_QUIET_FRIEND",
            {
                "target_host": friend.host,
                "days_since_hosted": friend.days,
                "never_hosted": friend.never_hosted,
                "suggestions": suggestions(int(now) // 3600),
            },
        )
        log.info("quiet-friend nudge", host=self.host, target=friend.host)
        return event

    # -- internals -----------------------------------------------------------

    async def _write(self, event_type: EventType, **data: Any) -> Event:
        event = Event(type=event_type, host=self.host, ts=self._clock.now(), data=data)
        self._seen[event.id] = event.ts
        await self._bus.publish(event)
        await self._room.post(self._ledger, encode(event))
        return event


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

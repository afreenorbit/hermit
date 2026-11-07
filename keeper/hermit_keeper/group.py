"""What every laptop in the group is doing, derived from the shared ledger.

Owner: Afreen. Phase 6/7.

A keeper knows its own presence from the keyboard, and the soul holder from
Switch. It knows nothing about the *other* laptops — and the critter on a
laptop that is not hosting still has to show something honest ("Hermit is with
Abhishek", not a blank screen or a guess).

The ledger room already carries everything needed, so this is a fold over it
rather than a new service: keepers post a small `HOST_HEARTBEAT` every few
seconds, and everyone reads the same room back.

**Two different ideas, deliberately kept apart:**

* *Who holds the soul* is shared state, owned by Switch. One answer for the
  whole group.
* *Whether a laptop is eligible to host* is local, from that machine's own
  keyboard and mouse. Three independent answers.

Mixing them is how you end up showing two laptops as Visiting, so they stay in
separate fields all the way to the UI.

**Silence is not absence.** A host whose heartbeat stopped is reported `stale`
with mood `offline` — we say we do not know, rather than guessing they left.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .events import Event, EventType

#: No heartbeat for this long and we stop believing what we last heard.
#: Three missed beats at the default 10 s cadence.
STALE_AFTER_S = 35.0

#: The six things a mascot can be doing. These are the `mood` values the API
#: returns and the names the UI renders directly.
MOODS = ("visiting", "arriving", "away", "sleeping", "waiting", "offline")


@dataclass
class HostView:
    """One laptop, as the rest of the group last saw it."""

    host_id: str
    state: str | None = None
    present: bool | None = None
    mood: str = "offline"
    last_seen: str | None = None
    stale: bool = True
    holding: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "host_id": self.host_id,
            "state": self.state,
            "present": self.present,
            "mood": self.mood,
            "last_seen": self.last_seen,
            "stale": self.stale,
            "holding": self.holding,
        }


#: How long after a successful claim the arrival plays before settling.
ARRIVING_WINDOW_S = 10.0


def mood_for(
    state: str | None,
    present: bool | None,
    holder: str | None,
    host: str,
    holding_for_s: float | None = None,
) -> str:
    """The mascot this laptop should be showing.

    Local state decides most of it; the holder decides the rest. A laptop that
    does not hold the soul can never be `visiting`, which is what stops two
    screens claiming Hermit at once.

    ``holding_for_s`` is how long this host has held the soul, and it separates
    *arriving* from *visiting*. Arriving is deliberately tied to a **successful
    claim**, not to reaching for one: when a soul frees, every awake laptop
    tries, and showing them all `arriving` would have Hermit apparently landing
    in two places at once. Only the winner arrives.
    """
    if state is None:
        return "offline"
    if state == "HOLDING":
        # Trust Switch over our own state if they disagree: the room is the
        # authority, and disagreeing here is exactly the double-Hermit bug.
        if holder not in (None, host):
            return "waiting"
        if holding_for_s is not None and holding_for_s < ARRIVING_WINDOW_S:
            return "arriving"
        return "visiting"
    if state == "CLAIMING":
        # Reaching for the soul, not holding it. Everyone who is awake does
        # this at the same moment; none of them has arrived anywhere yet.
        return "waiting"
    if state == "DEPARTING":
        return "away"
    if state == "BEDTIME_LOCK":
        return "sleeping"
    if state == "ASLEEP":
        return "sleeping" if present is False else "waiting"
    if state == "AWAKE_WAITING":
        return "waiting"
    return "offline"


class GroupView:
    """Everyone's last known state, folded from the ledger.

    Args:
        hosts: the host_ids we expect. Listing them up front means a laptop
            that has never checked in shows as `offline` rather than being
            missing from the dashboard entirely — a laptop you forgot to start
            is exactly what you want to see.
    """

    def __init__(self, hosts: list[str] | None = None) -> None:
        self._views: dict[str, HostView] = {h: HostView(host_id=h) for h in hosts or []}
        self.soul_holder: str | None = None

    # -- folding the ledger --------------------------------------------------

    def apply(self, event: Event) -> None:
        view = self._views.setdefault(event.host, HostView(host_id=event.host))
        data = event.data
        when = _iso(event.ts)
        # A delayed Switch queue item can arrive after this keeper's current
        # local heartbeat. Never let that older line make a live laptop look
        # stale again. Equal timestamps still apply in room order.
        if view.last_seen is not None and event.ts < datetime.fromisoformat(view.last_seen):
            return

        if event.type is EventType.HOST_HEARTBEAT:
            view.state = _str(data.get("state")) or view.state
            view.present = _bool(data.get("present"), view.present)
            view.last_seen = when

        elif event.type is EventType.PRESENCE_CHANGED:
            view.present = _bool(data.get("present"), view.present)
            view.last_seen = when

        elif event.type is EventType.SOUL_CLAIMED:
            self.soul_holder = _str(data.get("holder")) or event.host
            view.state = "HOLDING"
            view.last_seen = when

        elif event.type is EventType.SOUL_RELEASED:
            if self.soul_holder == event.host:
                self.soul_holder = None
            view.state = "ASLEEP"
            view.last_seen = when

        elif event.type is EventType.SOUL_FREE:
            self.soul_holder = None
            view.last_seen = when

        elif event.type is EventType.DEPARTURE_STARTED:
            view.state = "DEPARTING"
            view.last_seen = when

        elif event.type is EventType.BEDTIME_EVICTION:
            view.state = "BEDTIME_LOCK"
            view.last_seen = when

    def apply_all(self, events: list[Event]) -> None:
        for event in sorted(events, key=lambda e: (e.ts, e.id)):
            self.apply(event)

    # -- reading it back -----------------------------------------------------

    def snapshot(self, now: datetime, self_host: str | None = None) -> dict[str, Any]:
        """The shape `/v1/group` serves and the dashboard renders."""
        hosts: list[dict[str, Any]] = []
        for view in sorted(self._views.values(), key=lambda v: v.host_id):
            stale = _is_stale(view.last_seen, now)
            holding = (not stale) and self.soul_holder == view.host_id
            mood = (
                "offline"
                if stale
                else mood_for(view.state, view.present, self.soul_holder, view.host_id)
            )
            hosts.append(
                HostView(
                    host_id=view.host_id,
                    state=None if stale else view.state,
                    present=None if stale else view.present,
                    mood=mood,
                    last_seen=view.last_seen,
                    stale=stale,
                    holding=holding,
                ).to_dict()
            )

        # A holder we can no longer hear from is not a holder we can vouch for.
        holder = self.soul_holder
        if holder is not None and any(h["host_id"] == holder and h["stale"] for h in hosts):
            holder = None

        return {
            "v": 1,
            "generated_at": _iso(now),
            "self": self_host,
            "soul_holder": holder,
            "hosts": hosts,
        }


def _is_stale(last_seen: str | None, now: datetime) -> bool:
    if last_seen is None:
        return True
    try:
        seen = datetime.fromisoformat(last_seen)
    except ValueError:
        return True
    if seen.tzinfo is None or now.tzinfo is None:
        return False
    return now - seen > timedelta(seconds=STALE_AFTER_S)


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _bool(value: Any, fallback: bool | None) -> bool | None:
    return value if isinstance(value, bool) else fallback


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")

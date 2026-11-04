"""Stretch S1: find rare windows when two friends are both around. Opt-in.

Spec: plan.md 4.6. Off unless ``features.overlap`` is set.

Three friends in one city rarely sit at their laptops at the same time, which
is half of why Hermit exists. When the presence history shows that two of them
*usually* overlap for a short stretch, Hermit can say so — "you're both around
at nine tonight, call?" — and that is the one moment it actively tries to put
two people in the same place.

Everything in this module is pure and deterministic: presence history in,
windows out. No clock, no I/O, no ids. ``stretch.py`` does the impure part
(reading the ledger, cueing the brain, writing ``OVERLAP_SUGGESTED``).

The model, kept deliberately small:

1. **History.** Each host's presence as ``[start, end)`` intervals in epoch
   seconds, folded from ``HOST_HEARTBEAT`` / ``PRESENCE_CHANGED`` ledger lines.
2. **Routine.** For each 30-minute slot of the (UTC) day, the fraction of the
   last ``lookback_days`` on which the host was present for at least half of
   that slot. That is ``p``.
3. **Windows.** Over the next ``horizon_s``, runs of slots where both hosts have
   ``p >= threshold`` and **neither is inside their bedtime**, at least
   ``min_window_s`` long.
4. **Rare.** A pair that already overlaps for more than ``max_daily_overlap_s``
   a day does not need a crab's help and is skipped.
5. **Gentle.** At most one suggestion per pair per ``cooldown_s``, and none
   within ``min_gap_s`` of the last one for anybody; the pair that has waited
   longest goes first.

A day-of-week model (plan.md said hour-of-week) was dropped on purpose: seven
days of history gives a weekly slot exactly one sample, which is noise, while a
daily slot gets seven.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import combinations
from zoneinfo import ZoneInfo

from .bedtime import is_bedtime

DAY_S = 86400

#: ``[start, end)`` in epoch seconds.
Interval = tuple[float, float]
Pair = tuple[str, str]


@dataclass(frozen=True)
class OverlapParams:
    """Every knob, with the plan's defaults."""

    #: Width of one routine slot. Must divide a day.
    slot_s: int = 1800
    #: How far back the routine looks.
    lookback_days: int = 7
    #: Below this much group history, say nothing: one afternoon is not a routine.
    min_history_s: float = 24 * 3600
    #: Both hosts must usually be present in a slot for it to count.
    threshold: float = 0.6
    #: Shorter than this is not worth a call.
    min_window_s: float = 1800
    #: Only suggest windows starting within this long from now.
    horizon_s: float = 24 * 3600
    #: Never suggest the same pair twice within this long.
    cooldown_s: float = 3 * DAY_S
    #: Group-wide: no two suggestions (any pairs) closer together than this.
    min_gap_s: float = 6 * 3600
    #: Pairs that usually overlap more than this a day are not "rare".
    max_daily_overlap_s: float = 6 * 3600
    #: A host silent for longer than this is treated as absent, not present.
    stale_after_s: float = 3600

    def __post_init__(self) -> None:
        if self.slot_s <= 0 or DAY_S % self.slot_s:
            raise ValueError("slot_s must be a positive divisor of a day")


@dataclass(frozen=True)
class HostSchedule:
    """Where a host's clock is and when they should be asleep."""

    timezone: str = "Asia/Kolkata"
    bedtime_start: str = "01:00"
    bedtime_end: str = "06:00"

    def overlaps_bedtime(self, start: float, end: float) -> bool:
        """Does ``[start, end)`` touch this host's bedtime at all?

        Exact rather than sampled: either the window opens inside bedtime, or
        bedtime begins before the window closes.
        """
        if end <= start:
            return False
        zone = ZoneInfo(self.timezone)
        local_start = datetime.fromtimestamp(start, tz=UTC).astimezone(zone)
        if is_bedtime(local_start, self.bedtime_start, self.bedtime_end):
            return True
        hour, _, minute = self.bedtime_start.partition(":")
        onset = local_start.replace(
            hour=int(hour), minute=int(minute or 0), second=0, microsecond=0
        )
        if onset <= local_start:
            onset += timedelta(days=1)
        return onset.timestamp() < end


@dataclass(frozen=True)
class Window:
    """Two friends, both usually around, neither past their bedtime."""

    hosts: Pair
    start: float
    end: float
    #: How much these two usually overlap in a whole day. Smaller is rarer.
    daily_overlap_s: float

    @property
    def duration_s(self) -> float:
        return self.end - self.start

    def start_dt(self) -> datetime:
        return datetime.fromtimestamp(self.start, tz=UTC)

    def end_dt(self) -> datetime:
        return datetime.fromtimestamp(self.end, tz=UTC)


class PresenceHistory:
    """Each host's presence as change points. Feed it observations in order.

    Heartbeats arrive every few seconds; storing them all for a week would be
    silly, so only the moments presence *changes* are kept, plus when each host
    was last heard from. A gap in heartbeats longer than ``stale_after_s`` is
    recorded as absence: a laptop that was switched off was not "present" all
    night just because it said so before it died.
    """

    def __init__(self, stale_after_s: float = 3600) -> None:
        self.stale_after_s = stale_after_s
        self._points: dict[str, list[tuple[float, bool]]] = {}
        self._last_seen: dict[str, float] = {}
        #: Earliest observation of anyone. The start of the group's history.
        self.first_seen: float | None = None

    def observe(self, host: str, ts: float, present: bool) -> None:
        last = self._last_seen.get(host)
        if last is not None and ts < last:
            return  # out of order: the newer observation already won
        points = self._points.setdefault(host, [])
        if last is not None and points and points[-1][1] and ts - last > self.stale_after_s:
            points.append((last + self.stale_after_s, False))
        if not points or points[-1][1] != present:
            points.append((ts, present))
        self._last_seen[host] = ts
        if self.first_seen is None or ts < self.first_seen:
            self.first_seen = ts

    def hosts(self) -> list[str]:
        return sorted(self._points)

    def intervals(self, host: str, until: float) -> list[Interval]:
        """Present intervals up to ``until``. The last one is capped by staleness."""
        points = self._points.get(host, [])
        last_seen = self._last_seen.get(host, until)
        out: list[Interval] = []
        for index, (ts, present) in enumerate(points):
            if not present or ts >= until:
                continue
            if index + 1 < len(points):
                end = points[index + 1][0]
            else:
                end = last_seen + self.stale_after_s
            end = min(end, until)
            if end > ts:
                out.append((ts, end))
        return out


# -- the model ---------------------------------------------------------------


def _covered(intervals: list[Interval], start: float, end: float) -> float:
    total = 0.0
    for a, b in intervals:
        if b <= start:
            continue
        if a >= end:
            break
        total += min(b, end) - max(a, start)
    return total


def slot_probabilities(
    intervals: Iterable[Interval], start: float, end: float, slot_s: int = 1800
) -> dict[int, float]:
    """Slot-of-day index -> fraction of observed days the host was there.

    Only whole slots inside ``[start, end)`` count. A host is "there" for a
    slot if present for at least half of it.
    """
    ordered = sorted(intervals)
    seen: dict[int, int] = {}
    hits: dict[int, int] = {}
    slot = math.ceil(start / slot_s) * slot_s
    while slot + slot_s <= end:
        index = int(slot % DAY_S) // slot_s
        seen[index] = seen.get(index, 0) + 1
        if _covered(ordered, slot, slot + slot_s) * 2 >= slot_s:
            hits[index] = hits.get(index, 0) + 1
        slot += slot_s
    return {index: hits.get(index, 0) / count for index, count in seen.items()}


def find_windows(
    history: Mapping[str, Iterable[Interval]],
    now: float,
    schedules: Mapping[str, HostSchedule] | None = None,
    params: OverlapParams | None = None,
    *,
    history_start: float | None = None,
    default_schedule: HostSchedule | None = None,
) -> list[Window]:
    """Every upcoming window, for every pair, earliest first.

    Args:
        history: each host's present intervals (epoch seconds).
        now: epoch seconds.
        schedules: each host's timezone and bedtime. Hosts missing here get
            ``default_schedule``.
        history_start: when the group's history begins. Defaults to the
            earliest interval. Absence leaves no intervals, so pass it when
            you know it.
    """
    params = params or OverlapParams()
    schedules = schedules or {}
    fallback = default_schedule or HostSchedule()
    by_host = {host: sorted(spans) for host, spans in history.items()}

    if history_start is None:
        starts = [spans[0][0] for spans in by_host.values() if spans]
        if not starts:
            return []
        history_start = min(starts)
    observed_from = max(now - params.lookback_days * DAY_S, history_start)
    if now - observed_from < params.min_history_s:
        return []

    slot_s = params.slot_s
    probs = {
        host: slot_probabilities(spans, observed_from, now, slot_s)
        for host, spans in by_host.items()
    }

    windows: list[Window] = []
    for a, b in combinations(sorted(by_host), 2):
        both = {
            index
            for index, p in probs[a].items()
            if p >= params.threshold and probs[b].get(index, 0.0) >= params.threshold
        }
        if not both:
            continue
        daily = len(both) * slot_s
        if daily > params.max_daily_overlap_s:
            continue  # they see each other plenty already
        sched_a = schedules.get(a, fallback)
        sched_b = schedules.get(b, fallback)

        run_start: float | None = None
        slot = math.floor(now / slot_s) * slot_s
        last_slot = now + params.horizon_s
        while True:
            ok = (
                slot < last_slot
                and int(slot % DAY_S) // slot_s in both
                and not sched_a.overlaps_bedtime(slot, slot + slot_s)
                and not sched_b.overlaps_bedtime(slot, slot + slot_s)
            )
            if ok and run_start is None:
                run_start = slot
            elif not ok and run_start is not None:
                start = max(run_start, now)
                if slot - start >= params.min_window_s:
                    windows.append(Window((a, b), start, slot, daily))
                run_start = None
            if slot >= last_slot:
                break
            slot += slot_s
    return sorted(windows, key=lambda w: (w.start, w.hosts))


def choose_suggestion(
    windows: Iterable[Window],
    now: float,
    past: Iterable[tuple[Iterable[str], float]] = (),
    params: OverlapParams | None = None,
    *,
    involving: str | None = None,
) -> Window | None:
    """The one window worth mentioning now, or ``None``.

    Args:
        past: ``(hosts, when)`` of every earlier ``OVERLAP_SUGGESTED``.
        involving: only pairs that include this host — Hermit can only suggest
            a call to someone it is actually with.
    """
    params = params or OverlapParams()
    last: dict[Pair, float] = {}
    for hosts, when in past:
        pair = _pair(hosts)
        if pair is not None and when <= now:
            last[pair] = max(when, last.get(pair, -math.inf))
    if last and now - max(last.values()) < params.min_gap_s:
        return None  # one suggestion at a time; the den is not a calendar

    first: dict[Pair, Window] = {}
    for window in sorted(windows, key=lambda w: (w.start, w.hosts)):
        if involving is not None and involving not in window.hosts:
            continue
        if now - last.get(window.hosts, -math.inf) < params.cooldown_s:
            continue
        first.setdefault(window.hosts, window)
    if not first:
        return None
    # Longest-waiting pair first, then the rarer pair, then the sooner window.
    return min(
        first.values(),
        key=lambda w: (last.get(w.hosts, -math.inf), w.daily_overlap_s, w.start, w.hosts),
    )


def _pair(hosts: Iterable[str]) -> Pair | None:
    names = sorted(set(hosts))
    if len(names) != 2:
        return None
    return (names[0], names[1])


def local_span(window: Window, timezone: str) -> str:
    """``"21:00-22:00"`` in one host's own clock, for the brain to say."""
    zone = ZoneInfo(timezone)
    start = window.start_dt().astimezone(zone)
    end = window.end_dt().astimezone(zone)
    return f"{start:%H:%M}-{end:%H:%M}"

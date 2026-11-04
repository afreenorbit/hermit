"""The numbers for the README and the pilot write-up. Owner: D.

Computed from a ``journey.json`` (what ``scripts/export_journey.py`` writes)
and, when available, the raw ledger events it came from. Pure: data in, dict
out. ``python -m sim metrics`` is the command-line front end.

**Honesty rules, enforced here rather than remembered later:**

* Every result carries a ``source``. Anything from the fake sim is
  ``simulation`` and every rendering of it says SIMULATION in capitals.
* A number that cannot be measured from the data is ``None``, never a guess.
  The abrupt stop is the main case: nobody wrote down when the lid came down,
  so it is left out of handoff latency instead of being made up.

Definitions:

* **Stop** — one visit (one ``ARRIVAL_ANNOUNCED``).
* **Handoff** — consecutive stops on *different* laptops.
* **Handoff latency** — release -> next claim, for handoffs where somebody was
  waiting. "Waiting" means the next host was present when the soul was let go
  (from heartbeats in the ledger); with no presence data, a gap of at most
  ``hot_gap_s`` stands in for it. A handoff where nobody was awake is not
  latency, it is the group being asleep — that time is in
  ``nobody_hosting``. The claim time is the ``SOUL_CLAIMED`` event when the
  data has one, else the arrival announcement a moment later (an upper bound).
* **Percentiles** — nearest rank, so every reported value is one that happened.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any, Literal

from .events import Event, EventType
from .overlap import PresenceHistory

Source = Literal["simulation", "real"]

#: Without presence data, a handoff this quick counts as "somebody was waiting".
HOT_GAP_S = 600.0

#: How long a heartbeat is believed when deciding if the next host was waiting.
PRESENCE_STALE_S = 3600.0

DEPARTURES = ("graceful", "abrupt", "bedtime", "manual", "present")

DWELL_BUCKETS: list[tuple[str, float]] = [
    ("<15m", 15 * 60),
    ("15m-1h", 3600),
    ("1h-3h", 3 * 3600),
    ("3h-8h", 8 * 3600),
    (">=8h", math.inf),
]


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile. ``None`` for no data."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def dedupe(events: Iterable[Event]) -> list[Event]:
    """Oldest first, each event id once. Merged journals repeat lines."""
    seen: set[str] = set()
    out: list[Event] = []
    for event in sorted(events, key=lambda e: (e.ts, e.id)):
        if event.id not in seen:
            seen.add(event.id)
            out.append(event)
    return out


def compute(
    journey: dict[str, Any],
    events: Iterable[Event] | None = None,
    *,
    hot_gap_s: float = HOT_GAP_S,
) -> dict[str, Any]:
    """Every metric for one journey. ``events`` sharpens several of them."""
    evs = dedupe(events) if events is not None else None
    stops = sorted(journey.get("stops") or [], key=lambda s: s.get("seq", 0))
    obs_end = _observation_end(journey, stops, evs)

    return {
        "stops": len(stops),
        "handoffs": sum(1 for a, b in itertools.pairwise(stops) if a["host"] != b["host"]),
        "handoff_latency_s": handoff_latency(stops, evs, hot_gap_s=hot_gap_s),
        "dwell_s": dwell(stops, evs),
        "departures": departures(stops),
        "favors": favors(journey, evs),
        "nobody_hosting": nobody_hosting(stops, evs, obs_end),
        "brains": brains(journey, stops),
        "shell_pieces": len(journey.get("shell") or []),
        "cracked_pieces": sum(
            1 for p in journey.get("shell") or [] if p.get("departure") == "abrupt"
        ),
        "overlaps_suggested": _count(evs, EventType.OVERLAP_SUGGESTED)
        if evs is not None
        else (journey.get("stats") or {}).get("overlaps_suggested"),
        "nudges_sent": _count(evs, EventType.NUDGE_SENT) if evs is not None else None,
        "has_events": evs is not None,
    }


# -- individual metrics ------------------------------------------------------


def handoff_latency(
    stops: Sequence[dict[str, Any]],
    events: Sequence[Event] | None = None,
    *,
    hot_gap_s: float = HOT_GAP_S,
) -> dict[str, Any]:
    samples, cold, excluded_abrupt, has_presence = _latencies(stops, events, hot_gap_s)
    return {
        **_summary(samples),
        "method": "presence" if has_presence else f"gap<={int(hot_gap_s)}s",
        "cold_handoffs": cold,
        "excluded_abrupt": excluded_abrupt,
    }


def latency_samples(
    stops: Sequence[dict[str, Any]],
    events: Sequence[Event] | None = None,
    *,
    hot_gap_s: float = HOT_GAP_S,
) -> list[float]:
    """The raw values behind ``handoff_latency``, for pooling across runs."""
    return _latencies(stops, events, hot_gap_s)[0]


def _latencies(
    stops: Sequence[dict[str, Any]], events: Sequence[Event] | None, hot_gap_s: float
) -> tuple[list[float], int, int, bool]:
    """(samples, cold handoffs, abrupt handoffs left out, used presence?)"""
    presence = _presence(events)
    samples: list[float] = []
    cold = 0
    excluded_abrupt = 0
    for a, b in itertools.pairwise(stops):
        if a["host"] == b["host"]:
            continue
        if a.get("departure") == "abrupt" or not a.get("left_at"):
            excluded_abrupt += 1  # nobody recorded when the lid came down
            continue
        release = _ts(a["left_at"])
        gap = max(0.0, _claim_time(b, release, events) - release)
        waiting = _was_present(presence, b["host"], release)
        if waiting is None:
            waiting = gap <= hot_gap_s
        if waiting:
            samples.append(gap)
        else:
            cold += 1
    return samples, cold, excluded_abrupt, presence is not None


def dwell(stops: Sequence[dict[str, Any]], events: Sequence[Event] | None = None) -> dict[str, Any]:
    values: list[float] = []
    for stop in stops:
        end = _stop_end(stop, events)
        if end is not None:
            values.append(max(0.0, end - _ts(stop["arrived_at"])))
    buckets = {name: 0 for name, _ in DWELL_BUCKETS}
    for value in values:
        name = next(n for n, limit in DWELL_BUCKETS if value < limit)
        buckets[name] += 1
    summary = _summary(values)
    summary["mean"] = round(sum(values) / len(values), 1) if values else None
    summary["buckets"] = buckets
    return summary


def departures(stops: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {name: 0 for name in DEPARTURES}
    for stop in stops:
        kind = str(stop.get("departure") or "present")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def favors(journey: dict[str, Any], events: Sequence[Event] | None = None) -> dict[str, Any]:
    if events is not None:
        left_ids = {
            str((e.data.get("favor") or {}).get("id"))
            for e in events
            if e.type is EventType.FAVOR_LEFT and (e.data.get("favor") or {}).get("id")
        }
        done_ids = {
            str(e.data.get("favor_id"))
            for e in events
            if e.type is EventType.FAVOR_COMPLETED and e.data.get("favor_id")
        }
        left, done = len(left_ids), len(done_ids & left_ids)
    else:
        stats = journey.get("stats") or {}
        left, done = int(stats.get("favors_left") or 0), int(stats.get("favors_done") or 0)
    return {
        "left": left,
        "completed": done,
        "completion_rate": round(done / left, 3) if left else None,
    }


def nobody_hosting(
    stops: Sequence[dict[str, Any]],
    events: Sequence[Event] | None,
    obs_end: float | None,
) -> dict[str, Any]:
    """Time between the first arrival and the end of the data with no host."""
    if not stops or obs_end is None:
        return {"total_s": None, "longest_s": None, "observed_s": None, "fraction": None}
    start = _ts(stops[0]["arrived_at"])
    gaps: list[float] = []
    for a, b in itertools.pairwise(stops):
        end = _stop_end(a, events)
        if end is not None:
            gaps.append(max(0.0, _ts(b["arrived_at"]) - end))
    last_end = _stop_end(stops[-1], events)
    if last_end is not None and stops[-1].get("departure") != "present":
        gaps.append(max(0.0, obs_end - last_end))
    observed = max(0.0, obs_end - start)
    total = sum(gaps)
    return {
        "total_s": round(total, 1),
        "longest_s": round(max(gaps), 1) if gaps else 0.0,
        "observed_s": round(observed, 1),
        "fraction": round(total / observed, 3) if observed else None,
    }


def brains(journey: dict[str, Any], stops: Sequence[dict[str, Any]]) -> dict[str, Any]:
    provider = {h["host_id"]: h.get("brain_provider") for h in journey.get("hosts") or []}
    for piece in journey.get("shell") or []:
        provider.setdefault(piece.get("host", ""), piece.get("brain_provider"))
    visited = sorted({s["host"] for s in stops})
    providers = sorted({str(provider[h]) for h in visited if provider.get(h)})
    return {
        "distinct": len(providers),
        "providers": providers,
        "hosts_visited": visited,
        "unknown_hosts": [h for h in visited if not provider.get(h)],
    }


# -- rendering ---------------------------------------------------------------


def label(source: str) -> str:
    return "SIMULATION" if source == "simulation" else "REAL"


def render_markdown(results: Sequence[dict[str, Any]], pooled: dict[str, Any] | None = None) -> str:
    """One table, one row per dataset. ``results`` items: name, source, metrics."""
    sources = {r["source"] for r in results}
    lines: list[str] = []
    if "simulation" in sources:
        lines.append(
            "> **SIMULATION** - rows marked SIMULATION come from the fake sim "
            "(`python -m sim all`): scripted presence, fake Switch, fast-forwarded "
            "on one machine. They show the code works, not that people used it. "
            "They are **not** pilot results."
        )
    if "real" in sources:
        lines.append("> Rows marked REAL were computed from a real ledger/journey export.")
    lines.append("")
    lines.append(
        "| Dataset | Source | Stops | Handoffs | Handoff latency p50 / p95 / max (n) "
        "| Dwell p50 / max | Departures g / a / b / m | Favors left -> done (rate) "
        "| Nobody hosting (longest) | Brains | Overlaps | Nudges |"
    )
    lines.append("|" + "---|" * 12)
    for row in results:
        m = row["metrics"]
        lat = m["handoff_latency_s"]
        dw = m["dwell_s"]
        dep = m["departures"]
        fav = m["favors"]
        gap = m["nobody_hosting"]
        rate = f"{fav['completion_rate']:.0%}" if fav["completion_rate"] is not None else "n/a"
        lines.append(
            "| "
            + " | ".join(
                [
                    row["name"],
                    f"**{label(row['source'])}**",
                    str(m["stops"]),
                    str(m["handoffs"]),
                    f"{_dur(lat['p50'])} / {_dur(lat['p95'])} / {_dur(lat['max'])} ({lat['n']})",
                    f"{_dur(dw['p50'])} / {_dur(dw['max'])}",
                    f"{dep['graceful']} / {dep['abrupt']} / {dep['bedtime']} / {dep['manual']}",
                    f"{fav['left']} -> {fav['completed']} ({rate})",
                    f"{_dur(gap['total_s'])} ({_dur(gap['longest_s'])})",
                    str(m["brains"]["distinct"]),
                    _opt(m["overlaps_suggested"]),
                    _opt(m["nudges_sent"]),
                ]
            )
            + " |"
        )
    if pooled:
        for source, summary in sorted(pooled.items()):
            lines.append("")
            lines.append(
                f"**Pooled handoff latency, {label(source)}** (n={summary['n']}): "
                f"p50 {_dur(summary['p50'])}, p95 {_dur(summary['p95'])}, "
                f"max {_dur(summary['max'])}."
            )
    lines.append("")
    lines.append(
        "Latency = release -> next claim, only where the next friend was already "
        "waiting; abrupt departures are excluded (nobody recorded when the lid came "
        "down). Percentiles are nearest-rank. Departures: graceful / abrupt / "
        "bedtime / manual."
    )
    return "\n".join(lines) + "\n"


def pool_latency(results: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Latency samples pooled per source. Never pools simulation with real."""
    by_source: dict[str, list[float]] = {}
    for row in results:
        by_source.setdefault(row["source"], []).extend(row.get("latency_samples") or [])
    return {source: _summary(values) for source, values in by_source.items()}


# -- internals ---------------------------------------------------------------


def _summary(values: Sequence[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": max(values) if values else None,
        "min": min(values) if values else None,
    }


def _ts(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()


def _count(events: Sequence[Event] | None, kind: EventType) -> int | None:
    if events is None:
        return None
    return sum(1 for e in events if e.type is kind)


def _presence(events: Sequence[Event] | None) -> PresenceHistory | None:
    """When each host could have taken Hermit: present and not in bedtime lock.

    A friend at the keyboard at 2 a.m. is *present* but deliberately cannot
    claim, so counting them as "waiting" would book their whole night as
    handoff latency.
    """
    if events is None:
        return None
    history = PresenceHistory(PRESENCE_STALE_S)
    state: dict[str, str] = {}
    found = False
    for event in events:
        if event.type in (EventType.HOST_HEARTBEAT, EventType.PRESENCE_CHANGED):
            if isinstance(event.data.get("state"), str):
                state[event.host] = event.data["state"]
            present = event.data.get("present")
            if isinstance(present, bool):
                available = present and state.get(event.host) != "BEDTIME_LOCK"
                history.observe(event.host, event.ts.timestamp(), available)
                found = True
    return history if found else None


def _was_present(history: PresenceHistory | None, host: str, at: float) -> bool | None:
    """Could ``host`` have claimed at ``at``? ``None`` if we never heard from them."""
    if history is None or host not in history.hosts():
        return None
    return any(start <= at < end for start, end in history.intervals(host, at + 1))


def _claim_time(stop: dict[str, Any], release: float, events: Sequence[Event] | None) -> float:
    arrived = _ts(stop["arrived_at"])
    if events is not None:
        for event in events:
            if (
                event.type is EventType.SOUL_CLAIMED
                and event.host == stop["host"]
                and release <= event.ts.timestamp() <= arrived
            ):
                return event.ts.timestamp()
    return arrived


def _stop_end(stop: dict[str, Any], events: Sequence[Event] | None) -> float | None:
    """When a stop really ended, or ``None`` if nobody can know."""
    if stop.get("departure") == "present" or not stop.get("left_at"):
        return None
    if stop.get("departure") != "abrupt":
        return _ts(stop["left_at"])
    if events is None:
        return None  # the export's left_at is the next arrival, not the lid slam
    arrived, left = _ts(stop["arrived_at"]), _ts(stop["left_at"])
    lines = [
        e.ts.timestamp()
        for e in events
        if e.host == stop["host"] and arrived <= e.ts.timestamp() <= left
    ]
    return max(lines, default=arrived)


def _observation_end(
    journey: dict[str, Any], stops: Sequence[dict[str, Any]], events: Sequence[Event] | None
) -> float | None:
    candidates: list[float] = []
    if journey.get("generated_at"):
        candidates.append(_ts(journey["generated_at"]))
    if events:
        candidates.append(events[-1].ts.timestamp())
    for stop in stops:
        if stop.get("left_at"):
            candidates.append(_ts(stop["left_at"]))
    return max(candidates) if candidates else None


def _dur(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    s = round(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def _opt(value: Any) -> str:
    return "n/a" if value is None else str(value)

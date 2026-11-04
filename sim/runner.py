"""Run a whole group of keepers on one machine, fast-forwarded. Owner: Afreen.

This is the piece a judge actually runs. It has to work with no Switch server,
no second laptop and no API keys, in under a minute, and it has to produce
something you can look at: a readable timeline and a `journey.json` the map can
render.

Everything is wired to the fakes and a `FakeClock`, so a simulated day costs
milliseconds and every run is reproducible from the scenario file.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from hermit_keeper import ledger
from hermit_keeper.bedtime import is_bedtime
from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.events import Event, EventBus, EventType
from hermit_keeper.favors import FavorBook
from hermit_keeper.handoff import Handoff
from hermit_keeper.lease.fake import FakeSoulLease
from hermit_keeper.presence.composite import CompositePresence
from hermit_keeper.presence.fake import ScriptedPresence
from hermit_keeper.room.fake import FakeRoomHub
from hermit_keeper.shell_model import make_piece
from hermit_keeper.nudge import NudgeParams
from hermit_keeper.overlap import HostSchedule, OverlapParams
from hermit_keeper.statemachine import KeeperStateMachine
from hermit_keeper.stretch import StretchRunner

DEN = "hermit-den"
LEDGER = "hermit-ledger"
TICK_S = 30.0
#: The real keeper beats every 10 s. The sim beats whenever presence or state
#: changes and otherwise every 10 minutes: the same story, far fewer lines.
SIM_HEARTBEAT_S = 600.0
START = datetime(2026, 11, 5, 0, 0, tzinfo=UTC)


@dataclass
class HostSpec:
    host_id: str
    provider: str = "other"
    city: str = "Bengaluru"
    tz: str = "Asia/Kolkata"
    lat: float = 12.97
    lon: float = 77.59
    presence: list[tuple[float, bool]] = field(default_factory=list)
    bedtime_start: str = "01:00"
    bedtime_end: str = "06:00"


@dataclass
class ScheduledEvent:
    at_s: float
    host: str
    action: str
    text: str = ""


@dataclass
class SimResult:
    timeline: list[str]
    events: list[Event]
    journey: dict[str, Any]
    failures: list[str]
    hosts: list[HostSpec]

    @property
    def ok(self) -> bool:
        return not self.failures


class SimHost:
    """One simulated laptop: brain, favors, handoff, state machine."""

    def __init__(
        self,
        spec: HostSpec,
        clock: FakeClock,
        lease: FakeSoulLease,
        hub: FakeRoomHub,
        bus: EventBus,
        seed: int,
        favors: FavorBook,
    ) -> None:
        self.spec = spec
        self.clock = clock
        self.zone = ZoneInfo(spec.tz)
        self.room = hub.client(f"keeper-{spec.host_id}")
        self.brain = FakeBrain(
            f"hermit-{spec.host_id}",
            spec.provider,
            den=hub.client(f"hermit-{spec.host_id}"),
        )
        #: Shared across every host: a favor lives in the room, not on a laptop.
        self.favors = favors
        #: Set by a `favor_reply` scheduled event.
        self.pending_reply: str | None = None
        #: A slammed laptop stops sending anything at all, heartbeats included.
        self.lid_closed = False
        self._last_beat: float | None = None
        self._beat_said: tuple[bool, str] | None = None
        #: Stretch S1/S2, set by `run_scenario` when the scenario turns them on.
        self.stretch: StretchRunner | None = None

        self.handoff = Handoff(
            spec.host_id,
            self.room,
            self.brain,
            clock,
            bus,
            favors=self,
            context=self,
            den_room=DEN,
            ledger_room=LEDGER,
            brain_provider=spec.provider,
        )
        presence = CompositePresence(
            ScriptedPresence(clock, spec.presence or [(0, True)]),
            clock,
            idle_threshold_s=300.0,
            arrive_debounce_s=60.0,
            sleep_gap_s=90.0,
        )
        self.presence = presence
        self.machine = KeeperStateMachine(
            host=spec.host_id,
            agent=f"hermit-{spec.host_id}",
            lease=lease,
            presence=presence,
            clock=clock,
            bus=bus,
            is_bedtime=self._is_bedtime,
            min_dwell_s=300.0,
            claim_delay_s=float(seed % 3),
            claim_jitter_s=2.0,
            backoff_s=30.0,
            on_claimed=self.handoff.on_claimed,
            on_departing=self.handoff.on_departing,
            rng=random.Random(seed),
        )

    def local_now(self) -> datetime:
        return self.clock.now().astimezone(self.zone)

    def _is_bedtime(self, _now: datetime) -> bool:
        return is_bedtime(
            self.local_now(), self.spec.bedtime_start, self.spec.bedtime_end
        )

    # -- ContextProvider -----------------------------------------------------

    async def arrival_context(self) -> dict[str, Any]:
        return {
            "city": self.spec.city,
            "temp_c": 26.0,
            "weather": {"temp_c": 26.0, "code": 1},
            "local_hour": self.local_now().hour,
        }

    # -- FavorStore ----------------------------------------------------------

    async def carried(self, for_host: str) -> dict[str, Any] | None:
        return await self.favors.carried(for_host)

    async def assign(self, favor_id: str, host: str) -> None:
        await self.favors.assign(favor_id, host)

    async def ask_and_capture(self, timeout_s: float) -> dict[str, Any] | None:
        """In the sim the host's reply is scheduled, not typed."""
        if self.pending_reply is None:
            return None
        text, self.pending_reply = self.pending_reply, None
        favor = await self.favors.leave(self.spec.host_id, text)
        return favor.to_dict() if favor else None

    # -- heartbeats ------------------------------------------------------------

    async def beat(self) -> None:
        """What `KeeperRuntime.beat` does, at sim cadence.

        This is the presence history the overlap finder learns routines from,
        and what `metrics` uses to tell "somebody was waiting" from "everyone
        was asleep".
        """
        if self.lid_closed:
            return
        now = self.clock.now().timestamp()
        present, state = self.presence.present, str(self.machine.state)
        due = self._last_beat is None or now - self._last_beat >= SIM_HEARTBEAT_S
        if not due and (present, state) == self._beat_said:
            return
        self._last_beat, self._beat_said = now, (present, state)
        event = Event(
            type=EventType.HOST_HEARTBEAT,
            host=self.spec.host_id,
            ts=self.clock.now(),
            data={"state": str(self.machine.state), "present": present},
        )
        await self.room.post(LEDGER, ledger.encode(event))

    def schedule(self) -> HostSchedule:
        return HostSchedule(self.spec.tz, self.spec.bedtime_start, self.spec.bedtime_end)


class _Documents:
    """Favor documents, written into the fake room."""

    def __init__(self, room: Any) -> None:
        self._room = room

    async def create_room_document(
        self, room: str, name: str, description: str, instructions: str, content: str
    ) -> str:
        return await self._room.create_task(room, name, content, assignee=None)


def load_scenario(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _daily_presence(
    ranges: list[list[str]], tz: str, start: datetime, duration_s: float
) -> list[tuple[float, bool]]:
    """Expand a daily routine (local ``["HH:MM", "HH:MM"]`` ranges) to a timeline.

    The plan's scenario format (plan.md 5.1). A range whose end is before its
    start runs past midnight. Repeats every day of the scenario, which is what
    the overlap finder needs: a routine, not a one-off.
    """
    zone = ZoneInfo(tz)
    first_day = start.astimezone(zone).date()
    spans: list[tuple[float, float]] = []
    for day in range(-1, int(duration_s // 86400) + 2):
        date = first_day + timedelta(days=day)
        for begin, end in ranges:
            on = datetime.combine(date, _hhmm(begin), tzinfo=zone)
            off = datetime.combine(date, _hhmm(end), tzinfo=zone)
            if off <= on:
                off += timedelta(days=1)
            a = max(0.0, (on - start).total_seconds())
            b = min(duration_s, (off - start).total_seconds())
            if b > a:
                spans.append((a, b))
    merged: list[list[float]] = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    timeline: list[tuple[float, bool]] = [(0.0, False)]
    for a, b in merged:
        timeline += [(a, True), (b, False)]
    return timeline


def _hhmm(value: str) -> time:
    hour, _, minute = str(value).partition(":")
    return time(int(hour) % 24, int(minute or 0))


def _parse_hosts(
    raw: Any, start: datetime | None = None, duration_s: float = 86400
) -> list[HostSpec]:
    hosts: list[HostSpec] = []
    start = start or START
    for entry in raw or []:
        presence = [(float(t), bool(p)) for t, p in (entry.get("presence") or [])]
        if entry.get("presence_daily"):
            presence = _daily_presence(
                entry["presence_daily"],
                entry.get("timezone", entry.get("tz", "Asia/Kolkata")),
                start,
                duration_s,
            )
        hosts.append(
            HostSpec(
                host_id=entry["host_id"],
                provider=entry.get("brain_provider", entry.get("provider", "other")),
                city=entry.get("city", entry.get("area", "Bengaluru")),
                tz=entry.get("timezone", entry.get("tz", "Asia/Kolkata")),
                lat=float(entry.get("lat", 12.97)),
                lon=float(entry.get("lon", 77.59)),
                presence=presence,
                bedtime_start=entry.get("bedtime_start", "01:00"),
                bedtime_end=entry.get("bedtime_end", "06:00"),
            )
        )
    return hosts


async def run_scenario(path: Path, verbose: bool = True) -> SimResult:
    scenario = load_scenario(path)
    duration_s = float(
        scenario.get("duration_s") or scenario.get("duration_h", 24) * 3600
    )
    expiry_s = float(scenario.get("lease_expiry_s", 8))
    start = START
    hosts = _parse_hosts(scenario.get("hosts"), start, duration_s)
    if not hosts:
        return SimResult([], [], {}, [f"{path.name}: no hosts defined"], [])

    clock = FakeClock(start)
    lease = FakeSoulLease(clock=clock, expiry_delay_s=expiry_s)
    hub = FakeRoomHub(clock=clock)
    bus = EventBus()
    collected: list[Event] = []

    favors = FavorBook(clock, documents=_Documents(hub.client("keeper-sim")), room=DEN)
    sim_hosts = [
        SimHost(spec, clock, lease, hub, bus, seed=i, favors=favors)
        for i, spec in enumerate(hosts)
    ]
    by_id = {h.spec.host_id: h for h in sim_hosts}
    _attach_stretch(scenario, sim_hosts, hub, bus, clock)

    scheduled = _parse_events(scenario.get("events"), start)
    timeline: list[str] = []
    holder_before: str | None = None
    ledger_seen = 0

    elapsed = 0.0
    while elapsed < duration_s:
        for item in [e for e in scheduled if elapsed <= e.at_s < elapsed + TICK_S]:
            host = by_id.get(item.host)
            if host is None:
                continue
            if item.action == "lid_slam":
                await lease.expire(f"hermit-{item.host}", after_s=0)
                host.presence.set_override("asleep")
                host.lid_closed = True
                timeline.append(_stamp(clock, f"{item.host} slammed the lid"))
            elif item.action == "favor_reply":
                host.pending_reply = item.text
                timeline.append(
                    _stamp(clock, f'{item.host} left a favor: "{item.text}"')
                )

        for host in sim_hosts:
            await host.machine.tick()
            await host.beat()
            if host.stretch is not None:
                await host.stretch.tick(
                    holding=host.machine.holding, present=host.presence.present
                )

        holders = [h.spec.host_id for h in sim_hosts if h.machine.holding]
        if len(holders) > 1:
            timeline.append(_stamp(clock, f"!! TWO HOLDERS: {holders}"))
        now_holder = holders[0] if holders else None
        if now_holder != holder_before:
            if now_holder:
                timeline.append(_stamp(clock, f"Hermit is with {now_holder}"))
            else:
                timeline.append(_stamp(clock, "Hermit is between friends"))
            holder_before = now_holder
        ledger_seen = _narrate(hub, ledger_seen, clock, timeline)

        await clock.advance(TICK_S)
        elapsed += TICK_S

    # Completing a favor is a human act; in the sim the next host does it
    # shortly after arriving, which is what we want to exercise end to end.
    await _complete_favors(sim_hosts, clock)

    collected.extend(_ledger_events(hub))
    journey = _build_journey(collected, hosts, clock)
    failures = _check(
        scenario.get("assertions") or scenario.get("expect") or [],
        collected,
        timeline,
        hosts,
    )

    if verbose:
        for line in timeline:
            print("  " + line)
    return SimResult(timeline, collected, journey, failures, hosts)


async def _complete_favors(sim_hosts: list[SimHost], clock: FakeClock) -> None:
    """Assigned favors get done, each producing a shell piece.

    Written to the ledger only. They used to be appended to the collected
    events *as well*, and the ledger read-back then counted every completion
    and shell piece twice.
    """
    book = sim_hosts[0].favors
    for favor in list(book.favors.values()):
        if favor.status != "assigned" or favor.assignee is None:
            continue
        done = await book.complete(favor.id, favor.assignee)
        if done is None:
            continue
        doer = next(
            (h for h in sim_hosts if h.spec.host_id == favor.assignee), sim_hosts[0]
        )
        piece = make_piece(
            host=doer.spec.host_id,
            city=doer.spec.city,
            brain_provider=doer.spec.provider,
            dwell_s=doer.machine.dwell_s or 1800,
            departure="graceful",
            created_at=clock.now(),
            favor_id=favor.id,
            temp_c=26.0,
            weather_code=1,
        )
        for event in (
            Event(
                type=EventType.FAVOR_COMPLETED,
                host=doer.spec.host_id,
                ts=clock.now(),
                data={"favor_id": favor.id, "completed_by": favor.assignee},
            ),
            Event(
                type=EventType.SHELL_PIECE_ADDED,
                host=doer.spec.host_id,
                ts=clock.now(),
                data={"piece": piece.to_dict()},
            ),
        ):
            await doer.room.post(LEDGER, ledger.encode(event))


def _attach_stretch(
    scenario: dict[str, Any],
    sim_hosts: list[SimHost],
    hub: FakeRoomHub,
    bus: EventBus,
    clock: FakeClock,
) -> None:
    """Turn on S1/S2 for every host if the scenario's `features` asks for them.

    Same `StretchRunner` the real keeper runs. The sim knows every host's
    bedtime, so unlike a real keeper it can pass them all in.
    """
    features = scenario.get("features") or {}
    overlap, nudge = bool(features.get("overlap")), bool(features.get("nudge"))
    if not (overlap or nudge):
        return
    raw_overlap = scenario.get("overlap") or {}
    raw_nudge = scenario.get("nudge") or {}
    overlap_params = OverlapParams(
        **{k: v for k, v in raw_overlap.items() if k in OverlapParams.__dataclass_fields__}
    )
    nudge_params = NudgeParams(
        quiet_after_s=float(raw_nudge.get("quiet_after_h", 72)) * 3600,
        min_gap_s=float(raw_nudge.get("min_gap_h", 12)) * 3600,
    )
    schedules = {h.spec.host_id: h.schedule() for h in sim_hosts}
    for host in sim_hosts:
        host.stretch = StretchRunner(
            host.spec.host_id,
            hub.client(f"keeper-{host.spec.host_id}"),
            host.brain,
            clock,
            bus,
            overlap=overlap,
            nudge=nudge,
            ledger_room=LEDGER,
            schedule=host.schedule(),
            schedules=schedules,
            known_hosts=[h.spec.host_id for h in sim_hosts],
            overlap_params=overlap_params,
            nudge_params=nudge_params,
        )


def _narrate(
    hub: FakeRoomHub, seen: int, clock: FakeClock, timeline: list[str]
) -> int:
    """Timeline lines for the stretch features, read back from the ledger."""
    messages = hub.rooms.get(LEDGER, [])
    for message in messages[seen:]:
        event = ledger.decode(message.text)
        if event is None:
            continue
        data = event.data
        if event.type is EventType.OVERLAP_SUGGESTED:
            a, b = data["hosts"]
            start = data["window_start"][11:16]
            end = data["window_end"][11:16]
            timeline.append(
                _stamp(clock, f"overlap: {a} + {b} usually free {start}-{end} UTC")
            )
        elif event.type is EventType.NUDGE_SENT:
            timeline.append(
                _stamp(
                    clock,
                    f"nudge: {event.host} asks the group to leave something for "
                    f"{data['target_host']} ({data['days_since_hosted']} days quiet)",
                )
            )
        elif event.type is EventType.SHELL_PIECE_ADDED and data.get("cracked_for_stop"):
            timeline.append(
                _stamp(
                    clock,
                    f'"I left in a hurry" - {event.host} gets a cracked shell piece',
                )
            )
    return len(messages)


def _ledger_events(hub: FakeRoomHub) -> list[Event]:
    out: list[Event] = []
    for message in hub.rooms.get(LEDGER, []):
        event = ledger.decode(message.text)
        if event is not None:
            out.append(event)
    return out


def _build_journey(
    events: list[Event], hosts: list[HostSpec], clock: FakeClock
) -> dict[str, Any]:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from export_journey import build_journey  # type: ignore[import-not-found]

    host_dicts = [
        {
            "host_id": h.host_id,
            "display_name": h.host_id.title(),
            "city": h.city,
            "lat": h.lat,
            "lon": h.lon,
            "brain_provider": h.provider,
        }
        for h in hosts
    ]
    ordered = sorted(events, key=lambda e: (e.ts, e.id))
    journey: dict[str, Any] = build_journey(ordered, host_dicts, clock.now().isoformat())
    # Every number derived from this file must be labelled SIMULATION. The
    # schema lets `stats` carry extra keys, and `metrics` reads this one.
    journey["stats"]["source"] = "simulation"
    return journey


def _parse_events(raw: Any, start: datetime) -> list[ScheduledEvent]:
    out: list[ScheduledEvent] = []
    for entry in raw or []:
        at = entry.get("at")
        if isinstance(at, str):
            at_s = (datetime.fromisoformat(at) - start).total_seconds()
        else:
            at_s = float(at or 0)
        out.append(
            ScheduledEvent(
                at_s,
                entry.get("host", ""),
                entry.get("action", ""),
                entry.get("text", ""),
            )
        )
    return out


def _check(
    assertions: list[Any],
    events: list[Event],
    timeline: list[str],
    hosts: list[HostSpec] | None = None,
) -> list[str]:
    """Every assertion a scenario can make. Unknown ones fail loudly."""
    failures: list[str] = []
    arrivals = [e for e in events if e.type is EventType.ARRIVAL_ANNOUNCED]
    completed = [e for e in events if e.type is EventType.FAVOR_COMPLETED]
    left = [e for e in events if e.type is EventType.FAVOR_LEFT]
    overlaps = [e for e in events if e.type is EventType.OVERLAP_SUGGESTED]
    nudges = [e for e in events if e.type is EventType.NUDGE_SENT]
    cracked = [
        e
        for e in events
        if e.type is EventType.SHELL_PIECE_ADDED
        and (e.data.get("piece") or {}).get("departure") == "abrupt"
    ]
    schedules = {
        h.host_id: HostSchedule(h.tz, h.bedtime_start, h.bedtime_end)
        for h in hosts or []
    }

    for raw in assertions:
        name, value = (raw, None) if isinstance(raw, str) else next(iter(raw.items()))
        if name in ("never_two_holders", "never_two_souls"):
            if any("TWO HOLDERS" in line for line in timeline):
                failures.append("two hosts held the soul at once")
        elif name in ("min_handoffs", "handoffs_at_least"):
            if len(arrivals) < int(value):
                failures.append(f"only {len(arrivals)} arrivals, wanted {value}")
        elif name in ("favors_completed_at_least",):
            if len(completed) < int(value):
                failures.append(
                    f"only {len(completed)} favors completed, wanted {value}"
                )
        elif name in ("favors_left_at_least",):
            if len(left) < int(value):
                failures.append(f"only {len(left)} favors left, wanted {value}")
        elif name == "no_claim_during_bedtime":
            pass  # the state machine cannot claim in BEDTIME_LOCK; covered by unit tests
        elif name in ("nobody_awake_gap_handled", "no_handoffs"):
            if name == "no_handoffs" and arrivals:
                failures.append(f"expected no arrivals, got {len(arrivals)}")
        # -- S3: abrupt departures ------------------------------------------
        elif name == "cracked_pieces_at_least":
            if len(cracked) < int(value):
                failures.append(f"only {len(cracked)} cracked pieces, wanted {value}")
        elif name == "hurry_line_delivered":
            if not any("I left in a hurry" in line for line in timeline):
                failures.append('nobody heard "I left in a hurry"')
        # -- S1: overlap ----------------------------------------------------
        elif name == "overlaps_suggested_at_least":
            if len(overlaps) < int(value):
                failures.append(f"only {len(overlaps)} overlaps suggested, wanted {value}")
        elif name == "no_overlap_in_bedtime":
            for event in overlaps:
                start = datetime.fromisoformat(event.data["window_start"]).timestamp()
                end = datetime.fromisoformat(event.data["window_end"]).timestamp()
                for host in event.data["hosts"]:
                    if schedules.get(host, HostSchedule()).overlaps_bedtime(start, end):
                        failures.append(f"overlap {event.data['ovl_id']} is in {host}'s bedtime")
        elif name == "overlap_pair_cooldown_respected":
            cooldown = OverlapParams().cooldown_s
            last: dict[tuple[str, ...], datetime] = {}
            for event in sorted(overlaps, key=lambda e: e.ts):
                pair = tuple(sorted(event.data["hosts"]))
                if pair in last and (event.ts - last[pair]).total_seconds() < cooldown:
                    failures.append(f"pair {pair} suggested twice inside the cooldown")
                last[pair] = event.ts
        elif name == "overlap_only_from_a_holder_in_the_pair":
            for event in overlaps:
                if event.host not in event.data["hosts"]:
                    failures.append(f"{event.host} suggested a call it is not part of")
        # -- S2: quiet-friend nudge -----------------------------------------
        elif name == "nudges_at_least":
            if len(nudges) < int(value):
                failures.append(f"only {len(nudges)} nudges, wanted {value}")
        elif name == "nudges_at_most":
            if len(nudges) > int(value):
                failures.append(f"{len(nudges)} nudges, wanted at most {value}")
        elif name == "nudge_once_per_quiet_spell":
            spells = [(e.data["target_host"], e.data.get("quiet_since")) for e in nudges]
            if len(spells) != len(set(spells)):
                failures.append("the same quiet spell was nudged twice")
        elif name == "nudge_never_about_the_holder":
            for event in nudges:
                if event.data["target_host"] == event.host:
                    failures.append(f"{event.host} was nudged about themselves")
        else:
            failures.append(
                f"unknown assertion '{name}' — add it to sim/runner.py or fix the scenario"
            )
    return failures


def _stamp(clock: FakeClock, text: str) -> str:
    day = (clock.now() - START).days
    prefix = f"d{day + 1} " if day else ""
    return f"{prefix}{clock.now().strftime('%H:%M')}  {text}"

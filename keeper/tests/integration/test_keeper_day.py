"""Phase 3.6 acceptance: three real keepers, one scripted day, correct handoffs.

This is the state machine and the handoff sequence wired to the fakes — the
closest thing to the product that exists before Switch is connected. It is also
the test that will catch it if Phase 4 breaks the handoff order.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from hermit_keeper import ledger
from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.events import EventBus, EventType
from hermit_keeper.handoff import Handoff
from hermit_keeper.lease.fake import FakeSoulLease
from hermit_keeper.presence.composite import CompositePresence
from hermit_keeper.presence.fake import ScriptedPresence
from hermit_keeper.room.fake import FakeRoomHub
from hermit_keeper.statemachine import KeeperStateMachine, State

DEN = "hermit-den"
LEDGER = "hermit-ledger"
STEP = 30.0


class StubFavors:
    """Stands in for Abhishek's ``favors.py`` until Phase 4 lands."""

    def __init__(self, host: str) -> None:
        self.host = host
        self.carried_favor: dict[str, Any] | None = None
        self.assigned: list[tuple[str, str]] = []
        self.left: list[dict[str, Any]] = []

    async def carried(self) -> dict[str, Any] | None:
        return self.carried_favor

    async def assign(self, favor_id: str, host: str) -> None:
        self.assigned.append((favor_id, host))

    async def ask_and_capture(self, timeout_s: float) -> dict[str, Any] | None:
        favor = {
            "id": f"fav_{self.host}",
            "text": f"something {self.host} left",
            "left_by": self.host,
        }
        self.left.append(favor)
        return favor


class StubContext:
    def __init__(self, city: str) -> None:
        self.city = city

    async def arrival_context(self) -> dict[str, Any]:
        return {"city": self.city, "temp_c": 26.0, "weather": {"temp_c": 26.0, "code": 1}}


def build_host(
    host: str,
    provider: str,
    city: str,
    timeline: list[tuple[float, bool]],
    clock: FakeClock,
    lease: FakeSoulLease,
    hub: FakeRoomHub,
    bus: EventBus,
    seed: int,
    is_bedtime=None,
):
    room = hub.client(f"keeper-{host}")
    brain = FakeBrain(f"hermit-{host}", provider, den=hub.client(f"hermit-{host}"))
    favors = StubFavors(host)
    handoff = Handoff(host, room, brain, clock, bus, favors=favors, context=StubContext(city))
    presence = CompositePresence(
        ScriptedPresence(clock, timeline), clock, idle_threshold_s=300.0, arrive_debounce_s=60.0
    )
    machine = KeeperStateMachine(
        host=host,
        agent=f"hermit-{host}",
        lease=lease,
        presence=presence,
        clock=clock,
        bus=bus,
        is_bedtime=is_bedtime,
        min_dwell_s=300.0,
        claim_delay_s=float(seed),
        claim_jitter_s=0.0,
        backoff_s=30.0,
        on_claimed=handoff.on_claimed,
        on_departing=handoff.on_departing,
        rng=random.Random(seed),
    )
    return machine, handoff, favors, brain


async def test_three_hosts_one_day_correct_handoffs() -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    hub = FakeRoomHub(clock=clock)
    bus = EventBus()

    hosts = [
        build_host(
            "afreen",
            "claude-code",
            "Indiranagar",
            [(0, True), (3000, False)],
            clock,
            lease,
            hub,
            bus,
            seed=0,
        ),
        build_host(
            "abhishek",
            "opencode",
            "Kengeri",
            [(2400, True), (7000, False)],
            clock,
            lease,
            hub,
            bus,
            seed=1,
        ),
        build_host(
            "akshay", "codex", "Koramangala", [(6000, True)], clock, lease, hub, bus, seed=2
        ),
    ]
    machines = [h[0] for h in hosts]

    for _ in range(400):  # ~3.3 simulated hours
        for machine in machines:
            await machine.tick()
            holders = [m.host for m in machines if m.holding]
            assert len(holders) <= 1, f"two Hermits: {holders}"
        await clock.advance(STEP)

    lines = [m.text for m in await hub.client("reader").history(LEDGER)]
    events = [e for e in (ledger.decode(line) for line in lines) if e is not None]
    assert len(events) == len(lines), "every ledger line must decode"

    arrivals = [e.host for e in events if e.type is EventType.ARRIVAL_ANNOUNCED]
    assert arrivals, "Hermit never arrived anywhere"
    assert arrivals == sorted(set(arrivals), key=arrivals.index), "no host arrived twice in a row"
    assert "akshay" in arrivals, "the host who stayed should have been visited"

    # Hermit ends the day with whoever is still at their laptop.
    assert machines[2].holding, f"expected akshay to hold, states={[m.state for m in machines]}"


async def test_departure_sequence_is_ask_favor_then_goodbye_then_release() -> None:
    """Order matters: a goodbye before the ask would lose the favor chain."""
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    hub = FakeRoomHub(clock=clock)
    bus = EventBus()

    machine, _handoff, favors, brain = build_host(
        "afreen",
        "claude-code",
        "Indiranagar",
        [(0, True), (120, False)],
        clock,
        lease,
        hub,
        bus,
        seed=0,
    )

    for _ in range(80):
        await machine.tick()
        await clock.advance(STEP)
        if machine.state is State.ASLEEP and favors.left:
            break

    cues = [cue for cue, _ in brain.cues]
    assert cues[0] == "ARRIVE"
    assert cues.index("ASK_FAVOR") < cues.index("DEPART"), "must ask before saying goodbye"
    assert "FAVOR_CAPTURED" in cues
    assert await lease.holder() is None, "the soul must be free after a graceful departure"

    events = [
        e
        for e in (ledger.decode(m.text) for m in await hub.client("r").history(LEDGER))
        if e is not None
    ]
    kinds = [e.type for e in events]
    assert EventType.ARRIVAL_ANNOUNCED in kinds
    assert EventType.FAVOR_LEFT in kinds


async def test_a_carried_favor_is_assigned_to_the_next_host() -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    hub = FakeRoomHub(clock=clock)
    bus = EventBus()

    machine, _handoff, favors, brain = build_host(
        "abhishek", "opencode", "Kengeri", [(0, True)], clock, lease, hub, bus, seed=0
    )
    favors.carried_favor = {"id": "fav_from_afreen", "text": "send a song", "left_by": "afreen"}

    for _ in range(20):
        await machine.tick()
        if machine.holding:
            break
        await clock.advance(STEP)

    assert machine.holding
    assert favors.assigned == [("fav_from_afreen", "abhishek")]
    arrive_context = next(ctx for cue, ctx in brain.cues if cue == "ARRIVE")
    assert arrive_context["favor"]["text"] == "send a song"
    assert arrive_context["city"] == "Kengeri"


async def test_bedtime_eviction_frees_the_soul_and_locks_the_host_out() -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    hub = FakeRoomHub(clock=clock)
    bus = EventBus()
    bedtime = {"on": False}

    machine, _, _, brain = build_host(
        "afreen",
        "claude-code",
        "Indiranagar",
        [(0, True)],
        clock,
        lease,
        hub,
        bus,
        seed=0,
        is_bedtime=lambda _now: bedtime["on"],
    )
    for _ in range(20):
        await machine.tick()
        if machine.holding:
            break
        await clock.advance(STEP)
    assert machine.holding

    bedtime["on"] = True
    for _ in range(5):
        await machine.tick()
        await clock.advance(STEP)

    assert machine.state is State.BEDTIME_LOCK
    assert await lease.holder() is None
    depart_context = next(ctx for cue, ctx in brain.cues if cue == "DEPART")
    assert depart_context["reason"] == "bedtime"


def _never_bedtime(_now: datetime) -> bool:
    return False


async def test_the_next_host_learns_who_came_before_from_the_ledger() -> None:
    """A keeper has never seen another laptop's stops. The room is the memory."""
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    hub = FakeRoomHub(clock=clock)
    bus = EventBus()

    first, _, _, _ = build_host(
        "afreen",
        "claude-code",
        "Indiranagar",
        [(0, True), (120, False)],
        clock,
        lease,
        hub,
        bus,
        seed=0,
    )
    second, _, _, second_brain = build_host(
        "abhishek",
        "opencode",
        "Kengeri",
        [(0, True)],
        clock,
        lease,
        hub,
        bus,
        seed=1,
    )

    for _ in range(120):
        await first.tick()
        await second.tick()
        await clock.advance(STEP)
        if second.holding:
            break

    assert second.holding
    arrive = next(ctx for cue, ctx in second_brain.cues if cue == "ARRIVE")
    assert arrive["previous_host"] == "afreen"
    assert arrive["previous_departure"] == "graceful"


async def test_a_host_who_never_said_goodbye_is_recorded_as_abrupt() -> None:
    """No SOUL_RELEASED in the ledger means the lid came down.

    This is what Phase 4 turns into a cracked shell piece and the line
    "I left in a hurry".
    """
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock, expiry_delay_s=8.0)
    hub = FakeRoomHub(clock=clock)
    bus = EventBus()

    first, _, _, _ = build_host(
        "afreen", "claude-code", "Indiranagar", [(0, True)], clock, lease, hub, bus, seed=0
    )
    second, _, _, second_brain = build_host(
        "akshay", "codex", "Koramangala", [(0, True)], clock, lease, hub, bus, seed=5
    )

    for _ in range(20):
        await first.tick()
        if first.holding:
            break
        await clock.advance(STEP)
    assert first.holding, "afreen needs the soul before the lid can slam"

    # The lid slams: no goodbye, no SOUL_RELEASED, the lease simply expires.
    await lease.expire("hermit-afreen", after_s=0)

    for _ in range(60):
        await second.tick()
        await clock.advance(STEP)
        if second.holding:
            break

    assert second.holding
    arrive = next(ctx for cue, ctx in second_brain.cues if cue == "ARRIVE")
    assert arrive["previous_host"] == "afreen"
    assert arrive["previous_departure"] == "abrupt", "a silent exit must be marked abrupt"

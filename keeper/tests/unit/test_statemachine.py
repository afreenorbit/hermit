"""The state machine: every transition, plus the rules that keep it polite."""

from __future__ import annotations

import random
from datetime import datetime

from hermit_keeper.clock import FakeClock
from hermit_keeper.lease.fake import FakeSoulLease
from hermit_keeper.presence.composite import CompositePresence, Override
from hermit_keeper.presence.fake import ScriptedPresence
from hermit_keeper.statemachine import KeeperStateMachine, State

DEBOUNCE = 60.0
IDLE_THRESHOLD = 300.0
MIN_DWELL = 600.0


def build(
    host: str = "afreen",
    timeline: list[tuple[float, bool]] | None = None,
    lease: FakeSoulLease | None = None,
    clock: FakeClock | None = None,
    is_bedtime=None,
    min_dwell_s: float = MIN_DWELL,
    claim_delay_s: float = 0.0,
) -> tuple[KeeperStateMachine, FakeClock, FakeSoulLease, CompositePresence]:
    clock = clock or FakeClock()
    lease = lease if lease is not None else FakeSoulLease(clock=clock)
    source = ScriptedPresence(clock, timeline if timeline is not None else [(0, True)])
    presence = CompositePresence(
        source, clock, idle_threshold_s=IDLE_THRESHOLD, arrive_debounce_s=DEBOUNCE
    )
    machine = KeeperStateMachine(
        host=host,
        agent=f"hermit-{host}",
        lease=lease,
        presence=presence,
        clock=clock,
        is_bedtime=is_bedtime,
        min_dwell_s=min_dwell_s,
        claim_delay_s=claim_delay_s,
        claim_jitter_s=0.0,
        backoff_s=30.0,
        rng=random.Random(0),
    )
    return machine, clock, lease, presence


async def settle(machine: KeeperStateMachine, clock: FakeClock, seconds: float = 0) -> None:
    """Tick, optionally after advancing time."""
    if seconds:
        await clock.advance(seconds)
    await machine.tick()


async def reach_holding(
    machine: KeeperStateMachine, clock: FakeClock, step: float = 15.0, limit: int = 60
) -> None:
    """Tick until this keeper is HOLDING, or fail loudly.

    Reaching HOLDING legitimately takes several ticks — debounce, then noticing
    the soul is free, then the fairness delay, then the claim — so tests say
    what they are waiting for instead of counting ticks.
    """
    for _ in range(limit):
        await machine.tick()
        if machine.holding:
            return
        await clock.advance(step)
    raise AssertionError(f"never reached HOLDING; stuck in {machine.state}")


async def tick_for(
    machine: KeeperStateMachine, clock: FakeClock, seconds: float, step: float = 30.0
) -> None:
    """Run the keeper normally for a stretch of time.

    Steps must stay below ``sleep_gap_s`` (90s): a bigger jump is exactly how a
    suspended laptop looks, and the keeper is right to treat it as one. Tests
    that mean "the host walked away" tick in small steps; the test that means
    "the lid closed" jumps.
    """
    elapsed = 0.0
    while elapsed < seconds:
        await machine.tick()
        await clock.advance(step)
        elapsed += step


# -- the happy path ----------------------------------------------------------


async def test_present_host_claims_the_soul_after_debounce() -> None:
    machine, clock, lease, _ = build()

    await settle(machine, clock)
    assert machine.state is State.ASLEEP, "presence has not held long enough yet"

    await settle(machine, clock, DEBOUNCE + 1)
    assert machine.state is State.AWAKE_WAITING

    await settle(machine, clock, 1)  # sees the free soul
    await settle(machine, clock, 1)  # fairness delay elapsed -> CLAIMING
    await settle(machine, clock, 1)  # claim
    assert machine.state is State.HOLDING
    assert await lease.holder() == "hermit-afreen"


async def test_a_passing_nudge_does_not_drag_hermit_over() -> None:
    """Present for 10s then gone again: never claims."""
    machine, clock, lease, _ = build(timeline=[(0, True), (10, False)])

    for _ in range(10):
        await settle(machine, clock, 5)

    assert machine.state is State.ASLEEP
    assert await lease.holder() is None


# -- departures --------------------------------------------------------------


async def test_idle_host_departs_once_min_dwell_has_passed() -> None:
    """The host wanders off two minutes after Hermit arrives.

    Min dwell is what stops Hermit bouncing straight back out again: it stays
    put until it has had a real visit, then leaves.
    """
    machine, clock, lease, _ = build(timeline=[(0, True), (120, False)])
    await reach_holding(machine, clock)
    dwell_started = machine.dwell_s

    # Long past the idle threshold, but not yet a full minimum visit.
    await tick_for(machine, clock, 400)
    assert machine.state is State.HOLDING, "must not bounce off a short absence"
    assert machine.dwell_s < MIN_DWELL

    await tick_for(machine, clock, MIN_DWELL)
    assert machine.state in (State.DEPARTING, State.ASLEEP)
    assert dwell_started >= 0

    await settle(machine, clock, 1)
    await settle(machine, clock, 1)
    assert await lease.holder() is None, "the soul is free for the next host"


async def test_a_closed_lid_looks_like_a_suspend_not_an_idle_host() -> None:
    """A wall-clock jump bigger than sleep_gap_s means the machine was asleep.

    Idle time alone cannot see this: on wake the OS reports a tiny idle value
    and we would wrongly think the host is sitting right there.
    """
    machine, clock, _, presence = build()
    await reach_holding(machine, clock)

    await settle(machine, clock, 600)  # one big jump: the lid was shut

    assert presence.slept is True
    assert str(presence.reason) == "sleep_gap"
    assert machine.state is not State.HOLDING


async def test_manual_departure_ignores_min_dwell() -> None:
    """'I'm busy' in the critter must work immediately."""
    machine, clock, lease, _ = build()
    await reach_holding(machine, clock)

    machine.manual_depart = True
    await settle(machine, clock, 1)
    assert machine.state is State.DEPARTING

    await settle(machine, clock, 1)
    assert await lease.holder() is None


async def test_losing_the_lease_stops_hermit_speaking_with_no_goodbye() -> None:
    machine, clock, lease, _ = build()
    await reach_holding(machine, clock)

    # Switch gave the soul to someone else (our session died and came back).
    await lease.release("hermit-afreen")
    await lease.claim("hermit-akshay")

    await settle(machine, clock, 1)
    assert machine.state is not State.HOLDING
    assert machine.state is not State.DEPARTING
    assert await lease.holder() == "hermit-akshay", "we must not take it back"


# -- bedtime -----------------------------------------------------------------


def _always_bedtime(_now: datetime) -> bool:
    return True


async def test_never_claims_during_bedtime() -> None:
    machine, clock, lease, _ = build(is_bedtime=_always_bedtime)

    for _ in range(10):
        await settle(machine, clock, 30)

    assert machine.state is State.BEDTIME_LOCK
    assert await lease.holder() is None, "staying up must never be rewarded"


async def test_bedtime_evicts_a_holder_even_if_they_are_active() -> None:
    bedtime = {"on": False}
    machine, clock, lease, _ = build(is_bedtime=lambda _now: bedtime["on"])
    await reach_holding(machine, clock)

    bedtime["on"] = True
    await settle(machine, clock, 1)
    assert machine.state is State.DEPARTING

    await settle(machine, clock, 1)
    assert machine.state is State.BEDTIME_LOCK
    assert await lease.holder() is None


async def test_bedtime_lock_releases_in_the_morning() -> None:
    bedtime = {"on": True}
    machine, clock, _lease, _ = build(is_bedtime=lambda _now: bedtime["on"])
    for _ in range(3):
        await settle(machine, clock, 30)
    assert machine.state is State.BEDTIME_LOCK

    bedtime["on"] = False
    await settle(machine, clock, 1)
    assert machine.state is State.AWAKE_WAITING


# -- two keepers -------------------------------------------------------------


async def test_the_loser_backs_off_instead_of_hammering_the_lease() -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    afreen, _, _, _ = build("afreen", lease=lease, clock=clock)
    akshay, _, _, _ = build("akshay", lease=lease, clock=clock)

    for _ in range(40):
        await afreen.tick()
        await akshay.tick()
        await clock.advance(15)
        if afreen.holding or akshay.holding:
            break

    holding = [m.host for m in (afreen, akshay) if m.holding]
    assert len(holding) == 1, f"exactly one Hermit, got {holding}"
    loser = akshay if afreen.holding else afreen
    assert loser.state is State.AWAKE_WAITING


async def test_the_soul_moves_to_whoever_is_still_around() -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    # Afreen is there, then leaves. Akshay arrives later and stays.
    afreen, _, _, _ = build("afreen", timeline=[(0, True), (900, False)], lease=lease, clock=clock)
    akshay, _, _, _ = build("akshay", timeline=[(600, True)], lease=lease, clock=clock)

    for _ in range(120):
        await afreen.tick()
        await akshay.tick()
        await clock.advance(30)
        assert not (afreen.holding and akshay.holding), "two souls"

    assert akshay.holding, "Hermit should have followed the host who stayed"
    assert not afreen.holding


# -- overrides ---------------------------------------------------------------


async def test_override_asleep_releases_the_soul() -> None:
    machine, clock, lease, presence = build()
    await reach_holding(machine, clock)

    presence.set_override(Override.ASLEEP)
    await settle(machine, clock, MIN_DWELL + IDLE_THRESHOLD)
    await settle(machine, clock, 1)
    assert machine.state in (State.DEPARTING, State.ASLEEP)

    await settle(machine, clock, 1)
    assert await lease.holder() is None


# -- standing aside after a handoff ------------------------------------------


async def test_saying_go_hands_hermit_on_instead_of_taking_it_straight_back() -> None:
    """ "I'm busy, go" must not bounce back to the same laptop.

    The departing host is usually still the most eligible — present, awake,
    sitting right there — so without this it reclaims within seconds and the
    button looks broken.
    """
    machine, clock, lease, _ = build()
    machine._others_available = lambda: True  # someone else is awake
    await reach_holding(machine, clock)

    machine.manual_depart = True
    await settle(machine, clock, 1)
    await settle(machine, clock, 1)
    assert await lease.holder() is None, "the soul is free for someone else"

    # Well inside the stand-aside window: it must not take it back while
    # another host could have it.
    for _ in range(10):
        await settle(machine, clock, 15)
        assert not machine.holding, "took Hermit straight back after handing it on"


async def test_it_takes_hermit_back_rather_than_strand_it() -> None:
    """Standing aside only makes sense while somebody else could host."""
    machine, clock, _lease, _ = build()
    machine._others_available = lambda: False  # nobody else is around
    await reach_holding(machine, clock)

    machine.manual_depart = True
    await settle(machine, clock, 1)
    await settle(machine, clock, 1)

    for _ in range(40):
        await settle(machine, clock, 15)
        if machine.holding:
            break

    assert machine.holding, "Hermit was left with nowhere to go"


async def test_the_stand_aside_ends_once_someone_else_has_it() -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    machine, _, _, _ = build("afreen", lease=lease, clock=clock)
    machine._others_available = lambda: True
    await reach_holding(machine, clock)

    machine.manual_depart = True
    await settle(machine, clock, 1)
    await settle(machine, clock, 1)

    await lease.claim("hermit-akshay")
    # Past the short backoff, so the waiting tick actually looks at the holder.
    await settle(machine, clock, 60)

    assert machine._yield_until == 0.0, "handover done; normal fairness resumes"

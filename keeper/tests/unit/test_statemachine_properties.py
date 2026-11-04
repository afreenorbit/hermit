"""Phase 3.5 property test: whatever the group does, the rules hold.

Two properties, from plan.md 3.5:

1. **Safety** — at no instant are there two holders. If this breaks, two friends
   are talking to two different Hermits.
2. **Liveness** — if someone is present for longer than the debounce while the
   soul is free, *somebody* ends up holding it. A Hermit that is safe but never
   moves is just as broken; it would simply never show up.

Run with random presence timelines and random lease-expiry delays, because the
interesting bugs live in the interleavings nobody thought to write a test for.
"""

from __future__ import annotations

import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hermit_keeper.clock import FakeClock
from hermit_keeper.lease.fake import FakeSoulLease
from hermit_keeper.presence.composite import CompositePresence
from hermit_keeper.presence.fake import ScriptedPresence
from hermit_keeper.statemachine import KeeperStateMachine

HOSTS = ["afreen", "abhishek", "akshay", "dev", "guest"]
DEBOUNCE = 60.0
IDLE_THRESHOLD = 300.0
STEP = 30.0

timelines = st.lists(
    st.lists(
        st.tuples(st.integers(min_value=0, max_value=7200), st.booleans()),
        min_size=1,
        max_size=6,
    ),
    min_size=2,
    max_size=5,
)


def _build(host: str, timeline, clock: FakeClock, lease: FakeSoulLease, seed: int):
    source = ScriptedPresence(clock, [(float(t), p) for t, p in timeline])
    presence = CompositePresence(
        source, clock, idle_threshold_s=IDLE_THRESHOLD, arrive_debounce_s=DEBOUNCE
    )
    return KeeperStateMachine(
        host=host,
        agent=f"hermit-{host}",
        lease=lease,
        presence=presence,
        clock=clock,
        min_dwell_s=300.0,
        claim_delay_s=float(seed % 3),
        claim_jitter_s=2.0,
        backoff_s=30.0,
        rng=random.Random(seed),
    )


@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(timelines=timelines, expiry=st.floats(min_value=0.0, max_value=20.0))
@pytest.mark.asyncio
async def test_never_two_holders_whatever_the_group_does(timelines, expiry: float) -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock, expiry_delay_s=expiry)
    machines = [
        _build(HOSTS[i], timeline, clock, lease, seed=i) for i, timeline in enumerate(timelines)
    ]

    for _ in range(240):  # two simulated hours
        for machine in machines:
            await machine.tick()
            holders = [m.host for m in machines if m.holding]
            assert len(holders) <= 1, f"two Hermits at once: {holders}"
        await clock.advance(STEP)


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(present_from=st.integers(min_value=0, max_value=600))
@pytest.mark.asyncio
async def test_someone_present_and_a_free_soul_means_someone_claims_it(
    present_from: int,
) -> None:
    """Liveness: Hermit must actually show up for a host who is there."""
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    machines = [
        _build("afreen", [(present_from, True)], clock, lease, seed=1),
        _build("akshay", [(0, False)], clock, lease, seed=2),
    ]

    deadline_s = present_from + DEBOUNCE + 10 + 300  # generous: delays + backoff
    elapsed = 0.0
    while elapsed < deadline_s:
        for machine in machines:
            await machine.tick()
        await clock.advance(STEP)
        elapsed += STEP

    assert any(m.holding for m in machines), (
        "a host was present with a free soul and nobody ever claimed it"
    )
    assert machines[0].holding, "it should be the host who is actually there"

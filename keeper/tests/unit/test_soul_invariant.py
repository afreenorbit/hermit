"""The one claim the whole project rests on: there is never more than one Hermit.

If this file ever goes red, nothing else matters — two friends would be talking
to two different Hermits that each think they are the only one.
"""

from __future__ import annotations

import asyncio

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hermit_keeper.clock import FakeClock
from hermit_keeper.lease.fake import FakeSoulLease

HOSTS = ["afreen", "abhishek", "akshay"]


async def test_two_keepers_share_one_lease() -> None:
    """Phase 1.4 acceptance criterion: two keepers, one lease, one winner."""
    lease = FakeSoulLease()

    first = await lease.claim("afreen")
    second = await lease.claim("abhishek")

    assert first.ok is True
    assert first.holder == "afreen"
    assert second.ok is False
    assert second.holder == "afreen", "the loser must be told who actually has it"
    assert await lease.holder() == "afreen"


async def test_everyone_racing_at_once_produces_exactly_one_winner() -> None:
    """What really happens when a soul frees and three laptops are all awake."""
    lease = FakeSoulLease()

    results = await asyncio.gather(*(lease.claim(host) for host in HOSTS * 4))

    winners = [r.holder for r in results if r.ok]
    assert len(set(winners)) == 1, "two different agents believed they won"
    assert winners.count(winners[0]) == 4, "the winner may retry its own claim safely"
    assert await lease.holder() == winners[0]


async def test_release_frees_it_for_the_next_host() -> None:
    lease = FakeSoulLease()
    await lease.claim("afreen")
    await lease.release("afreen")

    assert await lease.holder() is None
    assert (await lease.claim("abhishek")).ok is True


async def test_a_non_holder_cannot_release_the_soul() -> None:
    """A keeper that lost its lease must not knock the new holder off."""
    lease = FakeSoulLease()
    await lease.claim("afreen")

    await lease.release("abhishek")

    assert await lease.holder() == "afreen"


async def test_lid_slam_frees_the_soul_after_the_expiry_delay() -> None:
    """Nobody says goodbye; Switch notices the dead session and frees the role."""
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock, expiry_delay_s=8.0)
    await lease.claim("afreen")

    expiring = asyncio.create_task(lease.expire("afreen"))
    await asyncio.sleep(0)

    await clock.advance(7)
    assert await lease.holder() == "afreen", "must not free early"

    await clock.advance(2)
    await expiring
    assert await lease.holder() is None


async def test_expiry_does_not_evict_whoever_came_after() -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock, expiry_delay_s=8.0)
    await lease.claim("afreen")
    expiring = asyncio.create_task(lease.expire("afreen"))
    await asyncio.sleep(0)

    await lease.release("afreen")
    await lease.claim("abhishek")
    await clock.advance(10)
    await expiring

    assert await lease.holder() == "abhishek"


async def test_watch_reports_every_change_including_frees() -> None:
    lease = FakeSoulLease()
    seen: list[str | None] = []
    stream = lease.watch()

    async def collect() -> None:
        async for holder in stream:
            seen.append(holder)

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)

    await lease.claim("afreen")
    await lease.release("afreen")
    await lease.claim("akshay")
    await asyncio.sleep(0)

    task.cancel()
    assert seen == ["afreen", None, "akshay"]


@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    actions=st.lists(
        st.tuples(st.sampled_from(HOSTS), st.sampled_from(["claim", "release", "expire"])),
        min_size=1,
        max_size=40,
    )
)
@pytest.mark.asyncio
async def test_no_sequence_of_actions_ever_produces_two_holders(
    actions: list[tuple[str, str]],
) -> None:
    """Hammer the lease with arbitrary interleavings; one holder, always.

    ``holder()`` returning a single value is the invariant by construction, so
    what this really proves is that no action path leaves a *stale* holder: a
    released or expired soul is genuinely free, and a claim only ever succeeds
    when it was.
    """
    lease = FakeSoulLease(expiry_delay_s=0.0)
    believed_holders: set[str] = set()

    for host, action in actions:
        if action == "claim":
            result = await lease.claim(host)
            if result.ok:
                believed_holders.add(host)
            else:
                believed_holders.discard(host)
        elif action == "release":
            await lease.release(host)
            believed_holders.discard(host)
        else:
            await lease.expire(host, after_s=0)
            believed_holders.discard(host)

        holder = await lease.holder()
        assert len(believed_holders) <= 1, f"two agents think they are Hermit: {believed_holders}"
        assert believed_holders in ({holder} if holder else set(), set())

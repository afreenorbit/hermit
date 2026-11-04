"""Three hosts, one soul, all fakes wired together.

This is the whole product in miniature and it runs in milliseconds with no
Switch, no network and no API keys. When Phase 3's real state machine lands it
should make this test shorter, not different: the sequence below is the
contract.
"""

from __future__ import annotations

import asyncio

from hermit_keeper import ledger
from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.events import Event, EventType
from hermit_keeper.lease.fake import FakeSoulLease
from hermit_keeper.presence.fake import ScriptedPresence
from hermit_keeper.room.fake import FakeRoomHub

DEN = "hermit-den"
LEDGER = "hermit-ledger"

HOSTS = {
    "afreen": ("claude-code", "Indiranagar"),
    "abhishek": ("opencode", "Kengeri"),
    "akshay": ("codex", "Koramangala"),
}


class MiniKeeper:
    """The smallest thing that behaves like a keeper, for wiring the fakes.

    Phase 3 replaces this with the real state machine; the calls it makes are
    the ones the real one will make.
    """

    def __init__(self, host: str, clock: FakeClock, lease: FakeSoulLease, hub: FakeRoomHub):
        provider, self.city = HOSTS[host]
        self.host = host
        self.clock = clock
        self.lease = lease
        self.room = hub.client(f"keeper-{host}")
        self.brain = FakeBrain(f"hermit-{host}", provider, den=hub.client(f"hermit-{host}"))

    async def _log(self, event_type: EventType, **data: object) -> None:
        event = Event(type=event_type, host=self.host, ts=self.clock.now(), data=data)
        await self.room.post(LEDGER, ledger.encode(event))

    async def arrive(self, previous_host: str | None) -> bool:
        result = await self.lease.claim(f"hermit-{self.host}")
        if not result.ok:
            await self._log(EventType.SOUL_CLAIM_REJECTED, holder=result.holder)
            return False
        await self._log(EventType.SOUL_CLAIMED, holder=self.host, previous_holder=previous_host)
        await self.brain.cue(
            "ARRIVE", {"city": self.city, "temp_c": 26, "previous_host": previous_host or "nobody"}
        )
        return True

    async def depart(self, reason: str = "idle") -> None:
        await self._log(EventType.DEPARTURE_STARTED, reason=reason)
        await self.brain.cue("ASK_FAVOR", {})
        await self.brain.cue("DEPART", {"reason": reason})
        await self.lease.release(f"hermit-{self.host}")
        await self._log(EventType.SOUL_RELEASED, departure="graceful")


async def test_a_day_of_hermit_moving_between_three_friends() -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock, expiry_delay_s=8.0)
    hub = FakeRoomHub(clock=clock)
    keepers = {host: MiniKeeper(host, clock, lease, hub) for host in HOSTS}

    # Afreen is at her laptop for 90 minutes, then goes idle.
    afreen_presence = ScriptedPresence(clock, [(0, True), (5400, False)])
    assert afreen_presence.present() is True

    # Afreen is up first and takes the soul.
    assert await keepers["afreen"].arrive(previous_host=None) is True
    assert await lease.holder() == "hermit-afreen"

    # Abhishek wakes while Afreen still has it: exactly one Hermit.
    assert await keepers["abhishek"].arrive(previous_host="afreen") is False
    assert await lease.holder() == "hermit-afreen"

    # Afreen goes idle and hands over.
    await clock.advance(5400)
    assert afreen_presence.present() is False, "presence is what triggers the handoff"
    assert await afreen_presence.idle_seconds() == 0
    await clock.advance(300)
    assert await afreen_presence.idle_seconds() == 300
    await keepers["afreen"].depart()
    assert await lease.holder() is None

    assert await keepers["abhishek"].arrive(previous_host="afreen") is True

    # Abhishek slams the lid. Nobody says goodbye; the lease expires.
    await clock.advance(3600)
    expiring = asyncio.create_task(lease.expire("hermit-abhishek"))
    await asyncio.sleep(0)
    await clock.advance(10)
    await expiring
    assert await lease.holder() is None

    assert await keepers["akshay"].arrive(previous_host="abhishek") is True

    # The ledger is the journey's source of truth: it must replay cleanly.
    lines = [m.text for m in await hub.client("reader").history(LEDGER)]
    events = [e for e in (ledger.decode(line) for line in lines) if e is not None]
    assert len(events) == len(lines), "every ledger line must decode"

    claimed = [e.host for e in events if e.type is EventType.SOUL_CLAIMED]
    assert claimed == ["afreen", "abhishek", "akshay"], "the journey, in order"

    rejected = [e for e in events if e.type is EventType.SOUL_CLAIM_REJECTED]
    assert len(rejected) == 1, "Abhishek's early claim was refused and recorded"

    # Only Afreen left gracefully; Abhishek's lid-slam left no SOUL_RELEASED,
    # which is exactly how Phase 4 will mark that stop as an abrupt departure.
    released = [e.host for e in events if e.type is EventType.SOUL_RELEASED]
    assert released == ["afreen"]


async def test_the_den_shows_one_memory_in_three_voices() -> None:
    clock = FakeClock()
    lease = FakeSoulLease(clock=clock)
    hub = FakeRoomHub(clock=clock)
    keepers = {host: MiniKeeper(host, clock, lease, hub) for host in HOSTS}

    previous: str | None = None
    for host in ("afreen", "abhishek", "akshay"):
        assert await keepers[host].arrive(previous) is True
        await clock.advance(600)
        await keepers[host].depart()
        previous = host

    den = [m.text for m in await hub.client("reader").history(DEN)]
    arrivals = [
        line for line in den if "Indiranagar" in line or "Kengeri" in line or "Koramangala" in line
    ]

    assert len(arrivals) == 3
    assert len(set(arrivals)) == 3, "three brains, three different voices"
    # The shared memory: each one knows who had Hermit before it.
    assert "afreen" in arrivals[1]
    assert "abhishek" in arrivals[2]

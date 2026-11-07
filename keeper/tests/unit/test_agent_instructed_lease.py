"""The real lease strategy: the brain holds the soul, the ledger is the witness.

The rule under test throughout: **never believe an ACK alone.** A coding agent
reporting success it did not achieve is the most likely way two friends end
up each thinking they have Hermit, so success needs the brain's ``ok:true``
*and* the ledger fold naming us.

These run over the in-memory room hub; ``tests/integration/test_switch_standin.py``
runs the same classes over real HTTP.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta

from hermit_keeper.brain.ledger_director import LedgerBrainDirector
from hermit_keeper.brain.protocol import format_ack, format_cue, parse_cue
from hermit_keeper.clock import RealClock
from hermit_keeper.events import Event, EventType
from hermit_keeper.lease.agent_instructed import AgentInstructedLease
from hermit_keeper.ledger import decode, encode
from hermit_keeper.room.fake import FakeRoomHub

LEDGER = "hermit-ledger"

Verdict = Callable[[str], bool | None]  # cue -> ok, or None to stay silent


class BrainBot:
    """A brain in the fake hub: answers its own cues according to ``verdict``."""

    def __init__(self, hub: FakeRoomHub, host: str, verdict: Verdict) -> None:
        self.room = hub.client(f"hermit-{host}")
        self.name = f"hermit-{host}"
        self.verdict = verdict
        self.cues: list[str] = []
        self.before_ack: Callable[[str], object] | None = None
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        async for message in self.room.stream(LEDGER):
            cue = parse_cue(message.text)
            if cue is None or cue.to != self.name:
                continue
            self.cues.append(cue.cue)
            ok = self.verdict(cue.cue)
            if ok is None:
                continue
            if self.before_ack is not None:
                result = self.before_ack(cue.cue)
                if asyncio.iscoroutine(result):
                    await result
            await self.room.post(LEDGER, format_ack(cue.cue, ok, cue.id))

    def stop(self) -> None:
        self._task.cancel()


def build(
    hub: FakeRoomHub, host: str = "afreen", verdict: Verdict = lambda _c: True
) -> tuple[AgentInstructedLease, BrainBot]:
    room = hub.client(f"keeper-{host}")
    director = LedgerBrainDirector(room, f"hermit-{host}", host)
    lease = AgentInstructedLease(
        director,
        room,
        host,
        clock=RealClock(),
        ack_timeout_s=0.5,
        settle_s=0.05,
        heartbeat_s=1.0,
        lease_expiry_s=1.0,
    )
    return lease, BrainBot(hub, host, verdict)


def ledger_events(hub: FakeRoomHub) -> list[Event]:
    return [e for e in (decode(m.text) for m in hub.rooms.get(LEDGER, [])) if e is not None]


async def test_claim_cues_the_brain_and_records_the_acked_claim() -> None:
    hub = FakeRoomHub()
    lease, brain = build(hub)
    await asyncio.sleep(0)

    result = await lease.claim("hermit-afreen")

    assert result.ok and result.holder == "hermit-afreen"
    assert brain.cues == ["CLAIM_SOUL"]
    claimed = [e for e in ledger_events(hub) if e.type is EventType.SOUL_CLAIMED]
    assert claimed and claimed[0].data["ack"] == lease.heartbeat_data()["soul"]["ack"]
    assert await lease.holder() == "hermit-afreen"
    brain.stop()


async def test_an_honest_refusal_is_not_a_claim() -> None:
    hub = FakeRoomHub()
    lease, brain = build(hub, verdict=lambda c: c != "CLAIM_SOUL")
    await asyncio.sleep(0)

    result = await lease.claim("hermit-afreen")

    assert result.ok is False
    assert await lease.holder() is None
    assert lease.heartbeat_data() == {"soul": None}
    brain.stop()


async def test_a_silent_brain_times_out_as_a_failed_claim() -> None:
    hub = FakeRoomHub()
    lease, brain = build(hub, verdict=lambda _c: None)
    await asyncio.sleep(0)

    result = await lease.claim("hermit-afreen")

    assert result.ok is False
    brain.stop()


async def test_no_cue_is_sent_for_a_soul_somebody_else_holds() -> None:
    hub = FakeRoomHub()
    other = hub.client("hermit-akshay")
    akshay = hub.client("keeper-akshay")
    await akshay.post(LEDGER, format_cue("hermit-akshay", "CLAIM_SOUL", "cue_a", "akshay", {}))
    await other.post(LEDGER, format_ack("CLAIM_SOUL", True, "cue_a"))
    lease, brain = build(hub)
    await asyncio.sleep(0)

    result = await lease.claim("hermit-afreen")

    assert result.ok is False and result.holder == "hermit-akshay"
    assert brain.cues == []
    brain.stop()


async def test_release_cues_the_brain_and_names_the_claim_it_ends() -> None:
    hub = FakeRoomHub()
    lease, brain = build(hub)
    await asyncio.sleep(0)
    assert (await lease.claim("hermit-afreen")).ok

    await lease.release("hermit-afreen")

    assert brain.cues == ["CLAIM_SOUL", "RELEASE_SOUL"]
    released = [e for e in ledger_events(hub) if e.type is EventType.SOUL_RELEASED]
    assert released[-1].data["confirmed"] is True
    assert released[-1].data["releases"]
    assert await lease.holder() is None
    brain.stop()


async def test_releasing_a_soul_we_do_not_hold_does_nothing() -> None:
    hub = FakeRoomHub()
    lease, brain = build(hub)
    await asyncio.sleep(0)

    await lease.release("hermit-afreen")

    assert brain.cues == []
    brain.stop()


async def test_losing_a_ledger_race_concedes_even_after_an_ok_ack() -> None:
    """Our brain says yes, but an earlier claim surfaces during the settle window."""
    hub = FakeRoomHub()
    lease, brain = build(hub)
    akshay_keeper = hub.client("keeper-akshay")

    async def earlier_rival(cue: str) -> None:
        if cue != "CLAIM_SOUL":
            return
        # A claim whose ACK is older than ours appears in the ledger.
        ts = (RealClock().now() - timedelta(seconds=0.2)).isoformat()
        await akshay_keeper.post(
            LEDGER,
            encode(
                Event(
                    type=EventType.SOUL_CLAIMED,
                    host="akshay",
                    ts=RealClock().now(),
                    data={"holder": "akshay", "ack": "$rival", "ack_ts": ts},
                )
            ),
        )

    brain.before_ack = earlier_rival
    await asyncio.sleep(0)

    result = await lease.claim("hermit-afreen")

    assert result.ok is False, "an ok ACK that loses in the ledger must not make us Hermit"
    assert result.holder == "hermit-akshay"
    assert brain.cues == ["CLAIM_SOUL", "RELEASE_SOUL"], "the loser tells its brain to let go"
    assert lease.heartbeat_data() == {"soul": None}
    brain.stop()


async def test_a_late_ack_after_a_timeout_is_released_as_an_orphan() -> None:
    hub = FakeRoomHub()
    lease, brain = build(hub)
    keeper = hub.client("keeper-afreen")
    # Our brain's ACK for a cue this keeper never saw confirmed.
    await keeper.post(LEDGER, format_cue("hermit-afreen", "CLAIM_SOUL", "cue_old", "afreen", {}))
    await hub.client("hermit-afreen").post(LEDGER, format_ack("CLAIM_SOUL", True, "cue_old"))
    await asyncio.sleep(0)

    assert await lease.holder() == "hermit-afreen"
    for _ in range(50):
        if "RELEASE_SOUL" in brain.cues:
            break
        await asyncio.sleep(0.02)
    assert "RELEASE_SOUL" in brain.cues
    for _ in range(50):
        if await lease.holder() is None:
            break
        await asyncio.sleep(0.02)
    assert await lease.holder() is None
    await lease.aclose()
    brain.stop()


class OfflineRoom:
    """A room client that has lost the server."""

    online = False
    listening_since = None

    def __init__(self, inner) -> None:
        self._inner = inner

    async def post(self, room: str, text: str) -> str:
        raise AssertionError("must not post while offline")

    async def history(self, room, since=None, limit=200):
        return await self._inner.history(room, since, limit)


async def test_offline_means_unknown_never_free_and_never_claim() -> None:
    hub = FakeRoomHub()
    room = OfflineRoom(hub.client("keeper-afreen"))
    director = LedgerBrainDirector(room, "hermit-afreen", "afreen")
    lease = AgentInstructedLease(director, room, "afreen", ack_timeout_s=0.1)

    assert lease.switch_state == "offline"
    result = await lease.claim("hermit-afreen")
    assert result.ok is False


async def test_heartbeat_data_names_the_claim_we_hold() -> None:
    hub = FakeRoomHub()
    lease, brain = build(hub)
    await asyncio.sleep(0)
    assert lease.heartbeat_data() == {"soul": None}
    assert (await lease.claim("hermit-afreen")).ok
    soul = lease.heartbeat_data()["soul"]
    assert soul["ack"] and soul["ack_ts"]
    brain.stop()


async def test_standalone_reconnect_does_not_wait_for_a_missing_brain() -> None:
    hub = FakeRoomHub()
    room = hub.client("keeper-afreen")
    room.online = True  # type: ignore[attr-defined]
    director = LedgerBrainDirector(room, "hermit-afreen", "afreen")
    lease = AgentInstructedLease(
        director,
        room,
        "afreen",
        standalone=True,
        settle_s=0.01,
        ack_timeout_s=0.01,
    )
    assert (await lease.claim("hermit-afreen")).ok
    before = len(hub.rooms[LEDGER])

    room.online = False  # type: ignore[attr-defined]
    assert await lease.holder() == "hermit-afreen"
    room.online = True  # type: ignore[attr-defined]
    assert await lease.holder() == "hermit-afreen"
    await asyncio.sleep(0)

    assert len(hub.rooms[LEDGER]) == before
    assert lease._background is None  # no verification task waiting for an AI ACK
    await lease.aclose()

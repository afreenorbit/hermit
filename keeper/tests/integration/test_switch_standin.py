"""The real Switch code path, end to end, over real HTTP — against a STAND-IN.

Three keepers are built by ``build_switch_keeper`` (what ``hermit-keeper run``
uses for ``agent_instructed``) and talk over loopback HTTP to
``sim/switch_standin.py``, which implements only the API surface verified
against switch-v0.9.0. Three stand-in brains follow stage-directions.md and
take the soul through an in-process exclusive role with session leases.

What these prove: the keeper's own code — room client, ledger director,
ledger-observed lease, favor store, runtime, status — behaves correctly when
the server and the brains behave as documented. What they cannot prove: that
real Switch and real coding agents do. That needs ``-m live`` and a server.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import httpx
import pytest
from sim.standin_group import StandinGroup, build_group, fast_timings, wait_for
from sim.switch_standin import StandinSwitch, serve_standin

from hermit_keeper import ledger
from hermit_keeper.api import create_app
from hermit_keeper.events import EventType
from hermit_keeper.statemachine import State

HOSTS = ["afreen", "abhishek", "akshay"]
SPEAKING_MOODS = {"arriving", "visiting"}


@contextlib.asynccontextmanager
async def running_group(
    *, echo_own: bool = False, honest: bool = True, **kw: object
) -> AsyncIterator[StandinGroup]:
    switch = StandinSwitch(long_poll_s=2.0, role_expiry_s=0.3, echo_own=echo_own)
    async with serve_standin(switch) as base_url:
        group = await build_group(switch, base_url, HOSTS, honest=honest, **kw)  # type: ignore[arg-type]
        try:
            yield group
        finally:
            await group.aclose()


class Watchdog:
    """Samples the group continuously and records every invariant breach."""

    def __init__(self, group: StandinGroup, *, check_role: bool = True) -> None:
        self.group = group
        self.check_role = check_role
        self.breaches: list[str] = []
        self.samples = 0
        self._task: asyncio.Task[None] | None = None

    async def _run(self) -> None:
        tick = 0
        while True:
            tick += 1
            holding = self.group.holding()
            if len(holding) > 1:
                self.breaches.append(f"two keepers HOLDING: {holding}")
            roles = self.group.role_holders()
            if len(roles) > 1:
                self.breaches.append(f"two role holders: {roles}")
            if self.check_role:
                for host in holding:
                    if roles != [f"hermit-{host}"]:
                        self.breaches.append(f"{host} HOLDING but role held by {roles}")
            if tick % 5 == 0:
                moods = []
                for member in self.group.live():
                    status = await member.keeper.runtime.status()
                    if status["mood"] in SPEAKING_MOODS:
                        moods.append(member.host)
                if len(moods) > 1:
                    self.breaches.append(f"two speaking moods: {moods}")
            self.samples += 1
            await asyncio.sleep(0.005)

    def __enter__(self) -> Watchdog:
        self._task = asyncio.create_task(self._run())
        return self

    def __exit__(self, *_: object) -> None:
        if self._task is not None:
            self._task.cancel()


async def holders_agree(group: StandinGroup, expected: str | None) -> bool:
    for member in group.live():
        status = await member.keeper.runtime.status()
        if status["soul_holder"] != expected:
            return False
    return True


async def settled_on_one(group: StandinGroup) -> str | None:
    holding = group.holding()
    if len(holding) != 1:
        return None
    winner = holding[0]
    if group.role_holders() != [f"hermit-{winner}"]:
        return None
    if any(m.state is State.CLAIMING for m in group.live()):
        return None
    return winner if await holders_agree(group, winner) else None


def ledger_events(group: StandinGroup, host: str) -> list[ledger.Event]:
    room = group.members[host].keeper.room
    return [e for e in (ledger.decode(m.text) for m in room._buffer.get("hermit-ledger", [])) if e]


# -- 1. one holder, ten simultaneous races -------------------------------------


@pytest.mark.parametrize("echo_own", [False, True], ids=["no-own-echo", "own-echo"])
async def test_ten_simultaneous_claim_races_have_exactly_one_winner(echo_own: bool) -> None:
    async with running_group(echo_own=echo_own) as group:
        group.set_presence("asleep")
        group.start()
        winners: list[str] = []
        with Watchdog(group) as dog:
            for _round in range(10):
                # Everyone wakes at the same instant and reaches for the soul.
                group.set_presence("awake")
                assert await wait_for(lambda: settled_on_one(group), timeout_s=10), (
                    f"round {_round}: no single settled holder: holding={group.holding()} "
                    f"roles={group.role_holders()}"
                )
                winner = await settled_on_one(group)
                assert winner is not None
                winners.append(winner)
                # Everyone leaves; wait until the soul is provably free everywhere.
                group.set_presence("asleep")
                assert await wait_for(
                    lambda: (
                        not group.holding()
                        and not group.role_holders()
                        and all(m.state is State.ASLEEP for m in group.live())
                    ),
                    timeout_s=10,
                )
                assert await wait_for(lambda: holders_agree(group, None), timeout_s=5)
        assert dog.breaches == [], dog.breaches[:5]
        assert dog.samples > 100
        assert len(winners) == 10
        if echo_own:
            # The stand-in handed own posts back; the client must have
            # recognised them instead of seeing every line twice.
            assert all(m.keeper.room.own_echoes_from_server > 0 for m in group.live())


# -- 2. an idle handoff --------------------------------------------------------


async def test_idle_handoff_moves_the_soul_and_everyone_agrees() -> None:
    async with running_group() as group:
        group.set_presence("asleep", "abhishek", "akshay")
        group.start()
        with Watchdog(group) as dog:
            assert await wait_for(lambda: settled_on_one(group), timeout_s=10)
            assert group.holding() == ["afreen"]

            group.set_presence("awake", "abhishek")
            group.set_presence("asleep", "afreen")  # afreen goes idle

            assert await wait_for(lambda: group.holding() == ["abhishek"], timeout_s=10)
            assert await wait_for(lambda: holders_agree(group, "abhishek"), timeout_s=5)
            assert group.role_holders() == ["hermit-abhishek"]
        assert dog.breaches == []

        brain = group.members["abhishek"].brain
        assert await wait_for(lambda: any(c == "ARRIVE" for c, _ in brain.cues), timeout_s=5)
        arrive = [ctx for cue, ctx in brain.cues if cue == "ARRIVE"]
        assert arrive[-1]["previous_host"] == "afreen"
        assert arrive[-1]["previous_departure"] == "graceful"
        released = [
            e
            for e in ledger_events(group, "akshay")
            if e.type is EventType.SOUL_RELEASED and e.host == "afreen"
        ]
        assert any(e.data.get("confirmed") is True for e in released), (
            "the lease records a release only after the brain confirmed it"
        )


# -- 3. lid slam ---------------------------------------------------------------


async def test_lid_slam_expires_and_another_host_claims_recorded_abrupt() -> None:
    async with running_group() as group:
        group.set_presence("asleep", "abhishek", "akshay")
        group.start()
        assert await wait_for(lambda: settled_on_one(group), timeout_s=10)
        assert group.holding() == ["afreen"]
        group.set_presence("awake", "abhishek", "akshay")
        await asyncio.sleep(0.5)
        assert group.holding() == ["afreen"], "nobody may take a soul that is held"

        with Watchdog(group) as dog:
            await group.lid_slam("afreen")
            # Nothing said goodbye. The holder's silence + Switch's expiry free it.
            assert await wait_for(lambda: len(group.holding()) == 1, timeout_s=10)
            new_host = group.holding()[0]
            assert new_host in ("abhishek", "akshay")
            assert await wait_for(lambda: holders_agree(group, new_host), timeout_s=5)
            assert group.role_holders() == [f"hermit-{new_host}"]
        assert dog.breaches == []

        brain = group.members[new_host].brain
        assert await wait_for(lambda: any(c == "ARRIVE" for c, _ in brain.cues), timeout_s=5)
        arrive = [ctx for cue, ctx in brain.cues if cue == "ARRIVE"]
        assert arrive[-1]["previous_host"] == "afreen"
        assert arrive[-1]["previous_departure"] == "abrupt"

        def announced() -> list[ledger.Event]:
            return [
                e
                for e in ledger_events(group, new_host)
                if e.type is EventType.ARRIVAL_ANNOUNCED and e.host == new_host
            ]

        assert await wait_for(lambda: announced(), timeout_s=5)
        assert announced()[-1].data["previous_departure"] == "abrupt"


# -- 4. Switch goes away and comes back ----------------------------------------


async def test_switch_outage_reports_offline_without_a_second_visitor_then_recovers() -> None:
    async with running_group() as group:
        group.set_presence("asleep", "abhishek", "akshay")
        group.start()
        assert await wait_for(lambda: settled_on_one(group), timeout_s=10)
        group.set_presence("awake", "abhishek", "akshay")
        await asyncio.sleep(0.3)

        with Watchdog(group) as dog:
            group.switch.set_down(True)
            assert await wait_for(
                lambda: all(not m.keeper.room.online for m in group.live()), timeout_s=5
            )
            # Longer than the stale threshold: silence while deaf must not free the soul.
            await asyncio.sleep(2.0)
            for member in group.live():
                status = await member.keeper.runtime.status()
                assert status["switch"] == "offline"
                assert status["soul_holder"] is None, "unknown, not stale"
                assert status["mood"] == "offline"
                snapshot = await member.keeper.runtime.group_status()
                assert snapshot["switch"] == "offline"
                assert snapshot["soul_holder"] is None
                assert not any(h["mood"] in SPEAKING_MOODS for h in snapshot["hosts"])
            assert group.holding() == ["afreen"], "nobody claimed while Switch was down"
            # And the critter's own API says so, for the holder and a waiter alike.
            for host in ("afreen", "akshay"):
                api = create_app(group.members[host].keeper.runtime)
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=api), base_url="http://127.0.0.1"
                ) as local:
                    status = (await local.get("/v1/status")).json()
                    assert (status["switch"], status["mood"], status["soul_holder"]) == (
                        "offline",
                        "offline",
                        None,
                    )
                    snapshot = (await local.get("/v1/group/status")).json()
                    assert snapshot["switch"] == "offline" and snapshot["soul_holder"] is None

            group.switch.set_down(False)
            assert await wait_for(
                lambda: all(m.keeper.room.online for m in group.live()), timeout_s=5
            )
            assert await wait_for(lambda: holders_agree(group, "afreen"), timeout_s=5)
            for member in group.live():
                assert (await member.keeper.runtime.status())["switch"] == "online"
            # The holder re-confirmed with its brain after the gap.
            assert await wait_for(
                lambda: (
                    sum(1 for c, _ in group.members["afreen"].brain.cues if c == "CLAIM_SOUL") >= 2
                ),
                timeout_s=5,
            )
            await asyncio.sleep(0.5)
            assert group.holding() == ["afreen"]
            assert group.role_holders() == ["hermit-afreen"]
        assert dog.breaches == []


# -- 5. favors cross laptops ---------------------------------------------------


async def test_a_favor_left_on_one_laptop_is_delivered_on_the_next() -> None:
    timings = fast_timings(favor_wait_s=5.0)
    async with running_group(timings=timings, humans=["friend-afreen"]) as group:
        group.set_presence("asleep", "abhishek", "akshay")
        group.start()
        assert await wait_for(lambda: group.holding() == ["afreen"], timeout_s=10)

        group.set_presence("awake", "abhishek")
        group.set_presence("asleep", "afreen")
        afreen = group.members["afreen"].brain
        assert await wait_for(lambda: any(c == "ASK_FAVOR" for c, _ in afreen.cues), timeout_s=10)
        await group.say_in_den("friend-afreen", "the last song that got stuck in your head")

        assert await wait_for(lambda: group.holding() == ["abhishek"], timeout_s=10)
        abhishek = group.members["abhishek"].brain
        assert await wait_for(lambda: any(c == "ARRIVE" for c, _ in abhishek.cues), timeout_s=5)
        arrive = [ctx for cue, ctx in abhishek.cues if cue == "ARRIVE"][-1]
        assert arrive["favor"]["text"] == "the last song that got stuck in your head"
        assert arrive["favor"]["left_by"] == "afreen"
        assert await wait_for(
            lambda: any("the last song" in line for line in abhishek.said), timeout_s=5
        ), "delivered in the den"
        assert await wait_for(
            lambda: any(
                e.type is EventType.FAVOR_ASSIGNED and e.data.get("assignee") == "abhishek"
                for e in ledger_events(group, "akshay")
            ),
            timeout_s=5,
        ), "the hand-over is recorded in the ledger for every laptop"


# -- 6. a brain that lies ------------------------------------------------------


async def test_brains_that_ack_success_they_did_not_get_still_yield_one_holder() -> None:
    """Every brain claims ok:true. The ledger rule must still converge on one."""
    async with running_group(honest=False) as group:
        group.set_presence("asleep")
        group.start()
        await asyncio.sleep(0.6)  # past warm-up, so all three race together
        with Watchdog(group, check_role=False) as dog:
            group.set_presence("awake")
            assert await wait_for(
                lambda: (
                    len(group.holding()) == 1
                    and not any(m.state is State.CLAIMING for m in group.live())
                ),
                timeout_s=10,
            )
            winner = group.holding()[0]
            assert await wait_for(lambda: holders_agree(group, winner), timeout_s=5)
            await asyncio.sleep(0.5)
            assert group.holding() == [winner]
        assert dog.breaches == []
        losers = [m for m in group.live() if m.host != winner]
        conceded = [m for m in losers if any(c == "RELEASE_SOUL" for c, _ in m.brain.cues)]
        assert conceded, "a keeper that lost the ledger race must tell its brain to let go"

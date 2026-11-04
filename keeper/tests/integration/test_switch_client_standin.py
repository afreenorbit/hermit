"""SwitchRoomClient over real HTTP against the STAND-IN.

Two behaviours of real Switch are still unmeasured, so the stand-in is run
both ways and the client must be right either way:

* whether ``/events`` hands an agent its own posts back, and
* how long an empty long-poll is held.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import httpx
import pytest
from sim.standin_group import wait_for
from sim.switch_standin import StandinSwitch, serve_standin

from hermit_keeper.room.switch_client import SwitchRoomClient, probe


@contextlib.asynccontextmanager
async def two_agents(
    switch: StandinSwitch, **client_kw: float
) -> AsyncIterator[tuple[str, SwitchRoomClient, SwitchRoomClient, httpx.AsyncClient]]:
    async with serve_standin(switch) as base_url:
        a_id, a_key = switch.register("keeper-afreen")
        b_id, b_key = switch.register("keeper-akshay")
        ledger = switch.create_room("hermit-ledger", [a_id, b_id])
        rooms = {"hermit-ledger": ledger}
        http = httpx.AsyncClient()
        a = SwitchRoomClient(
            base_url, a_id, a_key, rooms, http, agent_name="keeper-afreen", **client_kw
        )
        b = SwitchRoomClient(
            base_url, b_id, b_key, rooms, http, agent_name="keeper-akshay", **client_kw
        )
        try:
            yield base_url, a, b, http
        finally:
            await a.aclose()
            await b.aclose()
            await http.aclose()


@pytest.mark.parametrize("echo_own", [False, True], ids=["no-own-echo", "own-echo"])
async def test_a_post_is_seen_once_by_its_sender_and_once_by_the_room(echo_own: bool) -> None:
    switch = StandinSwitch(long_poll_s=1.0, echo_own=echo_own)
    async with two_agents(switch, retry_s=0.05) as (_url, a, b, _http):
        a.start()
        b.start()
        assert await wait_for(lambda: a.online and b.online, timeout_s=5)

        event_id = await a.post("hermit-ledger", "HERMIT/1 hello")
        assert event_id.startswith("$ev_")

        assert await wait_for(
            lambda: [m.id for m in b._buffer.get("hermit-ledger", [])] == [event_id], timeout_s=5
        )
        received = b._buffer["hermit-ledger"][0]
        assert (received.sender, received.text) == ("keeper-afreen", "HERMIT/1 hello")

        if echo_own:
            assert await wait_for(lambda: a.own_echoes_from_server == 1, timeout_s=5)
        mine = await a.history("hermit-ledger")
        assert [m.id for m in mine] == [event_id], "own post visible exactly once"
        if echo_own:
            assert mine[0].ts == received.ts, "the server's timestamp replaces the local one"


async def test_offline_is_reported_and_recovered() -> None:
    switch = StandinSwitch(long_poll_s=1.0)
    async with two_agents(switch, retry_s=0.05, max_retry_s=0.1) as (_url, a, _b, _http):
        a.start()
        assert await wait_for(lambda: a.online, timeout_s=5)
        first_stretch = a.listening_since

        switch.set_down(True)
        assert await wait_for(lambda: not a.online, timeout_s=5)
        assert a.listening_since is None
        assert a.last_error and "503" in a.last_error

        switch.set_down(False)
        assert await wait_for(lambda: a.online, timeout_s=5)
        assert a.listening_since is not None and a.listening_since > first_stretch


async def test_a_long_poll_held_past_our_timeout_is_not_an_outage() -> None:
    switch = StandinSwitch(long_poll_s=5.0)
    async with two_agents(switch, poll_timeout_s=0.3, retry_s=0.05) as (_url, a, _b, _http):
        a.start()
        assert await wait_for(lambda: a.online, timeout_s=3)
        await wait_for(lambda: False, timeout_s=1.0)
        assert a.online


async def test_history_never_drains_the_queue_itself() -> None:
    """Only the poller drains; reading the buffer twice changes nothing."""
    switch = StandinSwitch(long_poll_s=0.5)
    async with two_agents(switch, retry_s=0.05) as (_url, a, b, _http):
        a.start()
        b.start()
        await a.post("hermit-ledger", "one")
        assert await wait_for(lambda: len(b._buffer.get("hermit-ledger", [])) == 1, timeout_s=5)
        assert len(await b.history("hermit-ledger")) == 1
        assert len(await b.history("hermit-ledger")) == 1


async def test_probe_proves_the_key_without_touching_the_queue() -> None:
    switch = StandinSwitch(long_poll_s=0.5)
    async with two_agents(switch) as (url, a, _b, http):
        good = await probe(url, a.agent_id, a._api_key, a.room_id("hermit-ledger"), http)
        assert good["ok"] is True
        assert len(good["verified_now"]) == 2
        assert a._api_key not in str(good)

        bad = await probe(url, a.agent_id, "wrong-key", a.room_id("hermit-ledger"), http)
        assert bad["ok"] is False
        assert any("rejected" in line for line in bad["failed_now"])

        missing = await probe(url, a.agent_id, None, a.room_id("hermit-ledger"), http)
        assert missing["ok"] is False

    gone = await probe("http://127.0.0.1:9", "x", "y", "z")
    assert gone["ok"] is False
    assert any("unreachable" in line for line in gone["failed_now"])

"""Against a REAL Switch server. Deselected in CI (`-m "not live"`).

Run on the Switch host (or over Tailscale) with two registered keeper agents
that are both members of the ledger room::

    export HERMIT_LIVE_SWITCH_URL=http://127.0.0.1:8000
    export HERMIT_LIVE_LEDGER_ROOM=<ledger room uuid>
    export HERMIT_LIVE_A_ID=<agent uuid>  HERMIT_LIVE_A_KEY=<its api_key>
    export HERMIT_LIVE_B_ID=<agent uuid>  HERMIT_LIVE_B_KEY=<its api_key>
    pytest -m live -s tests/switch_live

Stop any keeper using these agents first: `/events` drains once, and a running
keeper would eat the messages this test is waiting for.

These answer the two questions the stand-in has to guess at, and print the
answers so they can go into docs/switch-facts.md:

* does `/events` hand an agent its own posts back?
* do senders arrive as agent names or uuids?

What they cannot do is touch the soul role: that is MCP-only, and needs a
connected coding agent (docs/actual-test.md, Step 2).
"""

from __future__ import annotations

import asyncio
import os

import httpx
import pytest

from hermit_keeper.room.switch_client import SwitchRoomClient, probe

pytestmark = pytest.mark.live

NEEDED = [
    "HERMIT_LIVE_SWITCH_URL",
    "HERMIT_LIVE_LEDGER_ROOM",
    "HERMIT_LIVE_A_ID",
    "HERMIT_LIVE_A_KEY",
    "HERMIT_LIVE_B_ID",
    "HERMIT_LIVE_B_KEY",
]


@pytest.fixture
def env() -> dict[str, str]:
    missing = [name for name in NEEDED if not os.environ.get(name)]
    if missing:
        pytest.skip(f"set {', '.join(missing)} to run against a real Switch")
    return {name: os.environ[name] for name in NEEDED}


async def test_probe_against_the_real_server(env: dict[str, str]) -> None:
    result = await probe(
        env["HERMIT_LIVE_SWITCH_URL"],
        env["HERMIT_LIVE_A_ID"],
        env["HERMIT_LIVE_A_KEY"],
        env["HERMIT_LIVE_LEDGER_ROOM"],
    )
    print(result)
    assert result["ok"], result["failed_now"]


async def test_two_keepers_exchange_a_ledger_line_and_report_echo(env: dict[str, str]) -> None:
    rooms = {"hermit-ledger": env["HERMIT_LIVE_LEDGER_ROOM"]}
    async with httpx.AsyncClient() as http:
        a = SwitchRoomClient(
            env["HERMIT_LIVE_SWITCH_URL"],
            env["HERMIT_LIVE_A_ID"],
            env["HERMIT_LIVE_A_KEY"],
            rooms,
            http,
            agent_name="live-a",
        )
        b = SwitchRoomClient(
            env["HERMIT_LIVE_SWITCH_URL"],
            env["HERMIT_LIVE_B_ID"],
            env["HERMIT_LIVE_B_KEY"],
            rooms,
            http,
            agent_name="live-b",
        )
        a.start()
        b.start()
        try:
            for _ in range(100):
                if a.online and b.online:
                    break
                await asyncio.sleep(0.1)
            assert a.online and b.online, (a.last_error, b.last_error)

            marker = f"HERMIT-LIVE-TEST {os.getpid()}"
            event_id = await a.post("hermit-ledger", marker)
            received = None
            for _ in range(300):
                received = next(
                    (m for m in await b.history("hermit-ledger") if m.text == marker), None
                )
                if received is not None:
                    break
                await asyncio.sleep(0.1)
            assert received is not None, "B never received A's ledger line"
            assert received.id == event_id, "event ids must match for echo de-duplication"
            await asyncio.sleep(3.0)  # give an own-echo time to arrive
            mine = [m for m in await a.history("hermit-ledger") if m.text == marker]
            assert len(mine) == 1, "the sender sees its own post exactly once"
            print(
                "\nREAL SWITCH ANSWERS:\n"
                f"  /events returns own posts: {a.own_echoes_from_server > 0}\n"
                f"  sender as received by B:   {received.sender!r}\n"
            )
        finally:
            await a.aclose()
            await b.aclose()

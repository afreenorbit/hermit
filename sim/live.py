"""Three real keepers on one machine, sharing one soul. Owner: Afreen.

    python -m sim live
    python -m sim live --hosts afreen,abhishek,akshay --base-port 47801

This exists because of a trap: three keepers started separately in `fake` mode
each build their **own** `FakeSoulLease`, so all three believe they hold the
soul and all three critters show `visiting`. That is not a demo of anything —
it is three unrelated programs.

Here the three keepers share **one** lease and **one** ledger room, in one
process, which is the same shape real Switch gives them across three laptops.
It is a true test of the handoff, the one-soul invariant and all three
critters at once; it is not a test of the network, and it does not prove the
Switch client works. Those need the real server.

Each keeper serves its own API, so a critter can be pointed at any of them:

    afreen    http://127.0.0.1:47801
    abhishek  http://127.0.0.1:47802
    akshay    http://127.0.0.1:47803

Drive presence by hand — this is the knob the demo uses:

    curl -X POST .../v1/presence/override -d '{"mode":"asleep"}'

**`--switch standin`** runs the *real* Switch code path instead: three keepers
built exactly as `hermit-keeper run` builds them for `agent_instructed`, three
stand-in brains following stage-directions.md, all talking over real loopback
HTTP to `sim/switch_standin.py` — a STAND-IN for Switch, not Switch. A control
port (base port + number of hosts) can slam a lid or take the server down:

    curl -X POST http://127.0.0.1:47804/lid-slam/afreen
    curl -X POST http://127.0.0.1:47804/switch/down     # and /switch/up
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
from typing import Any

import uvicorn
from hermit_keeper.api import create_app
from hermit_keeper.bedtime import is_bedtime
from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import RealClock
from hermit_keeper.config import (
    ApiConfig,
    BedtimeConfig,
    FeatureFlags,
    HostConfig,
    PresenceConfig,
    SwitchConfig,
)
from hermit_keeper.events import EventBus
from hermit_keeper.favors import FavorBook
from hermit_keeper.lease.fake import FakeSoulLease
from hermit_keeper.presence import for_this_platform
from hermit_keeper.presence.composite import CompositePresence
from hermit_keeper.room.fake import FakeRoomHub
from hermit_keeper.runtime import KeeperRuntime

DEN = "hermit-den"
LEDGER = "hermit-ledger"

AREAS = {
    "afreen": ("Indiranagar", "claude-code", 12.9719, 77.6412),
    "abhishek": ("Kengeri", "opencode", 12.9166, 77.4826),
    "akshay": ("Koramangala", "codex", 12.9352, 77.6245),
}


def _config(host: str, port: int) -> HostConfig:
    city, provider, lat, lon = AREAS.get(host, ("Bengaluru", "other", 12.97, 77.59))
    return HostConfig(
        host_id=host,
        display_name=host.title(),
        city=city,
        lat=lat,
        lon=lon,
        timezone="Asia/Kolkata",
        brain_agent=f"hermit-{host}",
        brain_provider=provider,  # type: ignore[arg-type]
        window_dir="~/HermitWindow",
        presence=PresenceConfig(
            # Short thresholds: a demo should not need a five-minute wait to
            # show a handoff. Real configs use the defaults.
            idle_threshold_s=20,
            arrive_debounce_s=5,
            min_dwell_s=15,
            sleep_gap_s=90,
        ),
        bedtime=BedtimeConfig(),
        switch=SwitchConfig(
            server_url="http://127.0.0.1:0",
            den_room=DEN,
            ledger_room=LEDGER,
            lease_strategy="fake",
        ),
        features=FeatureFlags(),
        api=ApiConfig(port=port),
    )


class _Context:
    """Arrival context without the network: the demo must not need weather."""

    def __init__(self, city: str) -> None:
        self.city = city

    async def arrival_context(self) -> dict[str, Any]:
        return {
            "city": self.city,
            "temp_c": 26.0,
            "weather": {"temp_c": 26.0, "code": 1},
        }


def build(hosts: list[str], base_port: int, real_presence: bool) -> list[KeeperRuntime]:
    """One lease, one room hub, N keepers — the shape real Switch gives us."""
    clock = RealClock()
    lease = FakeSoulLease(clock=clock, expiry_delay_s=8.0)
    hub = FakeRoomHub(clock=clock)
    favors = FavorBook(clock, room=DEN)

    runtimes: list[KeeperRuntime] = []
    for index, host in enumerate(hosts):
        config = _config(host, base_port + index)
        room = hub.client(f"keeper-{host}")
        brain = FakeBrain(
            config.brain_agent,
            config.brain_provider,
            den=hub.client(config.brain_agent),
            den_room=DEN,
        )
        source = for_this_platform()
        if not real_presence:
            # Everyone starts awake; the demo drives them with overrides.
            class _Always:
                async def idle_seconds(self) -> float:
                    return 0.0

            source = _Always()  # type: ignore[assignment]

        presence = CompositePresence(
            source,
            clock,
            idle_threshold_s=config.presence.idle_threshold_s,
            arrive_debounce_s=config.presence.arrive_debounce_s,
            sleep_gap_s=config.presence.sleep_gap_s,
        )
        runtimes.append(
            KeeperRuntime(
                config,
                lease,
                room,
                brain,
                presence,
                clock=clock,
                bus=EventBus(),
                is_bedtime=lambda now, c=config: is_bedtime(  # type: ignore[misc]
                    now.astimezone(), c.bedtime.start, c.bedtime.end
                ),
                favors=_HostFavors(favors, host),
                context=_Context(config.city),
                known_hosts=hosts,
            )
        )
    return runtimes


class _HostFavors:
    """One shared favor book, seen from one host's point of view."""

    def __init__(self, book: FavorBook, host: str) -> None:
        self._book = book
        self._host = host

    async def carried(self, for_host: str) -> dict[str, Any] | None:
        return await self._book.carried(for_host)

    async def assign(self, favor_id: str, host: str) -> None:
        await self._book.assign(favor_id, host)

    async def ask_and_capture(self, timeout_s: float) -> dict[str, Any] | None:
        favor = await self._book.leave(
            self._host, "say hello to whoever gets this next"
        )
        return favor.to_dict() if favor else None


async def serve(hosts: list[str], base_port: int, real_presence: bool) -> None:
    runtimes = build(hosts, base_port, real_presence)
    servers = [
        uvicorn.Server(
            uvicorn.Config(
                create_app(runtime),
                host="127.0.0.1",
                port=runtime.config.api.port,
                log_level="warning",
            )
        )
        for runtime in runtimes
    ]

    print("\n  Hermit live harness — one shared soul, three keepers\n")
    for runtime in runtimes:
        print(
            f"    {runtime.config.host_id:<9} http://127.0.0.1:{runtime.config.api.port}"
            f"   ({runtime.config.brain_provider})"
        )
    print(
        "\n  presence: "
        + (
            "this machine's real keyboard"
            if real_presence
            else "forced awake; use overrides"
        )
    )
    print(
        "  drive it:  curl -X POST http://127.0.0.1:"
        f"{base_port}/v1/presence/override -H 'content-type: application/json'"
        ' -d \'{"mode":"asleep"}\''
    )
    print(f"  dashboard: open the map with ?live=http://127.0.0.1:{base_port}\n")

    tasks = [runtime.start() for runtime in runtimes]
    tasks += [asyncio.create_task(server.serve()) for server in servers]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        for runtime in runtimes:
            await runtime.stop()


async def serve_standin_switch(
    hosts: list[str], base_port: int, real_presence: bool, switch_port: int
) -> None:
    """The real keeper code path, over HTTP, against the Switch STAND-IN."""
    from fastapi import FastAPI

    from sim.standin_group import build_group, fast_timings
    from sim.switch_standin import StandinSwitch, serve_standin

    # Demo pacing: quick enough to watch, slow enough to read.
    timings = fast_timings(
        tick_s=0.5,
        heartbeat_s=1.0,
        group_refresh_s=0.5,
        ack_timeout_s=10.0,
        settle_s=0.4,
        favor_wait_s=10.0,
        favor_poll_s=0.25,
        machine={"claim_jitter_s": 1.0, "backoff_s": 5.0},
    )
    switch = StandinSwitch(long_poll_s=10.0, role_expiry_s=3.0)
    async with serve_standin(switch, port=switch_port) as base_url:
        group = await build_group(
            switch,
            base_url,
            hosts,
            timings=timings,
            lease_expiry_s=3.0,
            humans=[f"friend-{h}" for h in hosts],
            api_port_base=base_port,
            demo_presence=True,
            presence_source=for_this_platform() if real_presence else None,
        )

        control = FastAPI(title="stand-in demo control")

        @control.post("/lid-slam/{host}")
        async def lid_slam(host: str) -> dict[str, Any]:
            if host not in group.members or not group.members[host].alive:
                return {"ok": False, "error": f"no live host {host}"}
            await group.lid_slam(host)
            return {"ok": True, "slammed": host}

        @control.post("/switch/{mode}")
        async def outage(mode: str) -> dict[str, Any]:
            switch.set_down(mode == "down")
            return {"ok": True, "switch": "down" if switch.down else "up"}

        @control.post("/favor/{host}")
        async def favor(host: str, body: dict[str, str]) -> dict[str, Any]:
            await group.say_in_den(f"friend-{host}", body.get("text", "say hello to the next one"))
            return {"ok": True}

        @control.get("/")
        async def overview() -> dict[str, Any]:
            return {
                "role_holders_in_standin": group.role_holders(),
                "keepers_holding": group.holding(),
                "brains_said": {h: m.brain.said[-3:] for h, m in group.members.items()},
            }

        control_port = base_port + len(hosts)
        servers = [
            uvicorn.Server(
                uvicorn.Config(
                    create_app(member.keeper.runtime),
                    host="127.0.0.1",
                    port=member.keeper.runtime.config.api.port,
                    log_level="warning",
                )
            )
            for member in group.members.values()
        ]
        servers.append(
            uvicorn.Server(
                uvicorn.Config(control, host="127.0.0.1", port=control_port, log_level="warning")
            )
        )

        print("\n  Hermit live harness — REAL keeper code path, STAND-IN Switch\n")
        print(f"    Switch STAND-IN (not Switch)  {base_url}")
        for member in group.members.values():
            port = member.keeper.runtime.config.api.port
            print(f"    {member.host:<9} http://127.0.0.1:{port}   (keeper-{member.host})")
        print(f"    control   http://127.0.0.1:{control_port}   GET / for who holds what\n")
        print(f"  presence: {'real keyboard' if real_presence else 'forced awake; use overrides'}")
        print(
            "  try:  curl -X POST http://127.0.0.1:"
            f"{base_port}/v1/presence/override -H 'content-type: application/json'"
            ' -d \'{"mode":"asleep"}\''
        )
        print(f"        curl -X POST http://127.0.0.1:{control_port}/lid-slam/{hosts[0]}")
        print(f"        curl -X POST http://127.0.0.1:{control_port}/switch/down   (then /up)\n")

        group.start()
        tasks = [asyncio.create_task(server.serve()) for server in servers]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            for server in servers:
                server.should_exit = True
            await group.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hosts", default="afreen,abhishek,akshay")
    parser.add_argument("--base-port", type=int, default=47801)
    parser.add_argument(
        "--real-presence",
        action="store_true",
        help="use this machine's real idle time for every keeper (they all move together)",
    )
    parser.add_argument(
        "--switch",
        choices=["fake", "standin"],
        default="fake",
        help="fake: one shared in-memory lease. standin: the real Switch code path "
        "over HTTP against sim/switch_standin.py (a stand-in, not Switch)",
    )
    parser.add_argument(
        "--switch-port", type=int, default=0, help="stand-in port (0 = any free port)"
    )
    args = parser.parse_args(argv)
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]

    with contextlib.suppress(KeyboardInterrupt):
        if args.switch == "standin":
            asyncio.run(
                serve_standin_switch(hosts, args.base_port, args.real_presence, args.switch_port)
            )
        else:
            asyncio.run(serve(hosts, args.base_port, args.real_presence))
    return 0

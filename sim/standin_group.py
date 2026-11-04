"""N real keepers + N stand-in brains on one STAND-IN Switch. Owner: Afreen.

Used by the integration tests and by ``python -m sim live --switch standin``.
Every keeper is built by ``hermit_keeper.switch_wiring.build_switch_keeper``,
the same function ``hermit-keeper run`` uses, and talks to the stand-in over
real loopback HTTP. Agents are registered and rooms created over HTTP too;
only the ``soul`` role is defined in-process, because over real Switch that is
an MCP operation a connected brain performs (there is no HTTP route for it).

What this proves and what it does not is spelled out in docs/switch-facts.md:
the keeper's real code path end to end, yes; real Switch's role exclusivity
and its real lease-expiry timing, no.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
from hermit_keeper.config import (
    ApiConfig,
    BedtimeConfig,
    HostConfig,
    PresenceConfig,
    SwitchConfig,
)
from hermit_keeper.statemachine import State
from hermit_keeper.switch_wiring import SwitchKeeper, Timings, build_switch_keeper

from sim.switch_standin import DEFAULT_REGISTRATION_TOKEN, StandinBrain, StandinSwitch

DEN = "hermit-den"
LEDGER = "hermit-ledger"

AREAS = {
    "afreen": ("Indiranagar", "claude-code", 12.9719, 77.6412),
    "abhishek": ("Kengeri", "opencode", 12.9166, 77.4826),
    "akshay": ("Koramangala", "codex", 12.9352, 77.6245),
}


class KillableTransport(httpx.AsyncBaseTransport):
    """A real HTTP transport with an off switch: the laptop's network going away."""

    def __init__(self) -> None:
        self._inner = httpx.AsyncHTTPTransport()
        self.dead = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.dead:
            raise httpx.ConnectError("network gone (lid closed)", request=request)
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


class AlwaysHere:
    """Presence source for a demo or test: a human who never goes idle.

    Drive it with the override (``runtime.set_override("asleep")``), exactly
    as the critter and the demo do.
    """

    async def idle_seconds(self) -> float:
        return 0.0


def fast_timings(**overrides: Any) -> Timings:
    """Production wiring, compressed so a lid slam takes about a second."""
    values: dict[str, Any] = {
        "tick_s": 0.05,
        "heartbeat_s": 0.25,
        "group_refresh_s": 0.1,
        "ack_timeout_s": 3.0,
        "settle_s": 0.15,
        "poll_timeout_s": 5.0,
        "retry_s": 0.05,
        "max_retry_s": 0.2,
        "favor_wait_s": 0.2,
        "favor_poll_s": 0.05,
        "machine": {"claim_jitter_s": 0.0, "backoff_s": 0.3},
    }
    values.update(overrides)
    return Timings(**values)


def host_config(
    host: str,
    base_url: str,
    agent_id: str,
    rooms: dict[str, str],
    *,
    lease_expiry_s: float,
    api_port: int = 47800,
    demo_presence: bool = False,
) -> HostConfig:
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
            idle_threshold_s=20,
            arrive_debounce_s=3 if demo_presence else 0,
            min_dwell_s=15 if demo_presence else 0,
            sleep_gap_s=90,
        ),
        # Never bedtime: tests must not fail because CI ran at 2 a.m. IST.
        bedtime=BedtimeConfig(start="00:00", end="00:00"),
        switch=SwitchConfig(
            server_url=base_url,
            den_room=DEN,
            ledger_room=LEDGER,
            lease_strategy="agent_instructed",
            agent_id=agent_id,
            rooms=rooms,
            lease_expiry_s=lease_expiry_s,
        ),
        api=ApiConfig(port=api_port),
    )


@dataclass
class Member:
    host: str
    keeper: SwitchKeeper
    brain: StandinBrain
    transport: KillableTransport
    alive: bool = True

    @property
    def state(self) -> State:
        return self.keeper.runtime.machine.state


@dataclass
class StandinGroup:
    switch: StandinSwitch
    base_url: str
    members: dict[str, Member]
    rooms: dict[str, str]
    #: Agents that are people, not software: name -> (id, api_key).
    humans: dict[str, tuple[str, str]] = field(default_factory=dict)

    def live(self) -> list[Member]:
        return [m for m in self.members.values() if m.alive]

    def holding(self) -> list[str]:
        return [m.host for m in self.live() if m.state is State.HOLDING]

    def role_holders(self) -> list[str]:
        return self.switch.roles.holders(DEN, "soul")

    def start(self) -> None:
        for member in self.members.values():
            member.brain.start()
            member.keeper.runtime.start()

    def set_presence(self, mode: str, *hosts: str) -> None:
        for host in hosts or tuple(self.members):
            self.members[host].keeper.runtime.set_override(mode)

    async def lid_slam(self, host: str) -> None:
        """Brain session dies, keeper's network dies, nothing says goodbye."""
        member = self.members[host]
        member.alive = False
        member.transport.dead = True
        await member.brain.kill()
        await member.keeper.aclose()

    async def say_in_den(self, human: str, text: str) -> None:
        agent_id, key = self.humans[human]
        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{self.base_url}/agents/{agent_id}/message",
                headers={"authorization": f"Bearer {key}"},
                json={"room_id": self.rooms[DEN], "content": text},
            )
            response.raise_for_status()

    async def aclose(self) -> None:
        for member in self.members.values():
            if member.alive:
                await member.keeper.aclose()
                await member.brain.aclose()
            else:
                await member.brain.aclose()
            await member.transport.aclose()


async def _register(http: httpx.AsyncClient, base_url: str, token: str, name: str) -> tuple[str, str]:
    response = await http.post(
        f"{base_url}/agents",
        headers={"authorization": f"Bearer {token}"},
        json={
            "name": name,
            "description": "hermit stand-in group",
            "connector_type": "custom",
            "integration_profile": {
                "connection_model": "always_on",
                "message_exchange": True,
                "pre_invocation_mediation": [],
                "post_invocation_mediation": [],
                "event_reporting": [],
                "task_protocol": {"can_delegate": False, "can_accept": False},
            },
        },
    )
    response.raise_for_status()
    body = response.json()
    return str(body["id"]), str(body["api_key"])


async def build_group(
    switch: StandinSwitch,
    base_url: str,
    hosts: list[str],
    *,
    timings: Timings | None = None,
    lease_expiry_s: float = 0.5,
    honest: bool = True,
    humans: list[str] | None = None,
    api_port_base: int = 47800,
    demo_presence: bool = False,
    presence_source: Any = None,
) -> StandinGroup:
    """Register everyone, create both rooms, define the soul, build the keepers."""
    token = DEFAULT_REGISTRATION_TOKEN
    async with httpx.AsyncClient() as http:
        keepers = {h: await _register(http, base_url, token, f"keeper-{h}") for h in hosts}
        brains = {h: await _register(http, base_url, token, f"hermit-{h}") for h in hosts}
        people = {p: await _register(http, base_url, token, p) for p in humans or []}

        creator_id, creator_key = keepers[hosts[0]]
        everyone = [i for i, _ in (*keepers.values(), *brains.values())]
        rooms: dict[str, str] = {}
        for name, members in ((DEN, everyone + [i for i, _ in people.values()]), (LEDGER, everyone)):
            response = await http.post(
                f"{base_url}/agents/{creator_id}/moderation/rooms",
                headers={"authorization": f"Bearer {creator_key}"},
                json={"name": name, "description": f"hermit {name}", "agent_ids": members},
            )
            response.raise_for_status()
            rooms[name] = str(response.json()["id"])

    # The one thing HTTP cannot do: a connected brain defines the role over MCP.
    switch.roles.define_role(DEN, "soul", exclusive=True)

    members: dict[str, Member] = {}
    for index, host in enumerate(hosts):
        agent_id, key = keepers[host]
        cfg = host_config(
            host,
            base_url,
            agent_id,
            rooms,
            lease_expiry_s=lease_expiry_s,
            api_port=api_port_base + index,
            demo_presence=demo_presence,
        )
        transport = KillableTransport()
        keeper = build_switch_keeper(
            cfg,
            env={cfg.switch.token_env: key},
            transport=transport,
            presence_source=presence_source or AlwaysHere(),
            timings=timings or fast_timings(),
            known_hosts=hosts,
            weather=False,
        )
        brain_id, brain_key = brains[host]
        brain = StandinBrain(
            f"hermit-{host}",
            base_url,
            brain_id,
            brain_key,
            rooms,
            switch.roles,
            den=DEN,
            ledger=LEDGER,
            honest=honest,
        )
        members[host] = Member(host, keeper, brain, transport)
    return StandinGroup(switch, base_url, members, rooms, humans=people)


async def wait_for(predicate: Any, timeout_s: float = 10.0, every_s: float = 0.02) -> bool:
    """Poll ``predicate`` (sync or async) until true. False on timeout."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return True
        await asyncio.sleep(every_s)
    return False

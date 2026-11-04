"""Assembles a keeper on the real Switch path. Owner: Afreen.

``cli._build_runtime`` calls this for ``lease_strategy = "agent_instructed"``;
the integration tests call **the same function** with an injected httpx
transport and short timings, so what is tested is the production wiring, not
a lookalike::

    SwitchRoomClient ─┬─ LedgerBrainDirector ─┐
      (one poller)    ├─ AgentInstructedLease ┼─ KeeperRuntime
                      └─ gameplay (favors, ┘
                         context, bedtime, journal)

One ``httpx.AsyncClient`` is shared by everything, and one room client owns the
only poll of this agent's drain-once event queue.

There is no fallback. If something required is missing this raises
:class:`SwitchConfigError` with what to fix; it never quietly builds the fake.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .brain.ledger_director import LedgerBrainDirector
from .clock import Clock, RealClock
from .config import HostConfig
from .events import EventBus
from .gameplay import Gameplay, build_gameplay
from .lease.agent_instructed import ACK_TIMEOUT_S, SETTLE_S, AgentInstructedLease
from .presence import for_this_platform
from .presence.base import PresenceSource
from .presence.composite import CompositePresence
from .room.switch_client import MAX_RETRY_S, POLL_TIMEOUT_S, RETRY_S, SwitchRoomClient
from .runtime import GROUP_REFRESH_S, HEARTBEAT_S, TICK_S, KeeperRuntime


class SwitchConfigError(ValueError):
    """The config or environment cannot run the real Switch path."""


@dataclass
class Timings:
    """Every interval on the real path. Production uses the defaults; tests
    shrink them so a lid slam takes a second, not half a minute."""

    tick_s: float = TICK_S
    heartbeat_s: float = HEARTBEAT_S
    group_refresh_s: float = GROUP_REFRESH_S
    ack_timeout_s: float = ACK_TIMEOUT_S
    settle_s: float = SETTLE_S
    poll_timeout_s: float = POLL_TIMEOUT_S
    retry_s: float = RETRY_S
    max_retry_s: float = MAX_RETRY_S
    #: Kept under presence.sleep_gap_s so a long wait is not read as a suspend.
    favor_wait_s: float = 60.0
    favor_poll_s: float = 0.5
    #: Extra KeeperStateMachine keyword arguments (claim jitter, backoff).
    machine: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwitchKeeper:
    """A built keeper and the resources it owns. Call :meth:`aclose` when done."""

    runtime: KeeperRuntime
    http: httpx.AsyncClient
    room: SwitchRoomClient
    brain: LedgerBrainDirector
    lease: AgentInstructedLease
    gameplay: Gameplay

    async def aclose(self) -> None:
        await self.runtime.stop()
        await self.lease.aclose()
        await self.room.aclose()
        await self.http.aclose()


def check_switch_config(cfg: HostConfig, env: Mapping[str, str] | None = None) -> str:
    """Everything the real path needs, or a SwitchConfigError naming what is not there.

    Returns the agent api_key (from the environment). Never logs it.
    """
    switch = cfg.switch
    problems: list[str] = []
    token = switch.token(env)
    if token is None:
        problems.append(
            f"environment variable {switch.token_env} is not set — export your keeper "
            "agent's api_key there (never put it in the config file)"
        )
    if not switch.agent_id:
        problems.append(
            "switch.agent_id is missing — set it to your keeper agent's uuid "
            "(printed by switch/scripts/bootstrap_rooms.py)"
        )
    for name in (switch.den_room, switch.ledger_room):
        if not switch.rooms.get(name):
            problems.append(
                f'switch.rooms has no uuid for "{name}" — add it under [switch.rooms]; '
                "Switch only accepts room uuids"
            )
    if problems:
        raise SwitchConfigError(
            "cannot run lease_strategy = 'agent_instructed':\n  - " + "\n  - ".join(problems)
        )
    assert token is not None
    return token


def build_switch_keeper(
    cfg: HostConfig,
    *,
    env: Mapping[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
    presence_source: PresenceSource | None = None,
    timings: Timings | None = None,
    known_hosts: list[str] | None = None,
    weather: bool = True,
    persist: bool = False,
    state_dir: Path | None = None,
) -> SwitchKeeper:
    """Build the real keeper for ``cfg``. Raises :class:`SwitchConfigError`.

    ``persist=True`` (what ``hermit-keeper run`` passes) keeps the favor
    snapshot and the journal in ``state_dir`` (default ``~/.hermit``).
    """
    if cfg.switch.lease_strategy != "agent_instructed":
        raise SwitchConfigError(
            f"build_switch_keeper needs lease_strategy = 'agent_instructed', "
            f"got '{cfg.switch.lease_strategy}'"
        )
    token = check_switch_config(cfg, env)
    agent_id = cfg.switch.agent_id
    assert agent_id is not None  # check_switch_config guarantees it
    t = timings or Timings()
    clock = clock or RealClock()
    switch = cfg.switch

    http = httpx.AsyncClient(transport=transport) if transport else httpx.AsyncClient()
    room = SwitchRoomClient(
        switch.server_url,
        agent_id,
        token,
        rooms=switch.rooms,
        client=http,
        agent_name=f"keeper-{cfg.host_id}",
        poll_timeout_s=t.poll_timeout_s,
        retry_s=t.retry_s,
        max_retry_s=t.max_retry_s,
        now=clock.now,
    )
    brain = LedgerBrainDirector(
        room,
        cfg.brain_agent,
        cfg.host_id,
        ledger_room=switch.ledger_room,
        brain_ids={switch.brain_agent_id} if switch.brain_agent_id else None,
    )
    lease = AgentInstructedLease(
        brain,
        room,
        cfg.host_id,
        ledger_room=switch.ledger_room,
        den_room=switch.den_room,
        clock=clock,
        ack_timeout_s=t.ack_timeout_s,
        heartbeat_s=t.heartbeat_s,
        lease_expiry_s=switch.lease_expiry_s,
        settle_s=t.settle_s,
    )
    presence = CompositePresence(
        presence_source or for_this_platform(),
        clock,
        idle_threshold_s=cfg.presence.idle_threshold_s,
        arrive_debounce_s=cfg.presence.arrive_debounce_s,
        sleep_gap_s=cfg.presence.sleep_gap_s,
    )
    bus = EventBus()
    gameplay = build_gameplay(
        cfg,
        room,
        brain,
        clock,
        bus,
        state_dir=state_dir,
        persist=persist,
        weather=weather,
        poll_s=t.favor_poll_s,
        favor_wait_s=t.favor_wait_s,
    )
    runtime = KeeperRuntime(
        cfg,
        lease,
        room,
        brain,
        presence,
        clock=clock,
        bus=bus,
        **gameplay.runtime_kwargs(),
        companions=gameplay.companions(),
        known_hosts=known_hosts or [cfg.host_id],
        tick_s=t.tick_s,
        heartbeat_s=t.heartbeat_s,
        group_refresh_s=t.group_refresh_s,
        machine_options=dict(t.machine),
    )
    return SwitchKeeper(
        runtime=runtime, http=http, room=room, brain=brain, lease=lease, gameplay=gameplay
    )

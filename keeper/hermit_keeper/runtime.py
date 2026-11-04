"""Wires one host's keeper together and runs its tick loop. Owner: Afreen.

Everything above this file takes its dependencies through constructors; this is
where the real ones get chosen and assembled. ``cli.py`` builds a runtime, the
API serves it, and the simulation builds the same thing with fakes.

Keeping the loop here (rather than inside the state machine) means the machine
stays a pure function of its inputs and the tests never have to start a task.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog

from .brain.base import BrainDirector
from .clock import Clock, RealClock
from .config import HostConfig
from .events import Event, EventBus, EventType
from .group import GroupView, mood_for
from .handoff import Handoff
from .lease.base import SoulLease
from .ledger import decode, encode
from .presence.composite import CompositePresence, Override
from .room.base import RoomClient
from .statemachine import SPEAKING_STATES, KeeperStateMachine

log = structlog.get_logger(__name__)

#: How often the keeper re-evaluates. Must stay well under ``sleep_gap_s`` or a
#: slow tick would be mistaken for the laptop having been asleep.
TICK_S = 5.0

#: How often this keeper tells the group it is still alive. Must stay well
#: under `group.STALE_AFTER_S` or healthy laptops flicker to `offline`.
HEARTBEAT_S = 10.0

#: How often we re-read the ledger to learn what the other laptops are doing.
GROUP_REFRESH_S = 5.0


class KeeperRuntime:
    """One host's keeper: presence, state machine, handoff, event stream."""

    def __init__(
        self,
        config: HostConfig,
        lease: SoulLease,
        room: RoomClient,
        brain: BrainDirector,
        presence: CompositePresence,
        clock: Clock | None = None,
        bus: EventBus | None = None,
        *,
        is_bedtime: Any = None,
        favors: Any = None,
        context: Any = None,
        known_hosts: list[str] | None = None,
    ) -> None:
        self.config = config
        self.clock: Clock = clock or RealClock()
        self.bus = bus or EventBus()
        self.presence = presence
        self.lease = lease

        self.handoff = Handoff(
            config.host_id,
            room,
            brain,
            self.clock,
            self.bus,
            favors=favors,
            context=context,
            den_room=config.switch.den_room,
            ledger_room=config.switch.ledger_room,
        )
        self.machine = KeeperStateMachine(
            host=config.host_id,
            agent=f"hermit-{config.host_id}",
            lease=lease,
            presence=presence,
            clock=self.clock,
            bus=self.bus,
            is_bedtime=is_bedtime,
            min_dwell_s=config.presence.min_dwell_s,
            on_claimed=self.handoff.on_claimed,
            on_departing=self.handoff.on_departing,
        )
        self._task: asyncio.Task[None] | None = None
        self._last_line: str | None = None
        self._room = room
        self._ledger_room = config.switch.ledger_room
        #: Everyone's last known state, folded from the shared ledger.
        self.group = GroupView(hosts=known_hosts or [config.host_id])
        self._last_heartbeat = 0.0
        self._last_group_read = 0.0
        self._ledger_cursor: datetime | None = None

    # -- the loop ------------------------------------------------------------

    async def run(self) -> None:
        """Tick until cancelled."""
        log.info(
            "keeper started",
            host=self.config.host_id,
            brain=self.config.brain_provider,
            lease=self.config.switch.lease_strategy,
        )
        try:
            while True:
                try:
                    await self.machine.tick()
                except Exception:
                    log.exception("tick failed", host=self.config.host_id)
                await self.clock.sleep(TICK_S)
        except asyncio.CancelledError:
            if self.machine.state in SPEAKING_STATES:
                # Be a good citizen on Ctrl-C: let the soul go so the group is
                # not waiting on a lease expiry that will not come.
                await self.lease.release(self.machine.agent)
                log.info("released the soul on shutdown", host=self.config.host_id)
            raise

    def start(self) -> asyncio.Task[None]:
        self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # -- telling the group we are here ---------------------------------------

    async def beat(self) -> None:
        """Post a heartbeat so the other laptops can tell silence from absence.

        Cheap and frequent: one short ledger line. Without it a laptop that
        crashed and one that is simply quiet look identical, and the dashboard
        would have to guess.
        """
        now = self.clock.now().timestamp()
        if now - self._last_heartbeat < HEARTBEAT_S:
            return
        self._last_heartbeat = now
        event = Event(
            type=EventType.HOST_HEARTBEAT,
            host=self.config.host_id,
            ts=self.clock.now(),
            data={"state": str(self.machine.state), "present": self.presence.present},
        )
        self.group.apply(event)
        try:
            await self._room.post(self._ledger_room, encode(event))
        except Exception:
            log.debug("heartbeat not delivered", host=self.config.host_id)

    async def refresh_group(self) -> None:
        """Re-read the ledger to learn what the other laptops are doing."""
        now = self.clock.now().timestamp()
        if now - self._last_group_read < GROUP_REFRESH_S:
            return
        self._last_group_read = now
        try:
            messages = await self._room.history(
                self._ledger_room, since=self._ledger_cursor, limit=300
            )
        except Exception:
            log.debug("could not read the ledger", host=self.config.host_id)
            return
        for message in messages:
            event = decode(message.text)
            if event is not None:
                self.group.apply(event)
            self._ledger_cursor = message.ts

    # -- what the critter and the CLI read -----------------------------------

    async def status(self) -> dict[str, Any]:
        """Matches ``Status`` in shared/schemas/keeper-api.openapi.yaml."""
        holder = await self.lease.holder()
        host = self.config.host_id
        holder_host = holder.removeprefix("hermit-") if holder else None
        return {
            "host": host,
            "state": str(self.machine.state),
            "present": self.presence.present,
            "soul_holder": holder_host,
            "since": self._since(),
            "mood": mood_for(str(self.machine.state), self.presence.present, holder_host, host),
            "favor_pending": None,
            "last_line": self._last_line,
        }

    async def group_status(self) -> dict[str, Any]:
        """Every laptop in the group — what `/v1/group` serves.

        The authoritative holder comes from Switch, not from the ledger fold:
        the ledger can lag a few seconds and the holder is the one field that
        must never be wrong.
        """
        await self.refresh_group()
        holder = await self.lease.holder()
        if holder is not None:
            self.group.soul_holder = holder.removeprefix("hermit-")
        return self.group.snapshot(self.clock.now(), self_host=self.config.host_id)

    def _since(self) -> str | None:
        if not self.machine.holding:
            return None
        started = self.clock.now().timestamp() - self.machine.dwell_s
        return datetime.fromtimestamp(started, tz=self.clock.now().tzinfo).isoformat()

    def set_override(self, mode: str) -> None:
        self.presence.set_override(Override(mode))

    def request_depart(self) -> None:
        """The critter's "I'm busy" button."""
        self.machine.manual_depart = True

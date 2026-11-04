"""Wires one host's keeper together and runs its tick loop. Owner: Afreen.

Everything above this file takes its dependencies through constructors; this is
where the real ones get chosen and assembled. ``cli.py`` builds a runtime, the
API serves it, and the simulation builds the same thing with fakes.

Keeping the loop here (rather than inside the state machine) means the machine
stays a pure function of its inputs and the tests never have to start a task.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Coroutine, Sequence
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
from .overlap import HostSchedule
from .presence.composite import CompositePresence, Override
from .room.base import RoomClient
from .statemachine import SPEAKING_STATES, KeeperStateMachine
from .stretch import StretchRunner

log = structlog.get_logger(__name__)

#: How often the keeper re-evaluates. Must stay well under ``sleep_gap_s`` or a
#: slow tick would be mistaken for the laptop having been asleep.
TICK_S = 5.0

#: How often this keeper tells the group it is still alive. Must stay well
#: under `group.STALE_AFTER_S` or healthy laptops flicker to `offline`.
HEARTBEAT_S = 10.0

#: How often we re-read the ledger to learn what the other laptops are doing.
GROUP_REFRESH_S = 5.0

#: How long Ctrl-C waits for the brain to let the soul go before giving up
#: and leaving it to Switch's lease expiry.
SHUTDOWN_RELEASE_S = 10.0


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
        tick_s: float = TICK_S,
        heartbeat_s: float = HEARTBEAT_S,
        group_refresh_s: float = GROUP_REFRESH_S,
        machine_options: dict[str, Any] | None = None,
        companions: Sequence[Callable[[], Coroutine[Any, Any, None]]] = (),
    ) -> None:
        self.config = config
        #: Background jobs that live exactly as long as the tick loop, like the
        #: heartbeat: gameplay's ledger sync and the local journal.
        self._companions = list(companions)
        self._tick_s = tick_s
        self._heartbeat_s = heartbeat_s
        self._group_refresh_s = group_refresh_s
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
            brain_provider=config.brain_provider,
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
            **(machine_options or {}),
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
        #: Stretch S1/S2. Does nothing unless features.overlap / features.nudge.
        self.stretch = StretchRunner(
            config.host_id,
            room,
            brain,
            self.clock,
            self.bus,
            overlap=config.features.overlap,
            nudge=config.features.nudge,
            ledger_room=config.switch.ledger_room,
            schedule=HostSchedule(config.timezone, config.bedtime.start, config.bedtime.end),
            known_hosts=known_hosts,
        )

    # -- the loop ------------------------------------------------------------

    async def run(self) -> None:
        """Tick until cancelled."""
        log.info(
            "keeper started",
            host=self.config.host_id,
            brain=self.config.brain_provider,
            lease=self.config.switch.lease_strategy,
        )
        # The heartbeat runs on its own task: a tick can legitimately block for
        # a long time (waiting for the brain's ACK, or for a favor before
        # leaving), and the holder going quiet for that long would look like a
        # lid slam to every other laptop.
        heart = asyncio.create_task(self._heartbeat_loop())
        helpers = [asyncio.create_task(job()) for job in self._companions]
        try:
            while True:
                try:
                    await self.machine.tick()
                    # Hear how the group is. Cheap, and must keep running even
                    # while this laptop is doing nothing interesting.
                    await self.refresh_group()
                    await self.stretch.tick(
                        holding=self.machine.holding, present=self.presence.present
                    )
                except Exception:
                    log.exception("tick failed", host=self.config.host_id)
                await self.clock.sleep(self._tick_s)
        except asyncio.CancelledError:
            if self.machine.state in SPEAKING_STATES:
                # Be a good citizen on Ctrl-C: let the soul go so the group is
                # not waiting on a lease expiry that will not come. Bounded,
                # and never fatal: if Switch is unreachable, expiry does it.
                try:
                    async with asyncio.timeout(SHUTDOWN_RELEASE_S):
                        await self.lease.release(self.machine.agent)
                    log.info("released the soul on shutdown", host=self.config.host_id)
                except Exception:
                    log.warning("could not release the soul on shutdown", host=self.config.host_id)
            raise
        finally:
            for task in (heart, *helpers):
                task.cancel()
            for task in (heart, *helpers):
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await self.beat(force=True)
            except Exception:
                log.exception("heartbeat failed", host=self.config.host_id)
            await self.clock.sleep(self._heartbeat_s)

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

    async def beat(self, force: bool = False) -> None:
        """Post a heartbeat so the other laptops can tell silence from absence.

        Cheap and frequent: one short ledger line. Without it a laptop that
        crashed and one that is simply quiet look identical, and the dashboard
        would have to guess. A ledger-backed lease adds which claim (if any)
        this keeper holds, so a keeper that starts later learns the holder.
        """
        now = self.clock.now().timestamp()
        if not force and now - self._last_heartbeat < self._heartbeat_s:
            return
        self._last_heartbeat = now
        data: dict[str, Any] = {"state": str(self.machine.state), "present": self.presence.present}
        extra = getattr(self.lease, "heartbeat_data", None)
        if callable(extra):
            data.update(extra())
        event = Event(
            type=EventType.HOST_HEARTBEAT,
            host=self.config.host_id,
            ts=self.clock.now(),
            data=data,
        )
        self.group.apply(event)
        try:
            await self._room.post(self._ledger_room, encode(event))
        except Exception:
            log.debug("heartbeat not delivered", host=self.config.host_id)

    async def refresh_group(self) -> None:
        """Re-read the ledger to learn what the other laptops are doing."""
        now = self.clock.now().timestamp()
        if now - self._last_group_read < self._group_refresh_s:
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

    def switch_state(self) -> str:
        """``online`` / ``offline`` for a real Switch lease, ``fake`` otherwise."""
        state = getattr(self.lease, "switch_state", None)
        return state if isinstance(state, str) else "fake"

    async def status(self) -> dict[str, Any]:
        """Matches ``Status`` in shared/schemas/keeper-api.openapi.yaml.

        While Switch is unreachable nobody's claim can be verified, so the
        holder is reported unknown (null) and the mood ``offline`` — never a
        stale ``visiting``.
        """
        holder = await self.lease.holder()
        host = self.config.host_id
        switch = self.switch_state()
        holder_host = holder.removeprefix("hermit-") if holder else None
        mood = mood_for(
            str(self.machine.state),
            self.presence.present,
            holder_host,
            host,
            self.machine.dwell_s if self.machine.holding else None,
        )
        if switch == "offline":
            holder_host, mood = None, "offline"
        return {
            "host": host,
            "state": str(self.machine.state),
            "present": self.presence.present,
            "soul_holder": holder_host,
            "since": self._since(),
            "mood": mood,
            "favor_pending": None,
            "last_line": self._last_line,
            "switch": switch,
        }

    async def group_status(self) -> dict[str, Any]:
        """Every laptop in the group — what `/v1/group` serves.

        The holder comes from the lease, not from the group view's own fold:
        the lease is the one component that resolves conflicting claims and
        stale holders, and the holder is the one field that must never be
        wrong. While Switch is unreachable it is reported unknown.
        """
        await self.refresh_group()
        holder = await self.lease.holder()
        switch = self.switch_state()
        self.group.soul_holder = holder.removeprefix("hermit-") if holder else None
        snapshot = self.group.snapshot(self.clock.now(), self_host=self.config.host_id)
        snapshot["switch"] = switch
        if switch == "offline":
            snapshot["soul_holder"] = None
            for view in snapshot["hosts"]:
                view["holding"] = False
                if view["mood"] in ("arriving", "visiting"):
                    view["mood"] = "offline"
        return snapshot

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

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
from .events import EventBus
from .handoff import Handoff
from .lease.base import SoulLease
from .presence.composite import CompositePresence, Override
from .room.base import RoomClient
from .statemachine import SPEAKING_STATES, KeeperStateMachine, State

log = structlog.get_logger(__name__)

#: How often the keeper re-evaluates. Must stay well under ``sleep_gap_s`` or a
#: slow tick would be mistaken for the laptop having been asleep.
TICK_S = 5.0

#: state -> mascot. These are exactly the four artwork states in
#: `map/public/pocket-hermit/`, so the critter can render `mood` directly
#: without a second lookup table that could drift from the art.
#:
#:   arriving  - peeking out of the shell, holding a letter
#:   visiting  - out of the shell, happy: Hermit is here
#:   away      - tucked in, walking off: with someone else, or nobody
#:   sleeping  - eyes shut: past this host's bedtime
_MOOD = {
    State.ASLEEP: "away",
    State.AWAKE_WAITING: "away",
    State.CLAIMING: "arriving",
    State.HOLDING: "visiting",
    State.DEPARTING: "away",
    State.BEDTIME_LOCK: "sleeping",
}


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

    # -- what the critter and the CLI read -----------------------------------

    async def status(self) -> dict[str, Any]:
        """Matches ``Status`` in shared/schemas/keeper-api.openapi.yaml."""
        holder = await self.lease.holder()
        return {
            "host": self.config.host_id,
            "state": str(self.machine.state),
            "present": self.presence.present,
            "soul_holder": holder.removeprefix("hermit-") if holder else None,
            "since": self._since(),
            "mood": _MOOD[self.machine.state],
            "favor_pending": None,
            "last_line": self._last_line,
        }

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

"""Turns raw idle time into "is a human here?". Owner: Afreen. Phase 3.1.

**Laptop awake is not the same as person awake.** A machine left open all night
reports zero idle time from the OS's point of view but nobody is there. Input
idle time is what makes presence mean a person, which is why Hermit is worth
hosting at all.

Three things sit on top of the raw idle seconds:

* **Sleep-gap detection.** The keeper ticks every few seconds. If wall-clock
  jumps further than ``sleep_gap_s`` between ticks, the machine was suspended —
  the lid was closed. Idle time alone cannot see this, because on wake the OS
  often reports a tiny idle value and we would think the host is right there.
* **Debounce.** Presence must hold for ``arrive_debounce_s`` before it counts
  for claiming the soul. Someone nudging a trackpad on the way past should not
  drag Hermit across the group.
* **Override.** ``awake`` / ``asleep`` / ``auto``, set from the local API. The
  sim, the tests and the demo all drive presence through this.
"""

from __future__ import annotations

from enum import StrEnum

from ..clock import Clock
from .base import PresenceSource


class Override(StrEnum):
    AUTO = "auto"
    AWAKE = "awake"
    ASLEEP = "asleep"


class PresenceReason(StrEnum):
    INPUT = "input"
    IDLE = "idle"
    SLEEP_GAP = "sleep_gap"
    OVERRIDE = "override"


class CompositePresence:
    """Args:
    source: the platform idle-time source (or a scripted fake).
    clock: injected, so tests can jump time to fake a suspend.
    idle_threshold_s: no input for this long means the host is gone.
    arrive_debounce_s: how long presence must hold before it counts for
        claiming.
    sleep_gap_s: a wall-clock jump larger than this means the machine slept.
    """

    def __init__(
        self,
        source: PresenceSource,
        clock: Clock,
        idle_threshold_s: float = 300.0,
        arrive_debounce_s: float = 60.0,
        sleep_gap_s: float = 90.0,
    ) -> None:
        self._source = source
        self._clock = clock
        self._idle_threshold_s = idle_threshold_s
        self._arrive_debounce_s = arrive_debounce_s
        self._sleep_gap_s = sleep_gap_s

        self.override: Override = Override.AUTO
        self._last_tick = clock.now()
        self._present = False
        self._present_since: float | None = None
        self._reason = PresenceReason.IDLE
        #: Set for exactly one tick after a suspend is detected.
        self.slept = False

    # -- reads ---------------------------------------------------------------

    @property
    def present(self) -> bool:
        """Raw presence, before debounce."""
        return self._present

    @property
    def reason(self) -> PresenceReason:
        return self._reason

    def settled(self) -> bool:
        """Presence has held long enough to justify claiming the soul.

        This is the one the state machine asks about. ``present`` says a human
        is there; ``settled`` says they have been there long enough to mean it.
        """
        if not self._present or self._present_since is None:
            return False
        held = (self._clock.now().timestamp()) - self._present_since
        return held >= self._arrive_debounce_s

    # -- the tick ------------------------------------------------------------

    async def tick(self) -> bool:
        """Re-evaluate presence. Returns True if it changed this tick.

        Call every few seconds. The gap between calls is what detects a suspend,
        so a keeper that stops ticking is itself the signal that the host is
        gone — which is the same thing Switch's lease expiry notices.
        """
        now = self._clock.now()
        gap = (now - self._last_tick).total_seconds()
        self._last_tick = now

        # A suspend beats everything, including an 'awake' override: the machine
        # demonstrably was not running.
        self.slept = gap > self._sleep_gap_s
        if self.slept:
            return self._set(False, PresenceReason.SLEEP_GAP, now.timestamp())

        if self.override is Override.AWAKE:
            return self._set(True, PresenceReason.OVERRIDE, now.timestamp())
        if self.override is Override.ASLEEP:
            return self._set(False, PresenceReason.OVERRIDE, now.timestamp())

        idle = await self._source.idle_seconds()
        if idle < self._idle_threshold_s:
            return self._set(True, PresenceReason.INPUT, now.timestamp())
        return self._set(False, PresenceReason.IDLE, now.timestamp())

    def set_override(self, mode: Override | str) -> None:
        self.override = Override(mode)

    # -- internals -----------------------------------------------------------

    def _set(self, present: bool, reason: PresenceReason, at: float) -> bool:
        changed = present != self._present
        if changed:
            self._present = present
            self._present_since = at if present else None
        self._reason = reason
        return changed

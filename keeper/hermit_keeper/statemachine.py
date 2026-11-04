"""The keeper state machine. Owner: A. Phase 3.2.

    IDLE_AWAY -> WAITING -> CLAIMING -> HOLDING -> DEPARTING -> IDLE_AWAY
                                   \-> (rejected) -> WAITING

Invariant, enforced here and proven in tests: at most one host is in HOLDING
across the whole group at any moment.
"""

from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    IDLE_AWAY = "IDLE_AWAY"
    WAITING = "WAITING"
    CLAIMING = "CLAIMING"
    HOLDING = "HOLDING"
    DEPARTING = "DEPARTING"
    ASLEEP = "ASLEEP"

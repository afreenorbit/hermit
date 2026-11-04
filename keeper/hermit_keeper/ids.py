"""ULID helpers. Every id that crosses a boundary is ``<prefix>_<ULID>``."""

from __future__ import annotations

from typing import Literal

from ulid import ULID

Prefix = Literal["evt", "fav", "pc", "stop", "ovl", "cue"]


def new_id(prefix: Prefix) -> str:
    """Return a fresh prefixed ULID, e.g. ``evt_01JC...``."""
    return f"{prefix}_{ULID()}"


def seed_from_id(value: str) -> int:
    """Deterministic 31-bit render seed derived from any prefixed id.

    Used for shell pieces so the same piece always draws the same way, on every
    machine, without storing the rendering itself.
    """
    body = value.split("_", 1)[-1]
    h = 2166136261
    for ch in body:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h & 0x7FFFFFFF

"""Encode and decode ``hermit-ledger`` lines.

The ledger room is the single source of truth for the journey, so the format is
deliberately boring: one prefix, one line, one JSON object.
"""

from __future__ import annotations

import json

from .events import Event

PREFIX = "HERMIT/1 "


def encode(event: Event) -> str:
    """Event -> one ledger line."""
    payload = event.model_dump(mode="json")
    return PREFIX + json.dumps(payload, separators=(",", ":"), sort_keys=False)


def decode(line: str) -> Event | None:
    """Ledger line -> Event. Returns None for anything else (humans chat here too)."""
    if not line.startswith(PREFIX):
        return None
    try:
        return Event.model_validate_json(line[len(PREFIX) :])
    except ValueError:
        return None

"""The ledger format is the journey's source of truth, so it gets a test on day one."""

from __future__ import annotations

from datetime import UTC, datetime

from hermit_keeper import ledger
from hermit_keeper.events import Event, EventType


def test_encode_decode_roundtrip() -> None:
    event = Event(
        type=EventType.SOUL_CLAIMED,
        host="afreen",
        ts=datetime(2026, 11, 5, 10, 12, 3, tzinfo=UTC),
        data={"holder": "afreen", "previous_holder": "abhishek", "latency_ms": 8400},
    )
    line = ledger.encode(event)
    assert line.startswith("HERMIT/1 {")
    assert "\n" not in line

    decoded = ledger.decode(line)
    assert decoded is not None
    assert decoded.id == event.id
    assert decoded.type is EventType.SOUL_CLAIMED
    assert decoded.data["latency_ms"] == 8400


def test_decode_ignores_human_chatter() -> None:
    assert ledger.decode("hey is hermit stuck on your laptop?") is None
    assert ledger.decode("HERMIT/1 not json") is None

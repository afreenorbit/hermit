"""Plan §4.8: a fixed ledger exports to exactly the committed journey.

The ledger below covers every departure the map draws differently: graceful,
abrupt (a lid slam, recovered from the ledger alone because no SOUL_RELEASED was
ever written) and bedtime. If the export changes on purpose, regenerate with::

    UPDATE_GOLDEN=1 pytest tests/contract/test_export_golden.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hermit_keeper.events import Event, EventType

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
from export_journey import build_journey, validate  # noqa: E402

STOP_A = "stop_01JC00000000000000000000A1"
STOP_B = "stop_01JC00000000000000000000B1"
STOP_C = "stop_01JC00000000000000000000C1"

GOLDEN = Path(__file__).parent / "golden" / "journey.golden.json"

HOSTS = [
    {
        "host_id": h,
        "display_name": h.title(),
        "city": city,
        "lat": lat,
        "lon": lon,
        "brain_provider": p,
    }
    for h, city, lat, lon, p in (
        ("afreen", "Indiranagar", 12.97, 77.64, "claude-code"),
        ("abhishek", "Kengeri", 12.91, 77.48, "opencode"),
        ("akshay", "Yelahanka", 13.10, 77.59, "codex"),
    )
]

FAVOR = {
    "v": 1,
    "id": "fav_01JC0000000000000000000001",
    "left_by": "afreen",
    "text": "the last song stuck in your head",
    "kind": "share",
    "created_at": "2026-11-05T03:40:00Z",
    "assignee": None,
    "status": "open",
    "switch_document_id": None,
    "completed_at": None,
}

PIECE = {
    "v": 1,
    "id": "pc_01JC0000000000000000000001",
    "host": "abhishek",
    "city": "Kengeri",
    "brain_provider": "opencode",
    "temp_c": 24.0,
    "weather_code": 2,
    "dwell_s": 1080,
    "departure": "graceful",
    "favor_id": FAVOR["id"],
    "created_at": "2026-11-05T04:00:00Z",
    "seed": 123456,
}


def _e(n: int, kind: EventType, host: str, hh: int, mm: int, **data: Any) -> Event:
    return Event(
        id=f"evt_01JC{n:022d}",
        type=kind,
        host=host,
        ts=datetime(2026, 11, 5, hh, mm, tzinfo=UTC),
        data=data,
    )


def ledger() -> list[Event]:
    weather = {"temp_c": 24.0, "code": 2}
    return [
        _e(1, EventType.ARRIVAL_ANNOUNCED, "afreen", 3, 0, stop_id=STOP_A, weather=weather),
        _e(2, EventType.FAVOR_LEFT, "afreen", 3, 40, favor=FAVOR),
        _e(3, EventType.SOUL_RELEASED, "afreen", 3, 41, stop_id=STOP_A, departure="graceful"),
        _e(
            4,
            EventType.ARRIVAL_ANNOUNCED,
            "abhishek",
            3,
            42,
            stop_id=STOP_B,
            weather=weather,
            favor_id=FAVOR["id"],
        ),
        _e(5, EventType.FAVOR_ASSIGNED, "abhishek", 3, 42, favor_id=FAVOR["id"]),
        _e(6, EventType.FAVOR_COMPLETED, "abhishek", 4, 0, favor_id=FAVOR["id"]),
        _e(7, EventType.SHELL_PIECE_ADDED, "abhishek", 4, 0, piece=PIECE),
        # abhishek's lid comes down: no SOUL_RELEASED, ever.
        _e(8, EventType.ARRIVAL_ANNOUNCED, "akshay", 5, 10, stop_id=STOP_C, weather=None),
        _e(9, EventType.SOUL_RELEASED, "akshay", 20, 0, stop_id=STOP_C, departure="bedtime"),
    ]


def export() -> dict[str, Any]:
    return build_journey(ledger(), HOSTS, generated_at="2026-11-05T20:30:00Z")


def test_the_fixed_ledger_exports_to_the_golden_journey() -> None:
    journey = export()
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(journey, indent=2) + "\n", encoding="utf-8")
    assert journey == json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_the_golden_journey_is_valid_against_the_schema() -> None:
    assert validate(export()) == []


def test_the_lid_slam_is_recovered_from_the_ledger_alone() -> None:
    stops = {s["host"]: s for s in export()["stops"]}
    assert stops["afreen"]["departure"] == "graceful"
    assert stops["abhishek"]["departure"] == "abrupt"
    assert stops["abhishek"]["left_at"] == "2026-11-05T05:10:00Z"
    assert stops["akshay"]["departure"] == "bedtime"
    assert stops["abhishek"]["favor_received"]["left_by"] == "afreen"

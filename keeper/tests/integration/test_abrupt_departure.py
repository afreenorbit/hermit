"""Stretch S3: a lid slam is told, not hidden.

The next host hears "I left in a hurry", the shell gets one cracked piece,
and the export pins that piece to the stop Hermit landed on.
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from hermit_keeper import ledger
from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.events import Event, EventBus, EventType
from hermit_keeper.handoff import Handoff
from hermit_keeper.room.fake import FakeRoomHub

REPO_ROOT = Path(__file__).resolve().parents[3]
LEDGER = "hermit-ledger"
AFREEN_STOP = "stop_" + "0" * 25 + "1"


class Context:
    async def arrival_context(self) -> dict[str, Any]:
        return {"city": "Koramangala", "weather": {"temp_c": 24.0, "code": 3}, "local_hour": 21}


async def _post(
    hub: FakeRoomHub, clock: FakeClock, kind: EventType, host: str, **data: Any
) -> None:
    event = Event(type=kind, host=host, ts=clock.now(), data=data)
    await hub.client(f"keeper-{host}").post(LEDGER, ledger.encode(event))


async def _afreen_vanishes(hub: FakeRoomHub, clock: FakeClock, goodbye: bool = False) -> None:
    await _post(hub, clock, EventType.ARRIVAL_ANNOUNCED, "afreen", stop_id=AFREEN_STOP)
    await clock.advance(600)
    await _post(hub, clock, EventType.HOST_HEARTBEAT, "afreen", present=True, state="HOLDING")
    if goodbye:
        await _post(hub, clock, EventType.SOUL_RELEASED, "afreen", departure="graceful")
    await clock.advance(300)


def _akshay(hub: FakeRoomHub, clock: FakeClock) -> tuple[Handoff, FakeBrain]:
    brain = FakeBrain("hermit-akshay", "codex")
    handoff = Handoff(
        "akshay",
        hub.client("keeper-akshay"),
        brain,
        clock,
        EventBus(),
        context=Context(),
        brain_provider="codex",
    )
    return handoff, brain


def _ledger(hub: FakeRoomHub) -> list[Event]:
    return [e for e in (ledger.decode(m.text) for m in hub.rooms.get(LEDGER, [])) if e]


def _cracked(hub: FakeRoomHub) -> list[Event]:
    return [e for e in _ledger(hub) if e.type is EventType.SHELL_PIECE_ADDED]


async def test_the_next_host_hears_it_and_gets_a_cracked_piece() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    await _afreen_vanishes(hub, clock)
    handoff, brain = _akshay(hub, clock)

    await handoff.on_claimed()

    arrive = next(ctx for cue, ctx in brain.cues if cue == "ARRIVE")
    assert arrive["left_in_a_hurry"] is True
    assert "I left Afreen's in a hurry" in arrive["hurry_line"]
    assert "cracked" in arrive["cracked_piece"]

    [event] = _cracked(hub)
    piece = event.data["piece"]
    assert event.data["cracked_for_stop"] == AFREEN_STOP
    assert piece["departure"] == "abrupt"
    assert (piece["host"], piece["city"], piece["brain_provider"]) == (
        "akshay",
        "Koramangala",
        "codex",
    )
    assert piece["dwell_s"] == 600  # arrival to afreen's last line, not to the lid slam
    _valid_piece(piece)

    # Written after the arrival so the export pins it to akshay's stop.
    kinds = [e.type for e in _ledger(hub)]
    assert kinds.index(EventType.ARRIVAL_ANNOUNCED, 1) < kinds.index(EventType.SHELL_PIECE_ADDED)


async def test_one_slam_one_crack_however_often_hermit_comes_back() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    await _afreen_vanishes(hub, clock)
    handoff, brain = _akshay(hub, clock)

    await handoff.on_claimed()
    await clock.advance(3600)
    await _post(hub, clock, EventType.SOUL_RELEASED, "akshay", departure="graceful")
    await clock.advance(3600)
    await handoff.on_claimed()  # akshay again: afreen's stop is old news now

    assert len(_cracked(hub)) == 1
    second = [ctx for cue, ctx in brain.cues if cue == "ARRIVE"][1]
    assert "left_in_a_hurry" not in second


async def test_a_goodbye_leaves_no_crack() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    await _afreen_vanishes(hub, clock, goodbye=True)
    handoff, brain = _akshay(hub, clock)

    await handoff.on_claimed()

    assert _cracked(hub) == []
    arrive = next(ctx for cue, ctx in brain.cues if cue == "ARRIVE")
    assert arrive["previous_departure"] == "graceful"
    assert "left_in_a_hurry" not in arrive


async def test_the_export_shows_the_abrupt_stop_and_the_crack() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    await _afreen_vanishes(hub, clock)
    handoff, _ = _akshay(hub, clock)
    await handoff.on_claimed()

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from export_journey import build_journey, validate

    journey = build_journey(_ledger(hub), [], (clock.now() + timedelta(seconds=1)).isoformat())
    assert validate(journey) == []
    first, second = journey["stops"]
    assert first["departure"] == "abrupt"
    assert second["shell_piece_id"] == journey["shell"][0]["id"]


def _valid_piece(piece: dict[str, Any]) -> None:
    schema = json.loads(
        (REPO_ROOT / "shared" / "schemas" / "shell-piece.schema.json").read_text(encoding="utf-8")
    )
    errors = list(Draft202012Validator(schema).iter_errors(piece))
    assert not errors, [e.message for e in errors]

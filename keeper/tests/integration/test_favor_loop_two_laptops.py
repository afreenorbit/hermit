"""Plan §4.9 acceptance, on the real keeper's wiring rather than the sim's.

The sim shares one ``FavorBook`` between simulated laptops. Real laptops do not
share memory, so this test gives each keeper its own ``build_gameplay`` and lets
the only connection between them be the room — exactly as on three machines.

    afreen leaves a favor -> Hermit arrives at abhishek -> favor assigned ->
    abhishek does it in the den -> shell piece -> journey.json validates
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.config import HostConfig
from hermit_keeper.events import EventBus, EventType
from hermit_keeper.gameplay import Gameplay, build_gameplay
from hermit_keeper.handoff import Handoff
from hermit_keeper.ledger import decode
from hermit_keeper.room.fake import FakeRoomHub

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
from export_journey import build_journey, validate  # noqa: E402

DEN, LEDGER = "hermit-den", "hermit-ledger"


class _NoWeather:
    async def get(self, *_: Any, **__: Any) -> Any:
        raise OSError("offline in tests")


def _config(host: str, provider: str, window: Path) -> HostConfig:
    return HostConfig.model_validate(
        {
            "host_id": host,
            "display_name": host.title(),
            "city": "Bengaluru",
            "lat": 12.97,
            "lon": 77.59,
            "timezone": "Asia/Kolkata",
            "brain_agent": f"hermit-{host}",
            "brain_provider": provider,
            "window_dir": str(window),
            "switch": {"server_url": "http://127.0.0.1:8000", "lease_strategy": "fake"},
        }
    )


class Laptop:
    def __init__(self, host: str, provider: str, hub: FakeRoomHub, clock: FakeClock, tmp: Path):
        self.host = host
        self.bus = EventBus()
        self.room = hub.client(f"keeper-{host}")
        self.brain = FakeBrain(f"hermit-{host}", provider, den=hub.client(f"hermit-{host}"))
        self.gameplay: Gameplay = build_gameplay(
            _config(host, provider, tmp),
            self.room,
            self.brain,
            clock,
            self.bus,
            state_dir=tmp / host,
            weather_client=_NoWeather(),
        )
        self.handoff = Handoff(
            host,
            self.room,
            self.brain,
            clock,
            self.bus,
            favors=self.gameplay.favors,
            context=self.gameplay.context,
        )
        self.human = hub.client(host)


async def _advance(clock: FakeClock, seconds: float, step: float = 1.0) -> None:
    for _ in range(int(seconds / step)):
        await clock.advance(step)
        for _ in range(5):
            await asyncio.sleep(0)


async def test_a_favor_crosses_laptops_and_grows_the_shell(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 11, 5, 4, 0, tzinfo=UTC))
    hub = FakeRoomHub(clock=clock)
    afreen = Laptop("afreen", "claude-code", hub, clock, tmp_path)
    abhishek = Laptop("abhishek", "opencode", hub, clock, tmp_path)

    # Afreen hosts, then leaves; she answers the favor ask from her phone.
    await afreen.handoff.on_claimed()
    await _advance(clock, 600, step=60)
    departing = asyncio.create_task(afreen.handoff.on_departing("idle"))
    await _advance(clock, 6)
    await afreen.human.post(DEN, "send the group the last song stuck in your head")
    await _advance(clock, 6)
    await _advance(clock, 90, step=5)
    await departing

    # Abhishek's keeper has never seen Afreen's laptop. It learns the favor
    # from the room alone.
    await _advance(clock, 30)
    await abhishek.handoff.on_claimed()
    arrive = [ctx for cue, ctx in abhishek.brain.cues if cue == "ARRIVE"][-1]
    assert arrive["favor"]["left_by"] == "afreen"

    # He does it in the den.
    await _advance(clock, 300, step=30)
    await abhishek.human.post(DEN, "it's Kun Faya Kun, every single time")
    await _advance(clock, 5)

    events = [e for e in (decode(m.text) for m in hub.rooms[LEDGER]) if e]
    types = [e.type for e in events]
    for expected in (
        EventType.ARRIVAL_ANNOUNCED,
        EventType.FAVOR_LEFT,
        EventType.SOUL_RELEASED,
        EventType.FAVOR_ASSIGNED,
        EventType.FAVOR_COMPLETED,
        EventType.SHELL_PIECE_ADDED,
    ):
        assert expected in types, expected

    piece = next(e for e in events if e.type is EventType.SHELL_PIECE_ADDED).data["piece"]
    assert piece["host"] == "abhishek"
    assert piece["brain_provider"] == "opencode"

    # Afreen's keeper hears about the completion too, and will not carry it again.
    await afreen.gameplay.favors.sync()
    assert await afreen.gameplay.favors.carried("akshay") is None

    hosts = [
        {
            "host_id": h,
            "display_name": h.title(),
            "city": "Bengaluru",
            "lat": 12.97,
            "lon": 77.59,
            "brain_provider": p,
        }
        for h, p in (("afreen", "claude-code"), ("abhishek", "opencode"))
    ]
    journey = build_journey(
        sorted(events, key=lambda e: (e.ts, e.id)), hosts, clock.now().isoformat()
    )
    assert validate(journey) == []
    assert journey["stats"]["favors_left"] == 1
    assert journey["stats"]["favors_done"] == 1
    assert len(journey["shell"]) == 1
    assert journey["stops"][1]["favor_received"]["left_by"] == "afreen"
    json.dumps(journey)  # serialisable, as the map will read it

    await afreen.gameplay.stop()
    await abhishek.gameplay.stop()

"""A note follows the current holder through Switch's shared room, not a direct socket."""

from __future__ import annotations

import httpx

from hermit_keeper.api import create_app
from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.config import HostConfig
from hermit_keeper.events import EventType
from hermit_keeper.lease.fake import FakeSoulLease
from hermit_keeper.ledger import decode
from hermit_keeper.presence.composite import CompositePresence
from hermit_keeper.presence.fake import ScriptedPresence
from hermit_keeper.room.fake import FakeRoomHub
from hermit_keeper.runtime import KeeperRuntime


def runtime(host: str, hub: FakeRoomHub, lease: FakeSoulLease, clock: FakeClock) -> KeeperRuntime:
    cfg = HostConfig.model_validate(
        {
            "host_id": host,
            "display_name": host.title(),
            "city": "Bengaluru",
            "lat": 12.97,
            "lon": 77.59,
            "timezone": "Asia/Kolkata",
            "brain_agent": f"hermit-{host}",
            "brain_provider": "other",
            "window_dir": ".",
            "switch": {"server_url": "http://127.0.0.1:8000", "lease_strategy": "fake"},
        }
    )
    return KeeperRuntime(
        cfg,
        lease,
        hub.client(f"keeper-{host}"),
        FakeBrain(f"hermit-{host}"),
        CompositePresence(ScriptedPresence(clock, [(0, True)]), clock),
        clock=clock,
        group_refresh_s=0,
    )


async def test_note_reaches_only_current_holder_and_same_timestamp_notes_are_not_lost() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock)
    lease = FakeSoulLease(clock)
    afreen = runtime("afreen", hub, lease, clock)
    akshay = runtime("akshay", hub, lease, clock)
    await lease.claim("hermit-akshay")

    assert (await afreen.send_note("First hello"))["to"] == "akshay"  # type: ignore[index]
    await akshay.refresh_group()
    assert (await akshay.status())["last_line"] == "afreen: First hello"
    assert await afreen.send_note("Second hello") is not None
    await akshay.refresh_group()
    assert (await akshay.status())["last_line"] == "afreen: Second hello"

    notes = [
        event
        for message in hub.rooms["hermit-ledger"]
        if (event := decode(message.text)) is not None and event.type is EventType.NOTE_SENT
    ]
    assert len(notes) == 2
    assert all(event.data["to"] == "akshay" for event in notes)
    assert (await afreen.status())["last_line"] is None


async def test_local_note_api_refuses_invalid_text_and_missing_holder() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock)
    afreen = runtime("afreen", hub, FakeSoulLease(clock), clock)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(afreen)), base_url="http://127.0.0.1"
    ) as client:
        bad = await client.post("/v1/notes", json={"text": "x"})
        assert bad.status_code == 400
        missing = await client.post("/v1/notes", json={"text": "Are you there?"})
        assert missing.status_code == 409

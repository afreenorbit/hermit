"""S1/S2 wired to fakes: what the real keeper's tick hook actually does."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from hermit_keeper import ledger
from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.events import Event, EventBus, EventType
from hermit_keeper.nudge import NudgeParams
from hermit_keeper.overlap import HostSchedule
from hermit_keeper.room.fake import FakeRoomHub
from hermit_keeper.stretch import StretchRunner

LEDGER = "hermit-ledger"
UTC_NIGHT = HostSchedule("UTC", "01:00", "06:00")
START = datetime(2026, 11, 1, tzinfo=UTC)


def runner(host: str, hub: FakeRoomHub, clock: FakeClock, **flags: Any) -> StretchRunner:
    return StretchRunner(
        host,
        hub.client(f"keeper-{host}"),
        FakeBrain(f"hermit-{host}", "other"),
        clock,
        EventBus(),
        schedule=UTC_NIGHT,
        schedules={"afreen": UTC_NIGHT, "akshay": UTC_NIGHT, "abhishek": UTC_NIGHT},
        known_hosts=["afreen", "abhishek", "akshay"],
        **flags,
    )


def ledger_events(hub: FakeRoomHub, kind: EventType) -> list[Event]:
    events = (ledger.decode(m.text) for m in hub.rooms.get(LEDGER, []))
    return [e for e in events if e is not None and e.type is kind]


async def beat(hub: FakeRoomHub, clock: FakeClock, host: str, present: bool) -> None:
    event = Event(
        type=EventType.HOST_HEARTBEAT, host=host, ts=clock.now(), data={"present": present}
    )
    await hub.client(f"keeper-{host}").post(LEDGER, ledger.encode(event))


async def test_off_by_default_and_does_nothing() -> None:
    clock = FakeClock(START)
    hub = FakeRoomHub(clock=clock)
    quiet = runner("afreen", hub, clock)
    assert not quiet.enabled
    clock_ticks = 0
    while clock_ticks < 400:
        assert await quiet.tick(holding=True, present=True) == []
        await clock.advance(1800)
        clock_ticks += 1
    assert hub.rooms.get(LEDGER, []) == []


async def test_the_holder_suggests_the_hour_it_shares_with_a_friend() -> None:
    clock = FakeClock(START)
    hub = FakeRoomHub(clock=clock)
    afreen = runner("afreen", hub, clock, overlap=True)

    # Two days: afreen around 09-12 UTC, akshay 11-13. One shared hour.
    # Hermit is elsewhere, so afreen's keeper only listens.
    for _ in range(2 * 48):
        hour = clock.now().hour
        await beat(hub, clock, "akshay", 11 <= hour < 13)
        assert await afreen.tick(holding=False, present=9 <= hour < 12) == []
        await clock.advance(1800)

    # Day three, 09:00: afreen has Hermit.
    await clock.advance(9 * 3600)
    [event] = await afreen.tick(holding=True, present=True)
    assert event.type is EventType.OVERLAP_SUGGESTED
    assert event.data["hosts"] == ["afreen", "akshay"]
    assert event.data["window_start"].endswith("T11:00:00Z")
    assert event.data["window_end"].endswith("T12:00:00Z")
    assert event.data["ovl_id"].startswith("ovl_")

    cue, context = afreen._brain.cues[-1]  # type: ignore[attr-defined]
    assert cue == "SUGGEST_OVERLAP"
    assert context["other_host"] == "akshay"
    assert context["window_local"] == "11:00-12:00"

    # Asking again later the same day: nothing new. The ledger remembers.
    await clock.advance(7 * 3600)
    assert await afreen.tick(holding=True, present=True) == []


async def test_a_quiet_friend_gets_one_nudge_and_another_laptop_respects_it() -> None:
    clock = FakeClock(START)
    hub = FakeRoomHub(clock=clock)
    params = NudgeParams(quiet_after_s=72 * 3600, min_gap_s=12 * 3600)
    afreen = runner("afreen", hub, clock, nudge=True, nudge_params=params)
    abhishek = runner("abhishek", hub, clock, nudge=True, nudge_params=params)

    async def arrives(host: str) -> None:
        event = Event(type=EventType.ARRIVAL_ANNOUNCED, host=host, ts=clock.now())
        await hub.client(f"keeper-{host}").post(LEDGER, ledger.encode(event))

    # akshay hosts once at the start, then goes quiet; the others keep hosting.
    await arrives("akshay")
    await clock.advance(50 * 3600)
    await arrives("abhishek")
    await clock.advance(23 * 3600)
    await arrives("afreen")

    [event] = await afreen.tick(holding=True, present=True)
    assert event.type is EventType.NUDGE_SENT
    assert event.data["target_host"] == "akshay"
    assert event.data["days_since_hosted"] == 3.0
    cue, context = afreen._brain.cues[-1]  # type: ignore[attr-defined]
    assert (cue, context["target_host"]) == ("NUDGE_QUIET_FRIEND", "akshay")
    assert len(context["suggestions"]) == 3

    # A day later Hermit is on abhishek's laptop. Same spell: not again.
    await clock.advance(24 * 3600)
    await arrives("abhishek")
    assert await abhishek.tick(holding=True, present=True) == []
    assert await afreen.tick(holding=False, present=True) == []
    assert len(ledger_events(hub, EventType.NUDGE_SENT)) == 1


async def test_only_the_soul_holder_speaks() -> None:
    clock = FakeClock(START)
    hub = FakeRoomHub(clock=clock)
    afreen = runner("afreen", hub, clock, nudge=True)
    await clock.advance(100 * 3600)
    assert await afreen.tick(holding=False, present=True) == []
    assert ledger_events(hub, EventType.NUDGE_SENT) == []

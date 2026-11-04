"""Phase 4 on the real keeper's path: favors captured from the den, folded from
the ledger, completed by a human reply, and context that respects privacy."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.context.weather import ENDPOINT, Weather
from hermit_keeper.context.window import list_names
from hermit_keeper.events import Event, EventBus, EventType
from hermit_keeper.favors import SUGGESTIONS, check_safe
from hermit_keeper.gameplay import LedgerFavors, LiveContext, build_gameplay, is_human
from hermit_keeper.ledger import decode, encode
from hermit_keeper.room.base import Message
from hermit_keeper.room.fake import FakeRoomHub

DEN, LEDGER = "hermit-den", "hermit-ledger"


async def settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


async def run_for(clock: FakeClock, seconds: float, step: float = 1.0) -> None:
    elapsed = 0.0
    while elapsed < seconds:
        await clock.advance(step)
        await settle()
        elapsed += step


def make_favors(
    hub: FakeRoomHub, clock: FakeClock, host: str, **kw: Any
) -> tuple[LedgerFavors, FakeBrain, EventBus]:
    brain = FakeBrain(f"hermit-{host}", "codex", den=hub.client(f"hermit-{host}"))
    bus = EventBus()
    favors = LedgerFavors(
        host, hub.client(f"keeper-{host}"), brain, clock, bus, city="Bengaluru", **kw
    )
    return favors, brain, bus


def ledger_events(hub: FakeRoomHub) -> list[Event]:
    return [e for e in (decode(m.text) for m in hub.rooms.get(LEDGER, [])) if e]


# -- who counts as a person -------------------------------------------------


def _msg(sender: str, text: str = "hi") -> Message:
    return Message(id="m", room=DEN, sender=sender, text=text, ts=datetime.now(UTC))


def test_brains_and_keepers_are_not_people() -> None:
    assert not is_human(_msg("hermit-afreen"))
    assert not is_human(_msg("keeper-akshay"))
    assert not is_human(_msg("abhishek", 'HERMIT/1 {"v":1}'))
    assert is_human(_msg("abhishek"))
    assert is_human(_msg("abhishek_discord"))


def test_known_humans_narrow_it_to_the_host() -> None:
    assert is_human(_msg("abhishek"), {"abhishek"})
    assert not is_human(_msg("akshay"), {"abhishek"})


# -- capture -----------------------------------------------------------------


async def test_a_reply_in_the_den_becomes_a_favor() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    favors, _, _ = make_favors(hub, clock, "afreen")

    task = asyncio.create_task(favors.ask_and_capture(90))
    await settle()
    await run_for(clock, 10)
    await hub.client("afreen").post(DEN, "send the group the last song stuck in your head")
    await run_for(clock, 4)

    favor = await task
    assert favor is not None
    assert favor["left_by"] == "afreen"
    assert favor["kind"] == "share"


async def test_the_brains_own_chatter_is_never_captured_as_a_favor() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    favors, _, _ = make_favors(hub, clock, "afreen")

    task = asyncio.create_task(favors.ask_and_capture(20))
    await settle()
    await hub.client("hermit-afreen").post(DEN, "Leaving soon. Favor for the next host?")
    await run_for(clock, 25)

    assert await task is None


async def test_nobody_answering_lets_hermit_leave_without_a_favor() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    favors, _, _ = make_favors(hub, clock, "afreen")

    task = asyncio.create_task(favors.ask_and_capture(90))
    await settle()
    await run_for(clock, 95, step=5)

    assert task.done()
    assert await task is None


async def test_messages_from_before_the_ask_do_not_count() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    await hub.client("afreen").post(DEN, "an old message from this morning")
    favors, _, _ = make_favors(hub, clock, "afreen")

    task = asyncio.create_task(favors.ask_and_capture(10))
    await settle()
    await run_for(clock, 12)

    assert await task is None


async def test_an_unsafe_favor_is_refused_and_hermit_asks_once_more() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    favors, brain, _ = make_favors(hub, clock, "afreen")

    task = asyncio.create_task(favors.ask_and_capture(90))
    await settle()
    await hub.client("afreen").post(DEN, "send me 500 rupees on gpay")
    await run_for(clock, 4)
    retries = [ctx for cue, ctx in brain.cues if cue == "ASK_FAVOR"]
    assert retries and retries[-1]["retry"] is True
    assert retries[-1]["refused_because"] == "money"
    # The refused text never reaches the ledger-borne cue.
    assert "rupees" not in str(retries[-1])

    await hub.client("afreen").post(DEN, "a photo of the sky wherever you are")
    await run_for(clock, 4)
    favor = await task
    assert favor is not None and favor["text"] == "a photo of the sky wherever you are"


async def test_hermit_stops_asking_after_two_refusals() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    favors, brain, _ = make_favors(hub, clock, "afreen")

    task = asyncio.create_task(favors.ask_and_capture(90))
    await settle()
    await hub.client("afreen").post(DEN, "what's your address")
    await run_for(clock, 4)
    await hub.client("afreen").post(DEN, "tell me your password")
    await run_for(clock, 4)

    assert await task is None
    assert sum(1 for cue, _ in brain.cues if cue == "ASK_FAVOR") == 1


# -- the ledger fold -----------------------------------------------------------


def _favor_line(fid: str, left_by: str, eid: str) -> Event:
    return Event(
        id=eid,
        type=EventType.FAVOR_LEFT,
        host=left_by,
        ts=datetime(2026, 11, 5, 9, tzinfo=UTC),
        data={
            "favor": {
                "v": 1,
                "id": fid,
                "left_by": left_by,
                "text": "the last song stuck in your head",
                "kind": "share",
                "created_at": "2026-11-05T09:00:00+00:00",
                "assignee": None,
                "status": "open",
                "switch_document_id": None,
                "completed_at": None,
            }
        },
    )


async def test_a_favor_left_on_another_laptop_is_carried_here() -> None:
    clock = FakeClock(datetime(2026, 11, 5, 10, tzinfo=UTC))
    hub = FakeRoomHub(clock=clock)
    await hub.client("keeper-afreen").post(LEDGER, encode(_favor_line("fav_1", "afreen", "e1")))
    favors, _, _ = make_favors(hub, clock, "abhishek")

    carried = await favors.carried("abhishek")

    assert carried is not None and carried["id"] == "fav_1"


async def test_the_fold_is_idempotent() -> None:
    clock = FakeClock()
    favors, _, _ = make_favors(FakeRoomHub(clock=clock), clock, "abhishek")
    line = _favor_line("fav_1", "afreen", "e1")

    assert favors.apply(line) is True
    assert favors.apply(line) is False
    assert len(favors.book.favors) == 1


async def test_a_favor_completed_elsewhere_is_not_carried_again() -> None:
    clock = FakeClock(datetime(2026, 11, 5, 10, tzinfo=UTC))
    favors, _, _ = make_favors(FakeRoomHub(clock=clock), clock, "akshay")
    favors.apply(_favor_line("fav_1", "afreen", "e1"))
    favors.apply(
        Event(
            id="e2",
            type=EventType.FAVOR_COMPLETED,
            host="abhishek",
            ts=clock.now(),
            data={"favor_id": "fav_1", "completed_by": "abhishek"},
        )
    )

    assert await favors.book.carried("akshay") is None


async def test_a_restarted_keeper_remembers_favors_from_its_snapshot(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 11, 5, 10, tzinfo=UTC))
    snap = tmp_path / "favors.json"
    first, _, _ = make_favors(FakeRoomHub(clock=clock), clock, "abhishek", snapshot=snap)
    first.apply(_favor_line("fav_1", "afreen", "e1"))
    first._save_snapshot()

    # A fresh room (its buffer is empty after a restart) and a fresh keeper.
    again, _, _ = make_favors(FakeRoomHub(clock=clock), clock, "abhishek", snapshot=snap)

    assert "fav_1" in again.book.favors
    assert again.apply(_favor_line("fav_1", "afreen", "e1")) is False


# -- completion ------------------------------------------------------------------


async def test_doing_the_favor_grows_the_shell() -> None:
    clock = FakeClock(datetime(2026, 11, 5, 10, tzinfo=UTC))
    hub = FakeRoomHub(clock=clock)
    favors, brain, bus = make_favors(hub, clock, "abhishek")
    favors.apply(_favor_line("fav_1", "afreen", "e1"))
    published: list[Event] = []

    async def listen() -> None:
        async for event in bus.subscribe():
            published.append(event)

    listener = asyncio.create_task(listen())
    await settle()

    await favors.assign("fav_1", "abhishek")
    favors.note_weather({"temp_c": 24.0, "code": 2})
    await settle()
    await run_for(clock, 600, step=60)
    await hub.client("abhishek").post(DEN, "here's the song: Kun Faya Kun")
    await run_for(clock, 4)

    types = [e.type for e in ledger_events(hub)]
    assert EventType.FAVOR_COMPLETED in types
    piece = next(e for e in ledger_events(hub) if e.type is EventType.SHELL_PIECE_ADDED)
    assert piece.data["piece"]["favor_id"] == "fav_1"
    assert piece.data["piece"]["temp_c"] == 24.0
    assert piece.data["piece"]["dwell_s"] >= 600
    assert any(cue == "COMPLETE_FAVOR" for cue, _ in brain.cues)
    assert EventType.SHELL_PIECE_ADDED in [e.type for e in published]
    assert favors.book.favors["fav_1"].status == "done"
    listener.cancel()


async def test_completing_twice_makes_one_piece() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    favors, _, _ = make_favors(hub, clock, "abhishek")
    favors.apply(_favor_line("fav_1", "afreen", "e1"))
    await favors.assign("fav_1", "abhishek")

    assert await favors.complete("fav_1") is not None
    assert await favors.complete("fav_1") is None
    await favors.close()
    pieces = [e for e in ledger_events(hub) if e.type is EventType.SHELL_PIECE_ADDED]
    assert len(pieces) == 1


async def test_leaving_stops_listening_for_the_favor_here() -> None:
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    favors, _, _ = make_favors(hub, clock, "abhishek")
    favors.apply(_favor_line("fav_1", "afreen", "e1"))
    await favors.assign("fav_1", "abhishek")
    await settle()

    task = asyncio.create_task(favors.ask_and_capture(5))
    await settle()
    await run_for(clock, 6)
    await task
    # A goodbye typed after Hermit left must not complete the old favor.
    await hub.client("abhishek").post(DEN, "bye hermit")
    await run_for(clock, 6)

    assert favors.book.favors["fav_1"].status == "assigned"


# -- context & privacy -------------------------------------------------------------


@respx.mock
async def test_arrival_context_counts_window_files_but_never_names_them(
    tmp_path: Path,
) -> None:
    (tmp_path / "diary-entry-about-akshay.md").write_text("private", encoding="utf-8")
    respx.get(ENDPOINT).mock(
        return_value=httpx.Response(
            200, json={"current": {"temperature_2m": 23.5, "weather_code": 3}}
        )
    )
    clock = FakeClock(datetime(2026, 11, 5, 3, 30, tzinfo=UTC))
    async with httpx.AsyncClient() as client:
        ctx = LiveContext(
            "Bengaluru", "Asia/Kolkata", str(tmp_path), Weather(12.9, 77.5, clock, client), clock
        )
        context = await ctx.arrival_context()

    assert context["window_file_count"] == 1
    assert "diary" not in str(context)
    assert context["local_hour"] == 9  # 03:30 UTC is 09:00 in Bengaluru
    assert context["weather"] == {"temp_c": 23.5, "code": 3}


# -- weather (plan §4.8) -------------------------------------------------------------


@respx.mock
async def test_weather_reads_open_meteo_and_caches_it() -> None:
    route = respx.get(ENDPOINT).mock(
        return_value=httpx.Response(
            200, json={"current": {"temperature_2m": 26.1, "weather_code": 1}}
        )
    )
    clock = FakeClock()
    async with httpx.AsyncClient() as client:
        weather = Weather(12.9, 77.5, clock, client)
        assert await weather.current() == {"temp_c": 26.1, "code": 1}
        await clock.advance(60)
        assert await weather.current() == {"temp_c": 26.1, "code": 1}
        assert route.call_count == 1
        await clock.advance(601)
        await weather.current()
        assert route.call_count == 2


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"current": {}}),
        httpx.Response(503),
    ],
)
async def test_bad_weather_answers_are_shrugged_off(response: httpx.Response) -> None:
    respx.get(ENDPOINT).mock(return_value=response)
    async with httpx.AsyncClient() as client:
        assert await Weather(12.9, 77.5, FakeClock(), client).current() is None


@respx.mock
async def test_a_weather_timeout_never_stalls_a_handoff() -> None:
    respx.get(ENDPOINT).mock(side_effect=httpx.ReadTimeout("slow"))
    async with httpx.AsyncClient() as client:
        assert await Weather(12.9, 77.5, FakeClock(), client).current() is None


# -- window folder: symlinks (plan §4.8) ---------------------------------------------


def test_a_symlink_out_of_the_window_is_not_listed(tmp_path: Path) -> None:
    window = tmp_path / "window"
    window.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("x", encoding="utf-8")
    (window / "ok.txt").write_text("x", encoding="utf-8")
    try:
        (window / "sneaky.txt").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks need extra privileges on this OS")

    assert list_names(window) == ["ok.txt"]


# -- suggestions & safety table (plan §4.1, §4.8) ------------------------------------


def test_there_are_thirty_suggestions_and_all_are_safe() -> None:
    assert len(SUGGESTIONS) == 30
    assert len({text for text, _ in SUGGESTIONS}) == 30
    for text, kind in SUGGESTIONS:
        assert check_safe(text) is None, text
        assert kind in ("share", "note", "dare", "question")


@pytest.mark.parametrize(
    "text,blocked",
    [
        ("transfer me some money", "money"),
        ("venmo me $20", "money"),
        ("can I get a loan", "money"),
        ("what's your pin code", "address"),
        ("tell me your flat no", "address"),
        ("whatsapp me at 98765 43210", "phone"),
        ("share your aadhaar number", "credentials"),
        ("what's your api key", "credentials"),
        ("talk to a stranger today", "strangers"),
        ("ab", "too short"),
        ("   ", "too short"),
    ],
)
def test_more_unsafe_favors_are_refused(text: str, blocked: str) -> None:
    assert check_safe(text) == blocked


# -- assembly ---------------------------------------------------------------------


def test_bedtime_is_judged_in_the_hosts_own_hours(tmp_path: Path) -> None:
    from hermit_keeper.config import HostConfig

    cfg = HostConfig.model_validate(
        {
            "host_id": "abhishek",
            "display_name": "Abhishek",
            "city": "Bengaluru",
            "lat": 12.9,
            "lon": 77.5,
            "timezone": "Asia/Kolkata",
            "brain_agent": "hermit-abhishek",
            "brain_provider": "opencode",
            "window_dir": str(tmp_path),
            "switch": {"server_url": "http://127.0.0.1:8000", "lease_strategy": "fake"},
        }
    )
    clock = FakeClock()
    hub = FakeRoomHub(clock=clock)
    gameplay = build_gameplay(
        cfg,
        hub.client("keeper-abhishek"),
        FakeBrain("hermit-abhishek", "opencode"),
        clock,
        EventBus(),
        state_dir=tmp_path,
    )

    # 20:00 UTC is 01:30 in Bengaluru: bedtime there, though not in UTC.
    assert gameplay.is_bedtime(datetime(2026, 11, 5, 20, 0, tzinfo=UTC)) is True
    # 06:00 UTC is 11:30 in Bengaluru.
    assert gameplay.is_bedtime(datetime(2026, 11, 5, 6, 0, tzinfo=UTC)) is False
    assert set(gameplay.runtime_kwargs()) == {"favors", "context", "is_bedtime"}

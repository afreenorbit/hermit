"""Phase 4: favors, the shell, bedtime and the window folder."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hermit_keeper.bedtime import is_bedtime, tease
from hermit_keeper.clock import FakeClock
from hermit_keeper.context.window import list_names
from hermit_keeper.favors import FAVOR_TTL_S, FavorBook, check_safe, classify, suggestions
from hermit_keeper.shell_model import describe, hour_band, make_piece

# -- the safety filter -------------------------------------------------------


@pytest.mark.parametrize(
    "text,blocked",
    [
        ("send me 500 rupees", "money"),
        ("pay me back on gpay", "money"),
        ("what's your address?", "address"),
        ("call me on +91 98765 43210", "phone"),
        ("tell me your password", "credentials"),
        ("send me the otp", "credentials"),
        ("dm a random person online", "strangers"),
        ("", "too short"),
        ("x" * 300, "too long"),
    ],
)
def test_unsafe_favors_are_refused(text: str, blocked: str) -> None:
    assert check_safe(text) == blocked


@pytest.mark.parametrize(
    "text",
    [
        "a photo of whatever is outside your window",
        "what did you eat today?",
        "text someone you haven't spoken to in a month",
        "recommend one thing worth ten minutes",
        "one line of a story for the next person",
    ],
)
def test_ordinary_favors_pass(text: str) -> None:
    assert check_safe(text) is None


def test_kinds_are_guessed_from_the_wording() -> None:
    assert classify("what did you eat today?") == "question"
    assert classify("text someone you miss") == "dare"
    assert classify("recommend a song") == "share"
    assert classify("the view from my desk") == "note"


def test_suggestions_rotate_so_nobody_is_asked_the_same_thing_twice() -> None:
    assert suggestions(0)[0] != suggestions(4)[0]
    assert len(suggestions(0)) == 3


# -- the favor lifecycle -----------------------------------------------------


async def test_a_favor_travels_from_one_friend_to_the_next() -> None:
    clock = FakeClock()
    book = FavorBook(clock)

    favor = await book.leave("afreen", "the last song stuck in your head")
    assert favor is not None and favor.status == "open"

    carried = await book.carried(for_host="abhishek")
    assert carried is not None and carried["id"] == favor.id

    await book.assign(favor.id, "abhishek")
    assert book.favors[favor.id].status == "assigned"

    done = await book.complete(favor.id, "abhishek")
    assert done is not None
    assert done.status == "done"
    assert done.completed_at is not None


async def test_nobody_is_handed_back_their_own_note() -> None:
    """The obvious bug in a carried favor, and a sad little loop if it happens."""
    clock = FakeClock()
    book = FavorBook(clock)
    await book.leave("afreen", "a photo of your window")

    assert await book.carried(for_host="afreen") is None
    assert await book.carried(for_host="akshay") is not None


async def test_a_rejected_favor_is_not_stored() -> None:
    clock = FakeClock()
    book = FavorBook(clock)

    assert await book.leave("afreen", "send me 2000 rupees") is None
    assert book.favors == {}
    assert book.rejected[0][1] == "money"


async def test_favors_nobody_did_expire_after_48h() -> None:
    clock = FakeClock()
    book = FavorBook(clock)
    favor = await book.leave("afreen", "what did you eat today?")
    assert favor is not None

    await clock.advance(FAVOR_TTL_S - 60)
    assert book.expire_old() == []

    await clock.advance(120)
    expired = book.expire_old()
    assert [f.id for f in expired] == [favor.id]
    assert await book.carried(for_host="akshay") is None


async def test_the_oldest_open_favor_is_carried_first() -> None:
    clock = FakeClock()
    book = FavorBook(clock)
    first = await book.leave("afreen", "recommend a song")
    await clock.advance(600)
    await book.leave("akshay", "what did you eat today?")

    carried = await book.carried(for_host="abhishek")
    assert carried is not None and first is not None
    assert carried["id"] == first.id


# -- the shell ---------------------------------------------------------------


def test_a_piece_is_identical_wherever_it_is_rendered() -> None:
    """Both the critter and the map derive the drawing from `seed`."""
    when = datetime(2026, 11, 5, 14, 30, tzinfo=UTC)
    args = dict(
        host="afreen",
        city="Indiranagar",
        brain_provider="claude-code",
        dwell_s=5400,
        departure="graceful",
        created_at=when,
        piece_id="pc_FIXED",
    )
    assert make_piece(**args).to_dict() == make_piece(**args).to_dict()  # type: ignore[arg-type]


def test_hour_bands_cover_the_whole_clock() -> None:
    assert [hour_band(h) for h in (6, 12, 19, 23, 3)] == [
        "dawn",
        "day",
        "dusk",
        "night",
        "night",
    ]


def test_an_abrupt_departure_leaves_a_cracked_piece() -> None:
    piece = make_piece(
        host="afreen",
        city="Indiranagar",
        brain_provider="codex",
        dwell_s=900,
        departure="abrupt",
        created_at=datetime(2026, 11, 5, 2, 0, tzinfo=UTC),
    )
    assert "cracked" in describe(piece, local_hour=2)
    assert "night" in describe(piece, local_hour=2)


# -- bedtime -----------------------------------------------------------------


@pytest.mark.parametrize(
    "hour,expected",
    [(0, False), (1, True), (3, True), (5, True), (6, False), (12, False), (23, False)],
)
def test_bedtime_handles_the_midnight_crossing(hour: int, expected: bool) -> None:
    assert is_bedtime(datetime(2026, 11, 5, hour, 0)) is expected


def test_a_daytime_bedtime_range_still_works() -> None:
    assert is_bedtime(datetime(2026, 11, 5, 14, 0), start="13:00", end="15:00") is True
    assert is_bedtime(datetime(2026, 11, 5, 16, 0), start="13:00", end="15:00") is False


def test_the_tease_never_congratulates_anyone_for_being_up() -> None:
    for hour in (1, 2, 4, 5):
        line = tease(datetime(2026, 11, 5, hour, 0)).lower()
        assert not any(w in line for w in ("well done", "impressive", "nice", "keep going"))


# -- the window folder -------------------------------------------------------


def test_window_lists_names_and_skips_hidden_files(tmp_path) -> None:
    (tmp_path / "notes.md").write_text("hello", encoding="utf-8")
    (tmp_path / "photo.jpg").write_text("x", encoding="utf-8")
    (tmp_path / ".secret").write_text("x", encoding="utf-8")
    (tmp_path / "subdir").mkdir()

    names = list_names(tmp_path)

    assert names == ["notes.md", "photo.jpg"]
    assert ".secret" not in names
    assert "subdir" not in names


def test_window_caps_the_list(tmp_path) -> None:
    for i in range(40):
        (tmp_path / f"file{i:02d}.txt").write_text("x", encoding="utf-8")
    assert len(list_names(tmp_path)) == 20


def test_a_missing_window_folder_is_not_an_error(tmp_path) -> None:
    assert list_names(tmp_path / "nope") == []

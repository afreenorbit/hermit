"""The group view: what every laptop shows, folded from the shared ledger.

The rule under test throughout: **two laptops must never both read as
`visiting`**, and a laptop we cannot hear from must say so rather than be
guessed at.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from hermit_keeper.events import Event, EventType
from hermit_keeper.group import STALE_AFTER_S, GroupView, mood_for

T0 = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
HOSTS = ["afreen", "abhishek", "akshay"]


def beat(host: str, state: str, present: bool, at: datetime) -> Event:
    return Event(
        type=EventType.HOST_HEARTBEAT,
        host=host,
        ts=at,
        data={"state": state, "present": present},
    )


# -- mood_for ----------------------------------------------------------------


@pytest.mark.parametrize(
    "state,present,holder,expected",
    [
        ("HOLDING", True, "afreen", "visiting"),
        ("HOLDING", True, "akshay", "waiting"),  # Switch disagrees: believe Switch
        ("CLAIMING", True, None, "waiting"),
        ("DEPARTING", True, "afreen", "away"),
        ("BEDTIME_LOCK", True, "akshay", "sleeping"),
        ("ASLEEP", False, "akshay", "sleeping"),
        ("ASLEEP", True, "akshay", "waiting"),
        ("AWAKE_WAITING", True, "akshay", "waiting"),
        (None, True, "akshay", "offline"),
    ],
)
def test_mood_mapping(state, present, holder, expected) -> None:
    assert mood_for(state, present, holder, "afreen") == expected


def test_arriving_only_follows_a_successful_claim() -> None:
    """Every awake laptop reaches when a soul frees; only the winner arrives."""
    assert mood_for("CLAIMING", True, None, "afreen") == "waiting"
    assert mood_for("HOLDING", True, "afreen", "afreen", holding_for_s=2.0) == "arriving"
    assert mood_for("HOLDING", True, "afreen", "afreen", holding_for_s=60.0) == "visiting"


def test_a_scramble_never_shows_two_laptops_arriving() -> None:
    moods = [mood_for("CLAIMING", True, None, host) for host in HOSTS]
    assert "arriving" not in moods


def test_only_the_holder_is_ever_visiting() -> None:
    moods = [mood_for("HOLDING", True, "akshay", host) for host in HOSTS]
    assert moods.count("visiting") == 1


# -- folding the ledger ------------------------------------------------------


def test_a_heartbeat_makes_a_laptop_visible_to_the_others() -> None:
    group = GroupView(HOSTS)
    group.apply(beat("abhishek", "AWAKE_WAITING", True, T0))

    snap = group.snapshot(T0, self_host="afreen")
    seen = {h["host_id"]: h for h in snap["hosts"]}

    assert seen["abhishek"]["stale"] is False
    assert seen["abhishek"]["mood"] == "waiting"
    assert seen["afreen"]["mood"] == "offline", "a laptop that never checked in is unknown"


def test_delayed_ledger_line_cannot_replace_a_newer_live_heartbeat() -> None:
    group = GroupView(HOSTS)
    recent = T0 + timedelta(minutes=10)
    group.apply(beat("afreen", "AWAKE_WAITING", True, recent))
    group.apply(beat("afreen", "ASLEEP", False, T0))

    afreen = next(h for h in group.snapshot(recent)["hosts"] if h["host_id"] == "afreen")
    assert afreen["state"] == "AWAKE_WAITING"
    assert afreen["present"] is True
    assert afreen["stale"] is False


def test_every_expected_host_appears_even_before_it_starts() -> None:
    """A laptop you forgot to run is exactly what you want to see on a dashboard."""
    snap = GroupView(HOSTS).snapshot(T0)
    assert [h["host_id"] for h in snap["hosts"]] == sorted(HOSTS)
    assert all(h["mood"] == "offline" for h in snap["hosts"])


def test_a_claim_moves_the_soul_and_only_one_laptop_is_visiting() -> None:
    group = GroupView(HOSTS)
    for host in HOSTS:
        group.apply(beat(host, "AWAKE_WAITING", True, T0))
    group.apply(Event(type=EventType.SOUL_CLAIMED, host="akshay", ts=T0, data={"holder": "akshay"}))

    snap = group.snapshot(T0, self_host="afreen")
    moods = {h["host_id"]: h["mood"] for h in snap["hosts"]}

    assert snap["soul_holder"] == "akshay"
    assert moods["akshay"] == "visiting"
    assert moods["afreen"] == "waiting"
    assert moods["abhishek"] == "waiting"
    assert list(moods.values()).count("visiting") == 1


def test_a_release_frees_the_soul_for_everyone() -> None:
    group = GroupView(HOSTS)
    group.apply(beat("akshay", "HOLDING", True, T0))
    group.apply(Event(type=EventType.SOUL_CLAIMED, host="akshay", ts=T0, data={"holder": "akshay"}))
    group.apply(
        Event(type=EventType.SOUL_RELEASED, host="akshay", ts=T0, data={"departure": "graceful"})
    )

    snap = group.snapshot(T0)
    assert snap["soul_holder"] is None
    assert all(h["mood"] != "visiting" for h in snap["hosts"])


def test_departure_shows_away_on_the_leaving_laptop() -> None:
    group = GroupView(HOSTS)
    group.apply(beat("akshay", "HOLDING", True, T0))
    group.apply(Event(type=EventType.SOUL_CLAIMED, host="akshay", ts=T0, data={"holder": "akshay"}))
    group.apply(
        Event(type=EventType.DEPARTURE_STARTED, host="akshay", ts=T0, data={"reason": "idle"})
    )

    moods = {h["host_id"]: h["mood"] for h in group.snapshot(T0)["hosts"]}
    assert moods["akshay"] == "away"


# -- silence is not absence --------------------------------------------------


def test_a_laptop_that_stops_beating_goes_offline_not_asleep() -> None:
    group = GroupView(HOSTS)
    group.apply(beat("abhishek", "AWAKE_WAITING", True, T0))

    later = T0 + timedelta(seconds=STALE_AFTER_S + 5)
    seen = {h["host_id"]: h for h in group.snapshot(later)["hosts"]}

    assert seen["abhishek"]["stale"] is True
    assert seen["abhishek"]["mood"] == "offline"
    assert seen["abhishek"]["state"] is None, "we stop repeating what we can no longer verify"


def test_a_holder_we_cannot_hear_from_is_not_reported_as_holding() -> None:
    """A lid closed mid-visit. We do not know; we must not claim they are there."""
    group = GroupView(HOSTS)
    group.apply(beat("akshay", "HOLDING", True, T0))
    group.apply(Event(type=EventType.SOUL_CLAIMED, host="akshay", ts=T0, data={"holder": "akshay"}))

    later = T0 + timedelta(seconds=STALE_AFTER_S + 5)
    snap = group.snapshot(later)

    assert snap["soul_holder"] is None
    assert all(h["holding"] is False for h in snap["hosts"])
    assert all(h["mood"] != "visiting" for h in snap["hosts"])


def test_a_laptop_just_inside_the_window_is_still_trusted() -> None:
    group = GroupView(HOSTS)
    group.apply(beat("abhishek", "AWAKE_WAITING", True, T0))

    still_ok = T0 + timedelta(seconds=STALE_AFTER_S - 1)
    seen = {h["host_id"]: h for h in group.snapshot(still_ok)["hosts"]}
    assert seen["abhishek"]["stale"] is False


def test_snapshot_matches_the_api_contract_shape() -> None:
    group = GroupView(HOSTS)
    group.apply(beat("afreen", "HOLDING", True, T0))
    snap = group.snapshot(T0, self_host="afreen")

    assert snap["v"] == 1
    assert set(snap) == {"v", "generated_at", "self", "soul_holder", "hosts"}
    for host in snap["hosts"]:
        assert set(host) == {
            "host_id",
            "state",
            "present",
            "mood",
            "last_seen",
            "stale",
            "holding",
        }

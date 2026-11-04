"""Stretch S1: the overlap finder. Pure functions, synthetic presence grids."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hermit_keeper.bedtime import is_bedtime
from hermit_keeper.overlap import (
    DAY_S,
    HostSchedule,
    OverlapParams,
    PresenceHistory,
    Window,
    choose_suggestion,
    find_windows,
    local_span,
    slot_probabilities,
)

#: Sunday 1 Nov 2026, 00:00 UTC. Every test day starts here.
BASE = datetime(2026, 11, 1, tzinfo=UTC).timestamp()
H = 3600
UTC_NIGHT = HostSchedule("UTC", "01:00", "06:00")


def daily(ranges: list[tuple[float, float]], days: int = 7) -> list[tuple[float, float]]:
    """``[(start_h, end_h)]`` every day, in UTC hours from BASE."""
    return [
        (BASE + d * DAY_S + a * H, BASE + d * DAY_S + b * H) for d in range(days) for a, b in ranges
    ]


NOW = BASE + 7 * DAY_S  # a week of history behind us, midnight UTC


# -- presence history ----------------------------------------------------------


def test_history_keeps_only_changes_and_caps_a_silent_laptop() -> None:
    history = PresenceHistory(stale_after_s=3600)
    for ts in (0, 10, 20):
        history.observe("afreen", ts, True)
    # Four hours of silence, then present again: the laptop was off, not on.
    history.observe("afreen", 4 * H, True)
    assert history.intervals("afreen", 5 * H) == [(0, 20 + H), (4 * H, 5 * H)]


def test_history_ignores_out_of_order_lines() -> None:
    history = PresenceHistory()
    history.observe("akshay", 100, True)
    history.observe("akshay", 50, False)
    assert history.intervals("akshay", 200) == [(100, 200)]
    assert history.first_seen == 100


def test_slot_probability_is_the_share_of_days_present() -> None:
    spans = daily([(9, 10)], days=3) + daily([(14, 15)], days=1)
    probs = slot_probabilities(spans, BASE, BASE + 4 * DAY_S)
    assert probs[18] == pytest.approx(3 / 4)  # 09:00 slot, three days of four
    assert probs[28] == pytest.approx(1 / 4)  # 14:00, once
    assert probs[0] == 0.0


# -- finding windows ------------------------------------------------------------


def test_finds_the_one_hour_two_friends_share() -> None:
    history = {"afreen": daily([(9, 12)]), "abhishek": daily([(11, 13)])}
    windows = find_windows(history, NOW, {"afreen": UTC_NIGHT, "abhishek": UTC_NIGHT})
    assert [(w.hosts, w.start - NOW, w.end - NOW) for w in windows] == [
        (("abhishek", "afreen"), 11 * H, 12 * H)
    ]
    assert windows[0].daily_overlap_s == H


def test_never_suggests_a_window_inside_anyones_bedtime() -> None:
    # Both up 00:00-03:00 UTC, bedtime from 01:00: only the first hour is fair.
    history = {"a1": daily([(0, 3)]), "b2": daily([(0, 3)])}
    windows = find_windows(history, NOW, {"a1": UTC_NIGHT, "b2": UTC_NIGHT})
    assert [(w.start - NOW, w.end - NOW) for w in windows] == [(0, H)]


def test_bedtime_in_another_timezone_still_counts() -> None:
    # 20:00-21:00 UTC is 01:30-02:30 in Bengaluru: bedtime for that host.
    history = {"a1": daily([(20, 21)]), "b2": daily([(20, 21)])}
    sched = {"a1": UTC_NIGHT, "b2": HostSchedule("Asia/Kolkata")}
    assert find_windows(history, NOW, sched) == []


def test_says_nothing_without_a_day_of_history() -> None:
    history = {"a1": daily([(9, 12)], days=1), "b2": daily([(9, 12)], days=1)}
    early = BASE + 20 * H
    assert find_windows(history, early, {}, history_start=BASE) == []


def test_friends_who_overlap_all_day_do_not_need_help() -> None:
    history = {"a1": daily([(8, 20)]), "b2": daily([(8, 20)])}
    assert find_windows(history, NOW, {"a1": UTC_NIGHT, "b2": UTC_NIGHT}) == []


def test_an_irregular_overlap_is_not_a_routine() -> None:
    # Overlapped once in seven days: p = 1/7, well under 0.6.
    history = {"a1": daily([(9, 12)]), "b2": daily([(10, 12)], days=1)}
    assert find_windows(history, NOW, {"a1": UTC_NIGHT, "b2": UTC_NIGHT}) == []


def test_a_window_already_under_way_starts_now() -> None:
    history = {"a1": daily([(9, 12)]), "b2": daily([(9, 12)])}
    now = NOW + 10 * H + 15 * 60
    windows = find_windows(history, now, {"a1": UTC_NIGHT, "b2": UTC_NIGHT})
    assert windows[0].start == now
    assert windows[0].end == NOW + 12 * H


def test_too_short_is_not_worth_a_call() -> None:
    history = {"a1": daily([(9, 12)]), "b2": daily([(11.5, 13)])}
    params = OverlapParams(min_window_s=3600)
    assert find_windows(history, NOW, {"a1": UTC_NIGHT, "b2": UTC_NIGHT}, params) == []


def test_slot_must_divide_a_day() -> None:
    with pytest.raises(ValueError):
        OverlapParams(slot_s=7 * 60)


def test_local_span_reads_in_the_hosts_own_clock() -> None:
    window = Window(("a1", "b2"), NOW + 17 * H, NOW + 18 * H, H)
    assert local_span(window, "Asia/Kolkata") == "22:30-23:30"


# -- choosing one -------------------------------------------------------------


def _w(a: str, b: str, start_h: float, daily_h: float = 1.0) -> Window:
    return Window((a, b), NOW + start_h * H, NOW + (start_h + 1) * H, daily_h * H)


def test_only_pairs_hermit_is_actually_with() -> None:
    windows = [_w("abhishek", "akshay", 1), _w("afreen", "akshay", 2)]
    chosen = choose_suggestion(windows, NOW, involving="afreen")
    assert chosen is not None and chosen.hosts == ("afreen", "akshay")


def test_a_pair_is_not_suggested_twice_within_three_days() -> None:
    windows = [_w("a1", "b2", 1)]
    past = [(["b2", "a1"], NOW - 2 * DAY_S)]
    assert choose_suggestion(windows, NOW, past, OverlapParams(min_gap_s=0)) is None
    later = NOW + DAY_S + 1
    assert choose_suggestion(windows, later, past, OverlapParams(min_gap_s=0)) is not None


def test_the_group_gets_one_suggestion_at_a_time() -> None:
    windows = [_w("a1", "c3", 1)]
    past = [(("a1", "b2"), NOW - H)]
    assert choose_suggestion(windows, NOW, past) is None
    assert choose_suggestion(windows, NOW + 6 * H, past) is not None


def test_longest_waiting_pair_goes_first_then_the_rarer_one() -> None:
    windows = [_w("a1", "b2", 1), _w("a1", "c3", 5, daily_h=0.5), _w("a1", "d4", 3)]
    params = OverlapParams(min_gap_s=0)
    # Never suggested beats suggested-long-ago.
    past = [(("a1", "b2"), NOW - 10 * DAY_S)]
    chosen = choose_suggestion(windows, NOW, past, params)
    assert chosen is not None and chosen.hosts == ("a1", "c3")  # rarer of the never-suggested
    # With nobody new left, the one that waited longest wins.
    past += [(("a1", "c3"), NOW - 4 * DAY_S), (("a1", "d4"), NOW - 5 * DAY_S)]
    chosen = choose_suggestion(windows, NOW, past, params)
    assert chosen is not None and chosen.hosts == ("a1", "b2")


# -- properties ------------------------------------------------------------------

ZONES = ["UTC", "Asia/Kolkata", "Asia/Kathmandu", "Europe/Berlin", "America/Toronto"]

routine = st.lists(st.tuples(st.integers(0, 47), st.integers(1, 16)), min_size=1, max_size=3)
schedule = st.builds(
    HostSchedule,
    st.sampled_from(ZONES),
    st.sampled_from(["22:00", "23:30", "00:00", "01:00", "02:15"]),
    st.sampled_from(["05:00", "06:00", "07:30"]),
)


def _spans(slots: list[tuple[int, int]], days: int = 8) -> list[tuple[float, float]]:
    return [
        (BASE + d * DAY_S + s * 1800, BASE + d * DAY_S + (s + n) * 1800)
        for d in range(days)
        for s, n in slots
    ]


@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    routines=st.lists(routine, min_size=2, max_size=3),
    schedules=st.lists(schedule, min_size=3, max_size=3),
    minute=st.integers(0, 1439),
    seed=st.integers(0, 1000),
)
def test_every_window_is_long_enough_upcoming_and_outside_bedtime(
    routines: list[list[tuple[int, int]]],
    schedules: list[HostSchedule],
    minute: int,
    seed: int,
) -> None:
    hosts = [f"h{i}" for i in range(len(routines))]
    history = {h: _spans(r) for h, r in zip(hosts, routines, strict=False)}
    sched = dict(zip(hosts, schedules, strict=False))
    now = BASE + 8 * DAY_S + minute * 60
    params = OverlapParams()

    windows = find_windows(history, now, sched, params)

    for window in windows:
        assert window.duration_s >= params.min_window_s
        assert now <= window.start < now + params.horizon_s
        # Brute force, independent of the exact check in HostSchedule.
        for host in window.hosts:
            zone = ZoneInfo(sched[host].timezone)
            t = window.start
            while t < window.end:
                local = datetime.fromtimestamp(t, tz=UTC).astimezone(zone)
                assert not is_bedtime(local, sched[host].bedtime_start, sched[host].bedtime_end)
                t += 60

    # Deterministic and order-blind: same data in any order, same answer.
    shuffled = list(history.items())
    random.Random(seed).shuffle(shuffled)
    again = find_windows({h: list(reversed(s)) for h, s in shuffled}, now, sched, params)
    assert again == windows
    assert choose_suggestion(again, now) == choose_suggestion(windows, now)


@settings(max_examples=60, deadline=None)
@given(
    times=st.lists(st.floats(0, 30 * DAY_S, allow_nan=False), min_size=1, max_size=40),
    pairs=st.lists(st.sampled_from([("a", "b"), ("a", "c"), ("b", "c")]), min_size=1),
)
def test_rate_limits_hold_however_often_the_holder_asks(
    times: list[float], pairs: list[tuple[str, str]]
) -> None:
    """Replaying the keeper asking at random moments never breaks the limits."""
    params = OverlapParams()
    past: list[tuple[tuple[str, str], float]] = []
    for i, t in enumerate(sorted(times)):
        a, b = pairs[i % len(pairs)]
        chosen = choose_suggestion([Window((a, b), t + H, t + 2 * H, H)], t, past, params)
        if chosen is not None:
            past.append((chosen.hosts, t))
    for i, (pair, when) in enumerate(past):
        for other_pair, other_when in past[i + 1 :]:
            assert other_when - when >= params.min_gap_s
            if other_pair == pair:
                assert other_when - when >= params.cooldown_s

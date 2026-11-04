"""Stretch S2: the quiet-friend nudge. Pure rules, no clock."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from hermit_keeper.nudge import NudgeParams, choose_nudge, quiet_friends

H = 3600.0
DAY = 24 * H
HOSTS = ["afreen", "abhishek", "akshay"]


def test_nobody_is_quiet_before_three_days() -> None:
    last = {"afreen": 0.0, "abhishek": 0.0, "akshay": 0.0}
    assert choose_nudge(HOSTS, last, 0.0, 71 * H, holder="afreen") is None


def test_a_friend_quiet_for_three_days_gets_a_nudge() -> None:
    last = {"afreen": 80 * H, "abhishek": 80 * H, "akshay": 2 * H}
    friend = choose_nudge(HOSTS, last, 0.0, 80 * H, holder="afreen")
    assert friend is not None
    assert friend.host == "akshay"
    assert friend.quiet_since == 2 * H
    assert friend.days == 3.2
    assert not friend.never_hosted


def test_never_hosted_counts_from_the_start_of_the_group() -> None:
    last = {"afreen": 79 * H}
    friend = choose_nudge(["afreen", "akshay"], last, 10 * H, 80 * H, holder="afreen")
    assert friend is None  # only 70 h of history: give them a chance first
    friend = choose_nudge(["afreen", "akshay"], last, 10 * H, 83 * H, holder="afreen")
    assert friend is not None and friend.never_hosted and friend.quiet_since == 10 * H


def test_never_about_the_friend_hermit_is_with() -> None:
    assert choose_nudge(["akshay"], {}, 0.0, 100 * H, holder="akshay") is None


def test_once_per_quiet_spell() -> None:
    last = {"akshay": 0.0}
    past = [("akshay", 75 * H)]
    # Ten days later, still the same spell: still nothing.
    assert choose_nudge(["akshay"], last, 0.0, 240 * H, past, holder="afreen") is None
    # They host again; a new spell must itself reach 72 h.
    last = {"akshay": 250 * H}
    assert choose_nudge(["akshay"], last, 0.0, 300 * H, past, holder="afreen") is None
    friend = choose_nudge(["akshay"], last, 0.0, 322 * H, past, holder="afreen")
    assert friend is not None and friend.quiet_since == 250 * H


def test_the_group_hears_at_most_one_nudge_per_gap() -> None:
    last = {"abhishek": 0.0, "akshay": 0.0}
    past = [("akshay", 100 * H)]
    assert choose_nudge(["abhishek", "akshay"], last, 0.0, 105 * H, past) is None
    friend = choose_nudge(["abhishek", "akshay"], last, 0.0, 112 * H, past)
    assert friend is not None and friend.host == "abhishek"


def test_quietest_first_then_by_name() -> None:
    last = {"bee": 0.0, "cat": 0.0, "ant": 10 * H}
    order = [f.host for f in quiet_friends(["cat", "bee", "ant"], last, 0.0, 100 * H)]
    assert order == ["bee", "cat", "ant"]


def test_quiet_after_is_configurable() -> None:
    params = NudgeParams(quiet_after_s=24 * H)
    friend = choose_nudge(["akshay"], {"akshay": 0.0}, 0.0, 25 * H, params=params)
    assert friend is not None


@settings(max_examples=80, deadline=None)
@given(
    hostings=st.lists(
        st.tuples(st.sampled_from(HOSTS), st.floats(0, 30 * DAY, allow_nan=False)),
        max_size=30,
    ),
    checks=st.lists(st.floats(0, 30 * DAY, allow_nan=False), min_size=1, max_size=60),
)
def test_replayed_month_never_repeats_a_spell_or_crowds_the_den(
    hostings: list[tuple[str, float]], checks: list[float]
) -> None:
    """Replay a month: hostings and keeper checks at random moments."""
    params = NudgeParams()
    timeline = sorted([(t, "host", h) for h, t in hostings] + [(t, "check", "") for t in checks])
    last: dict[str, float] = {}
    past: list[tuple[str, float]] = []
    spells: list[tuple[str, float]] = []
    holder: str | None = None
    for t, kind, host in timeline:
        if kind == "host":
            last[host] = t
            holder = host
            continue
        friend = choose_nudge(HOSTS, last, 0.0, t, past, holder=holder, params=params)
        if friend is None:
            continue
        assert friend.host != holder
        assert t - friend.quiet_since >= params.quiet_after_s
        assert (friend.host, friend.quiet_since) not in spells, "same spell nudged twice"
        if past:
            assert t - past[-1][1] >= params.min_gap_s
        spells.append((friend.host, friend.quiet_since))
        past.append((friend.host, t))

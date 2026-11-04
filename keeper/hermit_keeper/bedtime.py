"""The bedtime rule. Owner: Abhishek (4.4).

The rule that makes Hermit worth trusting: past your bedtime it *leaves*. It
never thanks you for being up, never rewards staying late, and never asks for
one more thing. A friend who sleeps is the point.
"""

from __future__ import annotations

from datetime import datetime, time


def _parse(value: str) -> time:
    hour, _, minute = value.partition(":")
    return time(int(hour), int(minute or 0))


def is_bedtime(local_now: datetime, start: str = "01:00", end: str = "06:00") -> bool:
    """Is it bedtime for this host right now?

    Handles ranges crossing midnight, which is the normal case: 01:00-06:00
    means "after one in the morning until six", not "between 1am and 6am on the
    same clock sweep".
    """
    begin, finish = _parse(start), _parse(end)
    now = local_now.time()
    if begin <= finish:
        return begin <= now < finish
    return now >= begin or now < finish


def tease(local_now: datetime) -> str:
    """A gentle line for leaving. Never approving of the hour."""
    hour = local_now.hour
    if hour < 3:
        return "it's past one. I'm going — and so should you."
    if hour < 5:
        return "whatever this is, it'll still be here tomorrow. goodnight."
    return "the sun's nearly up. go to bed, seriously."

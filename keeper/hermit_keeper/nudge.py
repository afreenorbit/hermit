"""Stretch S2: ask the group to leave a favor for someone quiet. Opt-in.

Spec: plan.md 4.7. Off unless ``features.nudge`` is set.

If one friend has not had Hermit for three days, the friendship is drifting in
exactly the way Hermit exists to notice. The fix is not to ping that friend —
being chased by a crab is not a reason to come back. Hermit asks the *others*,
in the den, to leave something for them instead.

Pure functions only; ``stretch.py`` reads the ledger and does the talking.

The rules:

* Only friends quiet for at least ``quiet_after_s`` (72 h by default). A friend
  who never hosted is measured from the start of the group's history, so a
  brand-new group does not nag about people who simply have not had a turn.
* Never the friend Hermit is with right now.
* **Once per quiet spell.** A spell starts when the friend last hosted. After
  one nudge nothing more is said about them until they host again — and then
  a fresh spell has to reach 72 h before it can be mentioned.
* At most one nudge per ``min_gap_s`` across the whole group, so the den never
  fills with "and also…".
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

DAY_S = 86400.0


@dataclass(frozen=True)
class NudgeParams:
    #: How long without hosting before a friend counts as quiet.
    quiet_after_s: float = 72 * 3600
    #: Group-wide: no two nudges closer together than this.
    min_gap_s: float = 12 * 3600


@dataclass(frozen=True)
class QuietFriend:
    host: str
    #: Start of the current quiet spell (epoch seconds): when they last hosted,
    #: or the start of the group's history if they never have.
    quiet_since: float
    quiet_s: float
    never_hosted: bool

    @property
    def days(self) -> float:
        return round(self.quiet_s / DAY_S, 1)


def quiet_friends(
    hosts: Iterable[str],
    last_hosted: Mapping[str, float],
    history_start: float,
    now: float,
    params: NudgeParams | None = None,
) -> list[QuietFriend]:
    """Everyone quiet for long enough, quietest first."""
    params = params or NudgeParams()
    out: list[QuietFriend] = []
    for host in sorted(set(hosts)):
        last = last_hosted.get(host)
        since = last if last is not None else history_start
        quiet = now - since
        if quiet >= params.quiet_after_s:
            out.append(QuietFriend(host, since, quiet, last is None))
    return sorted(out, key=lambda f: (-f.quiet_s, f.host))


def choose_nudge(
    hosts: Iterable[str],
    last_hosted: Mapping[str, float],
    history_start: float,
    now: float,
    past_nudges: Iterable[tuple[str, float]] = (),
    *,
    holder: str | None = None,
    params: NudgeParams | None = None,
) -> QuietFriend | None:
    """The one friend worth a nudge right now, or ``None``.

    Args:
        last_hosted: when each host last had Hermit (epoch seconds).
        past_nudges: ``(target_host, when)`` of every earlier ``NUDGE_SENT``.
        holder: who Hermit is with now. Never nudged about themselves.
    """
    params = params or NudgeParams()
    past = [(target, when) for target, when in past_nudges if when <= now]
    if past and now - max(when for _, when in past) < params.min_gap_s:
        return None
    for friend in quiet_friends(hosts, last_hosted, history_start, now, params):
        if friend.host == holder:
            continue
        if any(target == friend.host and when >= friend.quiet_since for target, when in past):
            continue  # already asked about this spell
        return friend
    return None

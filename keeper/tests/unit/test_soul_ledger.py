"""The ledger fold that replaces the roles endpoint Switch does not have.

Every keeper runs this over the same ledger and must get the same holder. The
tests feed it hand-built ledger lines, in arbitrary order, and check the rules:
claims come from brain ACKs, conflicts resolve by ledger order, silence frees
the soul only while we were listening.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from hermit_keeper.brain.protocol import format_ack, format_cue
from hermit_keeper.events import Event, EventType
from hermit_keeper.lease.soul_ledger import SoulLedger
from hermit_keeper.ledger import encode
from hermit_keeper.room.base import Message

T0 = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)
STALE = 10.0


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


class Ledger:
    """Builds ledger lines the way keepers and brains really write them."""

    def __init__(self) -> None:
        self.lines: list[Message] = []
        self._n = 0

    def _add(self, sender: str, text: str, when: float) -> str:
        self._n += 1
        message_id = f"$m{self._n:04d}"
        self.lines.append(
            Message(id=message_id, room="hermit-ledger", sender=sender, text=text, ts=at(when))
        )
        return message_id

    def cue(self, host: str, cue: str, when: float) -> str:
        cue_id = f"cue_{host}_{self._n}"
        self._add(f"keeper-{host}", format_cue(f"hermit-{host}", cue, cue_id, host, {}), when)
        return cue_id

    def ack(self, host: str, cue: str, cue_id: str | None, ok: bool, when: float) -> str:
        return self._add(f"hermit-{host}", format_ack(cue, ok, cue_id), when)

    def claim(self, host: str, when: float, ok: bool = True) -> str:
        cue_id = self.cue(host, "CLAIM_SOUL", when - 0.5)
        return self.ack(host, "CLAIM_SOUL", cue_id, ok, when)

    def event(self, host: str, kind: EventType, when: float, **data: object) -> None:
        self._add(
            f"keeper-{host}", encode(Event(type=kind, host=host, ts=at(when), data=data)), when
        )

    def beat(self, host: str, when: float, **data: object) -> None:
        self.event(host, EventType.HOST_HEARTBEAT, when, state="AWAKE_WAITING", **data)


def fold(ledger: Ledger, now: float, *, listening_since: float | None = 0.0, me: str | None = None):
    book = SoulLedger(stale_after_s=STALE)
    since = at(listening_since) if listening_since is not None else None
    lines = list(ledger.lines)
    random.Random(7).shuffle(lines)  # arrival order must not matter
    return book.fold(lines, now=at(now), listening_since=since, self_host=me)


def test_an_empty_ledger_has_no_holder() -> None:
    assert fold(Ledger(), now=1).holder is None


def test_a_brain_ack_is_a_claim() -> None:
    ledger = Ledger()
    ledger.claim("afreen", 1)
    view = fold(ledger, now=2)
    assert view.holder == "afreen"
    assert view.claim is not None and view.claim.host == "afreen"


def test_a_refused_claim_is_not_a_claim() -> None:
    ledger = Ledger()
    ledger.claim("afreen", 1, ok=False)
    assert fold(ledger, now=2).holder is None


def test_a_confirmed_release_frees_the_soul() -> None:
    ledger = Ledger()
    ref = ledger.claim("afreen", 1)
    ledger.event("afreen", EventType.SOUL_RELEASED, 3, releases=ref, confirmed=True)
    assert fold(ledger, now=4).holder is None


def test_the_brains_release_ack_frees_only_earlier_claims() -> None:
    ledger = Ledger()
    cue_id = ledger.cue("afreen", "RELEASE_SOUL", 0.5)
    ledger.ack("afreen", "RELEASE_SOUL", cue_id, True, 0.6)  # before the claim: irrelevant
    ledger.claim("afreen", 2)
    assert fold(ledger, now=3).holder == "afreen"

    cue_id = ledger.cue("afreen", "RELEASE_SOUL", 4)
    ledger.ack("afreen", "RELEASE_SOUL", cue_id, True, 4.5)
    assert fold(ledger, now=5).holder is None


def test_the_handoff_goodbye_line_alone_does_not_free_the_soul() -> None:
    """Handoff writes SOUL_RELEASED *before* the brain lets go. Only the
    lease's line, naming the claim it ends, counts."""
    ledger = Ledger()
    ledger.claim("afreen", 1)
    ledger.event("afreen", EventType.SOUL_RELEASED, 2, departure="graceful")
    assert fold(ledger, now=3).holder == "afreen"


def test_two_live_claims_resolve_to_the_earlier_one_on_every_keeper() -> None:
    ledger = Ledger()
    first = ledger.claim("abhishek", 1.0)
    second = ledger.claim("akshay", 1.2)
    ledger.beat("abhishek", 2)
    ledger.beat("akshay", 2)
    for seed_now in (2.5, 3.0, 4.0):
        view = fold(ledger, now=seed_now)
        assert view.holder == "abhishek"
        assert [c.ref for c in view.losers] == [second]
        assert view.claim is not None and view.claim.ref == first


def test_a_tie_on_timestamp_breaks_on_message_id() -> None:
    ledger = Ledger()
    ledger.claim("akshay", 1.0)
    ledger.claim("abhishek", 1.0)  # same instant, larger message id
    assert fold(ledger, now=2).holder == "akshay"


def test_a_claim_made_after_the_holder_went_silent_wins() -> None:
    """Lid slam, then a partition heals: the old holder's claim had expired."""
    ledger = Ledger()
    ledger.claim("afreen", 1)
    ledger.beat("afreen", 2)
    ledger.claim("akshay", 2 + STALE + 1)  # afreen silent for > STALE by then
    ledger.beat("afreen", 2 + STALE + 2)  # afreen's laptop comes back
    view = fold(ledger, now=2 + STALE + 3)
    assert view.holder == "akshay"
    assert [c.host for c in view.losers] == ["afreen"]


def test_a_silent_holder_is_free_once_we_have_listened_long_enough() -> None:
    ledger = Ledger()
    ledger.claim("afreen", 1)
    ledger.beat("afreen", 2)
    assert fold(ledger, now=2 + STALE - 1).holder == "afreen"
    view = fold(ledger, now=2 + STALE + 1)
    assert view.holder is None and view.stale


def test_silence_while_we_were_deaf_proves_nothing() -> None:
    ledger = Ledger()
    ledger.claim("afreen", 1)
    # We reconnected at t=30: nothing heard since t=1, but we only just started listening.
    assert fold(ledger, now=31, listening_since=30).holder == "afreen"


def test_our_own_claim_never_goes_stale_in_our_own_eyes() -> None:
    ledger = Ledger()
    ledger.claim("afreen", 1)
    assert fold(ledger, now=100, me="afreen").holder == "afreen"


def test_a_keeper_that_just_started_learns_the_holder_from_a_heartbeat() -> None:
    ledger = Ledger()
    ledger.beat("afreen", 50, soul={"ack": "$old-ack", "ack_ts": at(10).isoformat()})
    view = fold(ledger, now=51, listening_since=49)
    assert view.holder == "afreen"
    assert view.claim is not None and view.claim.ref == "$old-ack"


def test_an_ack_without_a_cue_id_is_attributed_by_the_brain_name() -> None:
    ledger = Ledger()
    ledger.ack("akshay", "CLAIM_SOUL", None, True, 1)
    assert fold(ledger, now=2).holder == "akshay"


def test_soul_claimed_restates_the_same_claim_not_a_second_one() -> None:
    ledger = Ledger()
    ref = ledger.claim("afreen", 1)
    ledger.event(
        "afreen", EventType.SOUL_CLAIMED, 1.5, holder="afreen", ack=ref, ack_ts=at(1).isoformat()
    )
    view = fold(ledger, now=2)
    assert view.holder == "afreen" and view.losers == []

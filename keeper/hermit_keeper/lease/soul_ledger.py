"""Who holds the soul, worked out from the ledger alone. Owner: Afreen.

Switch enforces the soul's exclusivity (an exclusive role: a second
``assume_role`` fails), but it gives the keeper **no way to ask** who holds it:
there is no roles endpoint over HTTP (docs/switch-facts.md, "Verified against a
running server"). So every keeper *observes* the outcome in the ledger room and
folds it with this one pure function. Same ledger in, same holder out, on every
laptop.

What counts as evidence:

=======================================  ========================================
ledger line                              meaning
=======================================  ========================================
brain ``HERMIT-ACK/1 CLAIM_SOUL ok:true``  that brain's ``assume_role`` succeeded:
                                         a claim, keyed by the ACK's message id
keeper ``SOUL_CLAIMED {ack, ack_ts}``    the same claim, restated by its keeper
keeper ``HOST_HEARTBEAT {soul: {..}}``   "I still hold claim <ack>" — lets a
                                         keeper that just started learn the
                                         holder without the original lines
brain ``HERMIT-ACK/1 RELEASE_SOUL ok``   that brain's claims so far are over
keeper ``SOUL_RELEASED {releases: id}``  that specific claim is over
any line from a host                     that host is alive at that moment
=======================================  ========================================

Claims are ordered by the **brain ACK's** server timestamp and message id. ACKs
are posted by brains, never by keepers, so every keeper receives them from the
server with the same timestamp — the order cannot depend on whose laptop clock
is ahead.

**Two claims, no release between them.** With real Switch this should only
happen after a lease expiry; with a confused brain it can happen any time. The
rule is deterministic: the earlier claim keeps the soul, *unless* its host had
gone silent for longer than ``stale_after_s`` by the time the later claim was
made — then Switch has freed the role, and the later claim is the real one.
The other claim is a *loser*, and its keeper must tell its brain to let go.

**Stale holders.** If the holder has said nothing for ``stale_after_s`` while
we were listening, the soul is treated as free: that is a lid slam, and Switch
will have expired the lease. Silence while *we* were offline proves nothing,
which is what ``listening_since`` is for.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..brain.protocol import Ack, Cue, parse_ack, parse_cue
from ..events import Event, EventType
from ..ledger import decode
from ..room.base import Message

CLAIM_CUE = "CLAIM_SOUL"
RELEASE_CUE = "RELEASE_SOUL"


@dataclass(frozen=True)
class Claim:
    """One successful ``assume_role``, as seen in the ledger."""

    host: str
    ref: str  # the brain ACK's message id
    at: datetime  # the brain ACK's (server) timestamp

    @property
    def key(self) -> tuple[datetime, str]:
        return (self.at, self.ref)


@dataclass
class SoulView:
    """The fold's answer."""

    #: host_id holding the soul, or None if it is free (or its holder went stale).
    holder: str | None = None
    #: The winning claim, even if its holder has since gone stale.
    claim: Claim | None = None
    #: True when ``claim`` exists but its host has gone silent: free in practice.
    stale: bool = False
    #: Live claims that lost a conflict. Their keepers must release them.
    losers: list[Claim] = field(default_factory=list)
    #: Last time each host was heard from.
    last_seen: dict[str, datetime] = field(default_factory=dict)


Parsed = tuple[Cue | None, Ack | None, Event | None]


class SoulLedger:
    """Folds ledger messages into a :class:`SoulView`. Caches line parsing."""

    def __init__(self, stale_after_s: float) -> None:
        self.stale_after_s = stale_after_s
        self._parsed: dict[str, Parsed] = {}

    def _parse(self, message: Message) -> Parsed:
        cached = self._parsed.get(message.id)
        if cached is None:
            text = message.text
            cached = (
                parse_cue(text) if "HERMIT-CUE/1" in text else None,
                parse_ack(text) if "HERMIT-ACK/1" in text else None,
                decode(text),
            )
            if len(self._parsed) > 20_000:
                self._parsed.clear()
            self._parsed[message.id] = cached
        return cached

    def fold(
        self,
        messages: Iterable[Message],
        *,
        now: datetime,
        listening_since: datetime | None,
        self_host: str | None = None,
    ) -> SoulView:
        rows = [(m, self._parse(m)) for m in messages]
        rows.sort(key=lambda row: (row[0].ts, row[0].id))

        # Pass 1: which keeper sent which cue, so an ACK can be attributed.
        cue_hosts: dict[str, str] = {}
        for _message, (sent, _ack, _event) in rows:
            if sent is not None and sent.id and sent.host:
                cue_hosts[sent.id] = sent.host

        seen: dict[str, list[datetime]] = {}
        claims: dict[str, Claim] = {}
        released: set[str] = set()
        brain_releases: list[tuple[str, tuple[datetime, str]]] = []

        def heard(host: str, at: datetime) -> None:
            bisect.insort(seen.setdefault(host, []), at)

        for message, (cue, ack, event) in rows:
            if ack is not None:
                host = _ack_host(ack, message.sender, cue_hosts)
                if host is None:
                    continue
                heard(host, message.ts)
                if ack.cue == CLAIM_CUE and ack.ok:
                    claims.setdefault(message.id, Claim(host, message.id, message.ts))
                elif ack.cue == RELEASE_CUE and ack.ok:
                    brain_releases.append((host, (message.ts, message.id)))
                continue
            if event is None:
                if cue is not None and cue.host:
                    heard(cue.host, message.ts)
                continue

            heard(event.host, message.ts)
            data = event.data
            if event.type is EventType.SOUL_CLAIMED:
                claim = _claim_from(event.host, data.get("ack"), data.get("ack_ts"))
                if claim is not None:
                    claims.setdefault(claim.ref, claim)
            elif event.type is EventType.HOST_HEARTBEAT:
                soul = data.get("soul")
                if isinstance(soul, dict):
                    claim = _claim_from(event.host, soul.get("ack"), soul.get("ack_ts"))
                    if claim is not None:
                        claims.setdefault(claim.ref, claim)
            elif event.type is EventType.SOUL_RELEASED:
                ref = data.get("releases")
                if isinstance(ref, str):
                    released.add(ref)

        # Each host's newest claim is the only one that can still be live.
        latest: dict[str, Claim] = {}
        for claim in claims.values():
            if claim.ref in released:
                continue
            if any(h == claim.host and key > claim.key for h, key in brain_releases):
                continue
            current = latest.get(claim.host)
            if current is None or claim.key > current.key:
                latest[claim.host] = claim

        view = SoulView(last_seen={h: times[-1] for h, times in seen.items()})
        winner: Claim | None = None
        for claim in sorted(latest.values(), key=lambda c: c.key):
            if winner is None:
                winner = claim
            elif self._silent_at(seen.get(winner.host, []), winner, claim.at):
                view.losers.append(winner)
                winner = claim
            else:
                view.losers.append(claim)

        view.claim = winner
        if winner is None:
            return view
        if winner.host != self_host and listening_since is not None:
            last = max(view.last_seen.get(winner.host, winner.at), winner.at, listening_since)
            view.stale = now - last > timedelta(seconds=self.stale_after_s)
        view.holder = None if view.stale else winner.host
        return view

    def _silent_at(self, times: list[datetime], claim: Claim, at: datetime) -> bool:
        """Had ``claim``'s host been silent for too long by ``at``?"""
        index = bisect.bisect_right(times, at)
        last = max(times[index - 1], claim.at) if index else claim.at
        return at - last > timedelta(seconds=self.stale_after_s)


def _ack_host(ack: Ack, sender: str, cue_hosts: dict[str, str]) -> str | None:
    if ack.id is not None and ack.id in cue_hosts:
        return cue_hosts[ack.id]
    # Fallback for a brain that forgot to echo the cue id: the agent naming
    # convention, hermit-<host_id>.
    if sender.startswith("hermit-") and len(sender) > len("hermit-"):
        return sender[len("hermit-") :]
    return None


def _claim_from(host: str, ref: object, at: object) -> Claim | None:
    if not isinstance(ref, str) or not ref or not isinstance(at, str):
        return None
    try:
        when = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return Claim(host, ref, when)

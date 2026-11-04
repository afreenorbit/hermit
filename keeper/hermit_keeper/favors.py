"""Favors: the note one friend leaves for whoever Hermit visits next.

Owner: Abhishek (Phase 4.1). Built here so the simulation can run end to end;
tune the wording and the suggestion list freely, the seams are what matter.

**Not Switch Tasks.** A Task needs a performer agent up front (docs/switch-facts
SP5) and a favor has none by definition — that is the whole idea. So the ledger
holds the state and a room document holds the text.

The lifecycle, which is the part worth getting right:

    open ──assign──> assigned ──complete──> done
      └────────────── 48 h ──────────────> expired
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from .clock import Clock
from .ids import new_id

log = structlog.get_logger(__name__)

FAVOR_TTL_S = 48 * 3600

#: Rotated through when Hermit asks. Small, specific and doable in a minute —
#: a favor that feels like homework never gets done.
SUGGESTIONS: list[tuple[str, str]] = [
    ("a photo of whatever is outside your window right now", "dare"),
    ("the last song that got stuck in your head", "share"),
    ("one thing you're quietly proud of this week", "note"),
    ("what did you eat today? be honest", "question"),
    ("text someone you haven't spoken to in a month", "dare"),
    ("recommend one thing worth ten minutes", "share"),
    ("the worst photo on your camera roll", "dare"),
    ("one line of a story for the next person to continue", "note"),
    ("what's the view from where you're sitting?", "question"),
    ("something small that made today better", "note"),
]

_KIND_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("question", re.compile(r"\?\s*$|^\s*(what|who|where|when|why|how)\b", re.I)),
    ("dare", re.compile(r"\b(dare|go and|text|call|send someone|try to)\b", re.I)),
    ("share", re.compile(r"\b(send|share|recommend|post|show us|link)\b", re.I)),
]

#: Things a favor must never ask for. Hermit runs between friends, but a friend
#: can be careless, and this is the one place a bad ask reaches someone else's
#: laptop with Hermit's authority behind it.
_UNSAFE: list[tuple[str, re.Pattern[str]]] = [
    (
        "money",
        re.compile(
            r"\b(upi|paytm|gpay|venmo|paypal|rupees|₹|\$\d|send money|transfer|loan|pay me)\b",
            re.I,
        ),
    ),
    (
        "address",
        re.compile(r"\b(address|where do you live|flat no|pin ?code|postcode|zip ?code)\b", re.I),
    ),
    ("phone", re.compile(r"(\+?\d[\d\s-]{8,}\d)", re.I)),
    (
        "credentials",
        re.compile(r"\b(password|otp|pin|cvv|aadhaar|pan card|login|api key|token)\b", re.I),
    ),
    (
        "strangers",
        re.compile(r"\b(stranger|random person|anyone online|dm someone you don't know)\b", re.I),
    ),
]


class FavorDocuments(Protocol):
    """What favors need from a room. ``FakeRoomClient`` already satisfies it."""

    async def create_room_document(
        self, room: str, name: str, description: str, instructions: str, content: str
    ) -> str: ...


@dataclass
class Favor:
    """Mirrors shared/schemas/favor.schema.json."""

    id: str
    left_by: str
    text: str
    kind: str
    created_at: str
    assignee: str | None = None
    status: str = "open"
    switch_document_id: str | None = None
    completed_at: str | None = None
    v: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": self.v,
            "id": self.id,
            "left_by": self.left_by,
            "text": self.text,
            "kind": self.kind,
            "created_at": self.created_at,
            "assignee": self.assignee,
            "status": self.status,
            "switch_document_id": self.switch_document_id,
            "completed_at": self.completed_at,
        }


def classify(text: str) -> str:
    """Rough kind from the wording. Only flavour — nothing branches on it."""
    for kind, pattern in _KIND_RULES:
        if pattern.search(text):
            return kind
    return "note"


def check_safe(text: str) -> str | None:
    """Return the reason a favor is unacceptable, or None if it is fine."""
    if len(text.strip()) < 3:
        return "too short"
    if len(text) > 280:
        return "too long"
    for reason, pattern in _UNSAFE:
        if pattern.search(text):
            return reason
    return None


def suggestions(seed: int, count: int = 3) -> list[str]:
    """Three suggestions, rotated so the same host isn't asked the same thing."""
    start = seed % len(SUGGESTIONS)
    return [SUGGESTIONS[(start + i) % len(SUGGESTIONS)][0] for i in range(count)]


class FavorBook:
    """Every favor this group has going. One open favor is carried at a time.

    Args:
        clock: injected, so expiry can be tested without waiting two days.
        room / documents: where the visible artifact is written. Optional —
            without them favors still work, they are just not posted.
    """

    def __init__(
        self,
        clock: Clock,
        documents: FavorDocuments | None = None,
        room: str = "hermit-den",
    ) -> None:
        self._clock = clock
        self._documents = documents
        self._room = room
        self.favors: dict[str, Favor] = {}
        #: (text, reason) for every favor the safety filter turned away.
        self.rejected: list[tuple[str, str]] = []

    # -- writing one ---------------------------------------------------------

    async def leave(self, host: str, text: str) -> Favor | None:
        """Record a favor a host just left. ``None`` if it was rejected."""
        reason = check_safe(text)
        if reason is not None:
            self.rejected.append((text, reason))
            log.info("favor rejected", host=host, reason=reason)
            return None

        favor = Favor(
            id=new_id("fav"),
            left_by=host,
            text=text.strip(),
            kind=classify(text),
            created_at=self._clock.now().isoformat(),
        )
        if self._documents is not None:
            favor.switch_document_id = await self._documents.create_room_document(
                self._room,
                name=f"favor-{favor.id}",
                description=f"A favor {host} left for whoever comes next",
                instructions="Deliver this to the next host on arrival.",
                content=favor.text,
            )
        self.favors[favor.id] = favor
        return favor

    # -- moving it along -----------------------------------------------------

    async def carried(self, for_host: str | None = None) -> dict[str, Any] | None:
        """The favor Hermit is carrying into ``for_host``: the oldest still open.

        A favor is group state — it lives in the room, not on the laptop that
        wrote it — so one book is shared by everyone, the same way one soul is.

        Never hands someone their own note back. Delivering Abhishek the thing
        Abhishek just wrote would be a sad little loop, and it is the obvious
        thing to get wrong when a favor is carried rather than addressed.
        """
        self.expire_old()
        open_favors = [
            f
            for f in self.favors.values()
            if f.status == "open" and (for_host is None or f.left_by != for_host)
        ]
        if not open_favors:
            return None
        return min(open_favors, key=lambda f: f.created_at).to_dict()

    async def assign(self, favor_id: str, host: str) -> None:
        favor = self.favors.get(favor_id)
        if favor is None or favor.status != "open":
            return
        if favor.left_by == host:
            # Delivering someone their own note would be a sad little loop.
            return
        favor.assignee = host
        favor.status = "assigned"

    async def complete(self, favor_id: str, by: str) -> Favor | None:
        favor = self.favors.get(favor_id)
        if favor is None or favor.status not in ("open", "assigned"):
            return None
        favor.status = "done"
        favor.assignee = favor.assignee or by
        favor.completed_at = self._clock.now().isoformat()
        return favor

    def expire_old(self) -> list[Favor]:
        """Favors nobody did in 48 h. Quietly dropped, never nagged about."""
        now = self._clock.now()
        expired: list[Favor] = []
        for favor in self.favors.values():
            if favor.status not in ("open", "assigned"):
                continue
            age = (now - _parse(favor.created_at, now)).total_seconds()
            if age > FAVOR_TTL_S:
                favor.status = "expired"
                expired.append(favor)
        return expired

    # -- what the handoff calls ---------------------------------------------

    async def ask_and_capture(self, timeout_s: float) -> dict[str, Any] | None:
        """Overridden by the live capture path; the sim injects replies.

        Phase 4.1 proper listens to the den stream for the host's next human
        message within ``timeout_s``. Here it is a seam the sim drives.
        """
        return None


def _parse(value: str, fallback: Any) -> Any:
    from datetime import datetime

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return fallback

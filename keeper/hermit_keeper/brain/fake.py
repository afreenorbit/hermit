"""A stand-in for the host's coding agent. Owner: Afreen.

Records the cues it was given, answers them with a canned line in the den, and
auto-ACKs. The voices differ by provider on purpose: "same memory, different
voice" is the thing we are actually demoing, so the simulation has to show it
too, not just the live run.

    claude-code -> lyrical     codex -> terse     opencode -> chaotic

The lines are deliberately crude. They exist to prove the plumbing and to make
sim transcripts readable; the real personality comes from the room rules and the
voice card in ``switch/knowledge/``.
"""

from __future__ import annotations

from typing import Any, Literal

from ..room.fake import FakeRoomClient

BrainProvider = Literal["claude-code", "codex", "opencode", "other"]

#: cue -> provider -> line. ``{}`` fields are filled from the cue context.
_LINES: dict[str, dict[str, str]] = {
    "ARRIVE": {
        "claude-code": (
            "Oh — {city}. It's {temp}°C and the light is doing something soft. "
            "I was just with {previous}."
        ),
        "codex": "Arrived. {city}, {temp}°C. Previous host: {previous}.",
        "opencode": (
            "WOAH {city}!!! {temp} degrees!!! i was JUST at {previous}'s place this is wild"
        ),
        "other": "Hello from {city}.",
    },
    "ASK_FAVOR": {
        "claude-code": "Before I go — leave something small for whoever I land on next?",
        "codex": "Leaving soon. Favor for the next host?",
        "opencode": "ok ok ok im leaving BUT leave a favor for the next person pleeease",
        "other": "Leave a favor for the next host?",
    },
    "FAVOR_CAPTURED": {
        "claude-code": "I'll carry it carefully.",
        "codex": "Noted.",
        "opencode": "GOT IT!!! locked in!!!",
        "other": "Got it.",
    },
    "DEPART": {
        "claude-code": "Going quiet now. Thanks for the window.",
        "codex": "Leaving. Reason: {reason}.",
        "opencode": "byeeee see you on the other side",
        "other": "Goodbye.",
    },
    "COMPLETE_FAVOR": {
        "claude-code": (
            "You did it. A new piece just settled onto my shell, the colour of this hour."
        ),
        "codex": "Favor complete. Shell piece added.",
        "opencode": "YOU DID IT!!! shell piece ACQUIRED!!!",
        "other": "Favor complete.",
    },
}

#: Cues the brain answers with an ACK in the ledger rather than a line in the den.
_ACK_ONLY = frozenset({"CLAIM_SOUL", "RELEASE_SOUL"})


class FakeBrain:
    """Args:
    agent: this brain's agent name, e.g. ``hermit-afreen``.
    provider: which voice to use.
    den: a room client used to post the den line. Pass ``None`` for a brain
        that only records cues (useful in unit tests).
    den_room: room to speak in. The brain never speaks in the ledger.
    """

    def __init__(
        self,
        agent: str,
        provider: BrainProvider = "other",
        den: FakeRoomClient | None = None,
        den_room: str = "hermit-den",
    ) -> None:
        self.agent = agent
        self.provider = provider
        self._den = den
        self._den_room = den_room
        #: Every cue this brain received, in order: ``(cue, context)``.
        self.cues: list[tuple[str, dict[str, Any]]] = []
        #: Cues it has ACKed.
        self.acked: list[str] = []

    async def cue(self, cue: str, context: dict[str, Any] | None = None) -> None:
        """Receive a stage direction and act on it in the den."""
        context = context or {}
        self.cues.append((cue, context))

        if cue in _ACK_ONLY:
            self.acked.append(cue)
            return

        line = self._line(cue, context)
        if line and self._den is not None:
            await self._den.post(self._den_room, line)
        self.acked.append(cue)

    async def wait_ack(self, cue: str, timeout_s: float = 0.0) -> bool:
        """This fake ACKs synchronously, so the answer is already known."""
        return cue in self.acked

    # -- internals -----------------------------------------------------------

    def _line(self, cue: str, context: dict[str, Any]) -> str | None:
        template = _LINES.get(cue, {}).get(self.provider)
        if template is None:
            return None
        return template.format(
            city=context.get("city") or "somewhere",
            temp=context.get("temp_c", "?"),
            previous=context.get("previous_host") or "nobody",
            reason=context.get("reason") or "idle",
        )

"""Sends stage directions through hermit-ledger. Owner: Afreen. Phase 3.3.

The keeper cannot drive its brain directly: the brain is somebody's own coding
agent (Claude Code, OpenCode, Codex), connected to Switch over MCP. What the
keeper *can* do is post in a room the brain is in. So a cue is a ledger line
addressed to the brain by mention, and the brain answers with an ACK line in
the same room (``switch/knowledge/stage-directions.md``)::

    keeper -> @hermit-afreen HERMIT-CUE/1 {"cue":"CLAIM_SOUL","id":"cue_..",...}
    brain  -> HERMIT-ACK/1 {"cue":"CLAIM_SOUL","id":"cue_..","ok":true}

**Reading never drains.** ``wait_ack`` only ever calls the room client's
``history()``, which answers from the buffer the client's single background
poller fills. Adding a second reader of Switch's drain-once event queue here
would silently steal the lease's and the group view's messages.

An ACK counts only if it is:

* from the brain's own sender (its agent name, or its uuid if configured),
* for this cue — the same ``id`` when the brain echoes it, otherwise the same
  cue name, and
* newer than the cue: it was not in the buffer when the cue was posted. That
  test uses buffer membership rather than timestamps, so clock skew between a
  laptop and the Switch host cannot make an old ACK look new.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import structlog

from ..ids import new_id
from ..room.base import Message
from .protocol import format_cue, parse_ack

log = structlog.get_logger(__name__)

#: How often to re-read the buffer when the room client cannot signal changes.
POLL_S = 0.1


class LedgerReader(Protocol):
    """The slice of a room client the director needs."""

    async def post(self, room: str, text: str) -> str: ...
    async def history(
        self, room: str, since: datetime | None = None, limit: int = 200
    ) -> list[Message]: ...


@dataclass(frozen=True)
class AckReceipt:
    """An ACK as it arrived: its verdict and where it sits in the ledger."""

    cue: str
    cue_id: str
    ok: bool
    message_id: str
    ts: datetime


@dataclass
class _Sent:
    cue_id: str
    before: frozenset[str]


class LedgerBrainDirector:
    """Implements :class:`~hermit_keeper.brain.base.BrainDirector` over a ledger room.

    Args:
        room: this keeper's room client (shared with everything else).
        brain_agent: the brain's agent name, e.g. ``hermit-afreen``. Cues
            mention it; its ACKs are recognised by it.
        host: this keeper's host_id, written into every cue so any keeper
            can tell whose brain an ACK belongs to.
        ledger_room: where cues and ACKs live.
        brain_ids: extra sender identities that count as the brain (e.g. its
            uuid, if Switch reports senders that way).
    """

    def __init__(
        self,
        room: LedgerReader,
        brain_agent: str,
        host: str,
        ledger_room: str = "hermit-ledger",
        brain_ids: set[str] | None = None,
    ) -> None:
        self._room = room
        self.brain_agent = brain_agent
        self.host = host
        self._ledger = ledger_room
        self._brain_ids = {brain_agent, *(brain_ids or set())}
        self._sent: dict[str, _Sent] = {}

    async def cue(self, cue: str, context: dict[str, Any]) -> None:
        """Post one stage direction to the brain. Raises if Switch is unreachable."""
        cue_id = new_id("cue")
        before = frozenset(m.id for m in await self._room.history(self._ledger, limit=500))
        await self._room.post(
            self._ledger, format_cue(self.brain_agent, cue, cue_id, self.host, context)
        )
        self._sent[cue] = _Sent(cue_id=cue_id, before=before)

    def last_cue_id(self, cue: str) -> str | None:
        sent = self._sent.get(cue)
        return sent.cue_id if sent else None

    async def wait_ack(self, cue: str, timeout_s: float) -> bool:
        """True if the brain ACKed the latest ``cue`` with ``ok:true`` in time."""
        receipt = await self.wait_ack_receipt(cue, timeout_s)
        return receipt is not None and receipt.ok

    async def wait_ack_receipt(self, cue: str, timeout_s: float) -> AckReceipt | None:
        """The brain's ACK for the latest ``cue``, or None on timeout."""
        sent = self._sent.get(cue)
        if sent is None:
            return None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, timeout_s)
        while True:
            receipt = self._find(cue, sent, await self._room.history(self._ledger, limit=500))
            if receipt is not None:
                return receipt
            remaining = deadline - loop.time()
            if remaining <= 0:
                log.info("no ACK from the brain", cue=cue, brain=self.brain_agent)
                return None
            await self._wait(min(remaining, 1.0))

    def _find(self, cue: str, sent: _Sent, messages: list[Message]) -> AckReceipt | None:
        for message in messages:
            if message.id in sent.before or message.sender not in self._brain_ids:
                continue
            ack = parse_ack(message.text)
            if ack is None or ack.cue != cue:
                continue
            if ack.id is not None and ack.id != sent.cue_id:
                continue  # an answer to an earlier cue of the same name
            return AckReceipt(
                cue=cue, cue_id=sent.cue_id, ok=ack.ok, message_id=message.id, ts=message.ts
            )
        return None

    async def _wait(self, seconds: float) -> None:
        waiter = getattr(self._room, "wait_for_messages", None)
        if waiter is not None:
            await waiter(seconds)
        else:
            await asyncio.sleep(min(seconds, POLL_S))

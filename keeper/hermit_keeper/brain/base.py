"""BrainDirector — how a keeper cues its own coding agent. Owner: A.

Cues go to ``hermit-ledger`` as ``HERMIT-CUE/1 {...}`` addressed to the brain by
mention. The brain speaks only in ``hermit-den``, never in the ledger.
"""

from __future__ import annotations

from typing import Any, Protocol


class BrainDirector(Protocol):
    async def cue(self, cue: str, context: dict[str, Any]) -> None: ...
    async def wait_ack(self, cue: str, timeout_s: float) -> bool: ...

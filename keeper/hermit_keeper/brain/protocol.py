"""The two ledger line shapes a keeper and its brain exchange. Owner: Afreen.

Spec: ``switch/knowledge/stage-directions.md``. A keeper cues its own brain::

    @hermit-afreen HERMIT-CUE/1 {"cue":"CLAIM_SOUL","id":"cue_...","host":"afreen","context":{}}

and the brain acknowledges in the same room::

    HERMIT-ACK/1 {"cue":"CLAIM_SOUL","id":"cue_...","ok":true}

``id`` lets an ACK be matched to the exact cue it answers, and ``host`` lets
*every* keeper attribute a brain's ACK to a laptop without knowing anyone's
agent names. Both are additive: a brain that forgets to echo ``id`` is still
understood, just matched less precisely.

Parsing is deliberately forgiving about what surrounds the JSON (a brain may
prefix a mention or append a full stop) and strict about the JSON itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

CUE_TAG = "HERMIT-CUE/1 "
ACK_TAG = "HERMIT-ACK/1 "


@dataclass(frozen=True)
class Cue:
    cue: str
    id: str | None
    host: str | None
    #: The agent the cue was addressed to, from the leading ``@mention``.
    to: str | None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Ack:
    cue: str
    ok: bool
    id: str | None


def format_cue(to: str, cue: str, cue_id: str, host: str, context: dict[str, Any]) -> str:
    body = {"cue": cue, "id": cue_id, "host": host, "context": context}
    return f"@{to} {CUE_TAG}{json.dumps(body, separators=(',', ':'), default=str)}"


def format_ack(cue: str, ok: bool, cue_id: str | None) -> str:
    body: dict[str, Any] = {"cue": cue, "ok": ok}
    if cue_id is not None:
        body["id"] = cue_id
    return ACK_TAG + json.dumps(body, separators=(",", ":"))


def parse_cue(text: str) -> Cue | None:
    payload = _payload(text, CUE_TAG)
    if payload is None or not isinstance(payload.get("cue"), str):
        return None
    head = text[: text.find(CUE_TAG)].strip()
    to = head[1:] if head.startswith("@") and " " not in head else None
    context = payload.get("context")
    return Cue(
        cue=payload["cue"],
        id=_opt_str(payload.get("id")),
        host=_opt_str(payload.get("host")),
        to=to,
        context=context if isinstance(context, dict) else {},
    )


def parse_ack(text: str) -> Ack | None:
    payload = _payload(text, ACK_TAG)
    if payload is None or not isinstance(payload.get("cue"), str):
        return None
    ok = payload.get("ok")
    return Ack(cue=payload["cue"], ok=ok is True, id=_opt_str(payload.get("id")))


def _payload(text: str, tag: str) -> dict[str, Any] | None:
    at = text.find(tag)
    if at < 0:
        return None
    try:
        value, _end = json.JSONDecoder().raw_decode(text[at + len(tag) :].lstrip())
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None

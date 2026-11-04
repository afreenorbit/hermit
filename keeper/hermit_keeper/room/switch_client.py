"""The real Switch room client. Owner: Afreen. Phase 2.5.

**Verified against a running switch-v0.9.0.** Every path and payload here was
exercised: a keeper posted a ledger line to a real Switch room and another
keeper read it back. See docs/switch-facts.md, "Verified against a running
server".

Three things the source alone did not tell us, each of which cost an attempt:

1. **Auth is `Authorization: Bearer <api_key>`** — the agent's own key from
   registration, not the shared registration token. `X-API-Key` is rejected.
2. **`POST /agents/{id}/message` takes `content`, not `body`**, and `room_id`
   is the room's **uuid**, not its name.
3. **Room history does not work for this.** `GET .../rooms/{id}/history`
   returns an empty list even for messages that were provably delivered.
   Agents receive through a **long-polling queue** at
   `GET /agents/{id}/events`, which drains what it hands out.

That last point shapes the whole class. Because the queue is drain-once, this
client owns the only poll and buffers what it reads, so `history()` keeps
working the way the rest of the keeper expects. If two things polled, each
would silently eat events the other needed.

Not here: roles and documents have no HTTP endpoint at all. The keeper learns
the soul holder from the ledger instead.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from .base import Message

log = structlog.get_logger(__name__)

TIMEOUT_S = 15.0
#: The server long-polls; this bounds how long a quiet room blocks us.
POLL_TIMEOUT_S = 25.0
#: Messages kept per room for `history()` to answer from.
BUFFER = 500


class SwitchRoomClient:
    """One agent's view of Switch, over the agent bridge HTTP API.

    Args:
        base_url: the Switch server, e.g. ``http://100.x.y.z:8000``.
        agent_id: this keeper's **registered agent uuid**.
        api_key: that agent's own key, from registration.
        rooms: ``{"hermit-den": "<uuid>", ...}``. Switch addresses rooms by
            uuid; the keeper thinks in names, so the mapping lives here.
    """

    def __init__(
        self,
        base_url: str,
        agent_id: str,
        api_key: str,
        rooms: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self._api_key = api_key
        self._rooms = dict(rooms or {})
        self._ids_to_names = {v: k for k, v in self._rooms.items()}
        self._client = client
        self._buffer: dict[str, list[Message]] = {}
        self._seq = 0
        self._drain_lock = asyncio.Lock()

    # -- plumbing ------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }

    def room_id(self, room: str) -> str:
        """Accept a name or a uuid; Switch only takes the uuid."""
        return self._rooms.get(room, room)

    async def _request(
        self, method: str, path: str, request_timeout: float = TIMEOUT_S, **kw: Any
    ) -> Any:
        url = f"{self.base_url}{path}"
        if self._client is not None:
            response = await self._client.request(
                method, url, headers=self._headers(), timeout=request_timeout, **kw
            )
        else:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method, url, headers=self._headers(), timeout=request_timeout, **kw
                )
        response.raise_for_status()
        text = response.text.strip()
        return json.loads(text) if text else None

    # -- writing -------------------------------------------------------------

    async def post(self, room: str, text: str) -> str:
        """Send a message to a room as this agent."""
        result = await self._request(
            "POST",
            f"/agents/{self.agent_id}/message",
            json={"room_id": self.room_id(room), "content": text},
        )
        return str((result or {}).get("event_id", ""))

    # -- reading -------------------------------------------------------------

    async def drain(self) -> int:
        """Pull pending events into the buffer. Returns how many messages arrived.

        One caller only — the queue hands each event out once, so a second
        poller would quietly steal events this one needed. The lock enforces
        that even if two tasks call it at the same moment.
        """
        async with self._drain_lock:
            try:
                result = await self._request(
                    "GET", f"/agents/{self.agent_id}/events", request_timeout=POLL_TIMEOUT_S
                )
            except httpx.HTTPError:
                log.debug("event poll failed", agent=self.agent_id)
                return 0

            events = (result or {}).get("events", []) if isinstance(result, dict) else []
            added = 0
            for event in events:
                if event.get("type") != "message":
                    continue
                room_uuid = str(event.get("room_id", ""))
                name = self._ids_to_names.get(room_uuid, room_uuid)
                payload = event.get("payload") or {}
                content = payload.get("content") or payload.get("body") or ""
                if not content:
                    continue
                self._seq += 1
                message = Message(
                    id=str(payload.get("event_id") or f"msg_{self._seq:08d}"),
                    room=name,
                    sender=str(payload.get("sender") or ""),
                    text=str(content),
                    ts=_timestamp(payload),
                )
                bucket = self._buffer.setdefault(name, [])
                bucket.append(message)
                del bucket[:-BUFFER]
                added += 1
            return added

    async def history(
        self, room: str, since: datetime | None = None, limit: int = 200
    ) -> list[Message]:
        """Messages this client has seen in a room.

        Answered from the buffer rather than the server: Switch's history
        endpoint returns nothing for agent-posted messages, and the event queue
        is the only path that actually delivers them.

        So a keeper only knows what has happened **since it started**. That is
        fine for the group view, where heartbeats arrive every few seconds, but
        it means a keeper cannot rebuild the whole journey from a cold start —
        `export_journey.py` reads the local journal for that.
        """
        await self.drain()
        messages = self._buffer.get(room, [])
        if since is not None:
            messages = [m for m in messages if m.ts > since]
        return list(messages[-limit:])

    def stream(self, room: str) -> AsyncIterator[Message]:
        """Live messages, by repeatedly draining the queue."""

        async def _stream() -> AsyncIterator[Message]:
            cursor = datetime.now(UTC)
            while True:
                for message in await self.history(room, since=cursor, limit=50):
                    cursor = message.ts
                    yield message
                await asyncio.sleep(1.0)

        return _stream()

    # -- what Switch does not expose over HTTP -------------------------------

    async def list_roles(self, room: str) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "No roles endpoint exists over HTTP - verified against the live "
            "server's /openapi.json. Read the holder from the ledger instead."
        )

    async def create_room_document(
        self, room: str, name: str, description: str, instructions: str, content: str
    ) -> str:
        raise NotImplementedError(
            "No documents endpoint over HTTP either. A favor's visible artifact "
            "is a message the brain posts in the den; its state lives in the ledger."
        )

    async def create_task(self, room: str, title: str, body: str, assignee: str | None) -> str:
        raise NotImplementedError(
            "Tasks ARE exposed over HTTP, but a Task needs a performer agent up "
            "front and a carried favor has none. See docs/switch-facts.md SP5."
        )


def _timestamp(payload: dict[str, Any]) -> datetime:
    raw = payload.get("timestamp")
    if isinstance(raw, int | float):
        # Switch sends milliseconds since the epoch.
        return datetime.fromtimestamp(raw / 1000.0, tz=UTC)
    return datetime.now(UTC)


def describe_handshake() -> str:
    """What is settled and what still is not. Printed by `check --switch`."""
    return json.dumps(
        {
            "verified_against_switch_v0_9_0": [
                "auth: Authorization: Bearer <agent api_key>",
                "register: POST /agents -> {id, api_key}",
                "send: POST /agents/{id}/message {room_id(uuid), content}",
                "receive: GET /agents/{id}/events - long-poll, drains once",
                "create rooms: POST /agents/{id}/moderation/rooms",
                "room history endpoint returns nothing for agent messages",
                "NO roles endpoint over HTTP - holder comes from the ledger",
                "NO documents endpoint over HTTP",
            ],
            "still_open": [
                "measured lease expiry delay after a disconnect",
                "a brain assuming the soul role over MCP (Step 2)",
                "Discord bridge setup",
            ],
        },
        indent=2,
    )

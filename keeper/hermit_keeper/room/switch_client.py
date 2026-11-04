"""The real Switch room client. Owner: Afreen. Phase 2.5.

Speaks to Switch Core's agent bridge over HTTP as a registered agent, so the
keeper sits in the same rooms as the coding agents. Shapes come from the Switch
source, cited in `docs/switch-facts.md`.

⚠ **Unverified against a live server.** Every call here is written from reading
`core/switch_core/bridges/agent/`, which settles the semantics but not the
handshake: registration, auth headers and the exact response envelopes need one
session against a running Switch before this can be trusted. Until then
`lease_strategy = "fake"` is the honest default and `sim live` is the way to
exercise three keepers.

What is already settled (switch-facts SP2/SP4): a role can only be assumed by
the agent's own session, so this client never claims the soul. It reads who
holds it with `list_roles`, and `AgentInstructedLease` cues the brain to take
it. The keeper is a room member that writes the ledger and watches.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx
import structlog

from .base import Message

log = structlog.get_logger(__name__)

TIMEOUT_S = 10.0


class SwitchRoomClient:
    """One agent's view of Switch, over the agent bridge HTTP API.

    Args:
        base_url: the Switch server, e.g. ``http://100.x.y.z:8080``.
        agent_id: this keeper's registered agent, ``keeper-<host>``.
        token: bearer token, read from the env var named in the host config.
        client: injectable for tests (``respx``).
    """

    def __init__(
        self,
        base_url: str,
        agent_id: str,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self._token = token
        self._client = client
        self._rooms: dict[str, str] = {}

    # -- plumbing ------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self._token:
            headers["authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        if self._client is not None:
            response = await self._client.request(
                method, url, headers=self._headers(), timeout=TIMEOUT_S, **kwargs
            )
        else:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method, url, headers=self._headers(), timeout=TIMEOUT_S, **kwargs
                )
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()

    # -- messages ------------------------------------------------------------

    async def post(self, room: str, text: str) -> str:
        """Send a message to a room as this agent."""
        body = {"room": room, "body": text}
        result = await self._request("POST", f"/agents/{self.agent_id}/message", json=body)
        return str((result or {}).get("id", ""))

    async def history(
        self, room: str, since: datetime | None = None, limit: int = 200
    ) -> list[Message]:
        """Recent messages, oldest first.

        ``since`` is how the keeper tails the ledger without re-reading it all;
        the server is asked to filter so a long-running group does not pull a
        day of lines every few seconds.
        """
        params: dict[str, str] = {"room": room, "limit": str(limit)}
        if since is not None:
            params["since"] = since.isoformat()
        result = await self._request("GET", f"/agents/{self.agent_id}/messages", params=params)
        return [_message(row, room) for row in (result or {}).get("messages", [])]

    def stream(self, room: str) -> AsyncIterator[Message]:
        """Live messages over SSE.

        Falls back to polling `history` if the stream drops: a keeper that
        stops hearing the room is a keeper that stops handing Hermit on, so a
        slower path is much better than no path.
        """

        async def _stream() -> AsyncIterator[Message]:
            cursor: datetime | None = None
            while True:
                try:
                    for message in await self.history(room, since=cursor, limit=50):
                        cursor = message.ts
                        yield message
                except httpx.HTTPError:
                    log.debug("room stream hiccup", room=room)
                await asyncio.sleep(3.0)

        return _stream()

    # -- roles (read-only: see switch-facts SP2) -----------------------------

    async def list_roles(self, room: str) -> list[dict[str, Any]]:
        """Roles in a room, each with ``held_by``.

        This is how the keeper learns who holds the soul. It cannot *take* the
        role — only the holding agent's own session can do that.
        """
        result = await self._request("GET", f"/agents/{self.agent_id}/rooms/{room}/roles")
        if isinstance(result, list):
            return result
        return list((result or {}).get("roles", []))

    # -- favors live as room documents (switch-facts SP5) --------------------

    async def create_room_document(
        self, room: str, name: str, description: str, instructions: str, content: str
    ) -> str:
        body = {
            "room": room,
            "name": name,
            "description": description,
            "instructions": instructions,
            "content": content,
        }
        result = await self._request("POST", f"/agents/{self.agent_id}/documents", json=body)
        return str((result or {}).get("document_id", ""))

    # -- the Task API is deliberately not used -------------------------------

    async def create_task(self, room: str, title: str, body: str, assignee: str | None) -> str:
        raise NotImplementedError(
            "Switch Tasks need a performer agent up front and a favor has none "
            "by definition - see docs/switch-facts.md SP5. Use "
            "create_room_document instead."
        )


def _message(row: dict[str, Any], room: str) -> Message:
    ts = row.get("ts") or row.get("created_at") or ""
    try:
        when = datetime.fromisoformat(str(ts))
    except ValueError:
        when = datetime.now().astimezone()
    return Message(
        id=str(row.get("id", "")),
        room=str(row.get("room", room)),
        sender=str(row.get("sender") or row.get("agent_id") or ""),
        text=str(row.get("body") or row.get("text") or ""),
        ts=when,
    )


def describe_handshake() -> str:
    """What a human must confirm before this client can be trusted.

    Printed by `hermit-keeper check` so the unknowns are visible rather than
    discovered at 2am on the night of the pilot.
    """
    return json.dumps(
        {
            "verified_from_source": [
                "roles are assumed only by the holding agent's own session (SP2)",
                "a lease auto-releases shortly after that session disconnects (SP3)",
                "list_roles().held_by names the live holder (SP4)",
                "room Tasks cannot hold a favor; documents can (SP5)",
            ],
            "needs_a_live_server": [
                "agent registration and the auth header",
                "exact paths for message / messages / roles / documents",
                "SSE endpoint for room streaming",
                "measured lease expiry delay after a disconnect",
            ],
        },
        indent=2,
    )

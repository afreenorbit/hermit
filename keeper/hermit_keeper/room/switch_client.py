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
client owns **the only poll** — one background task per client — and buffers
what it reads. Everything else (`history()`, the brain director, the soul
lease) reads that buffer and never touches the queue. If two things polled,
each would silently eat events the other needed.

**Own messages.** Whether Switch hands an agent its *own* posts back on
`/events` is not yet verified. This client is correct either way: a successful
post is echoed into the local buffer at once under the server's `event_id`,
and if the server later delivers the same `event_id` the copy replaces the
echo's timestamp instead of being added twice.

**Online / offline.** The poller is also the connectivity probe. A connection
error or a 5xx marks the client offline; the next successful poll marks it
online again and resets `listening_since`, which the soul lease uses so that
"I heard nothing while I was deaf" is never mistaken for "they went silent".

Not here: roles and documents have no HTTP endpoint at all. The keeper learns
the soul holder from the ledger instead (`lease/agent_instructed.py`).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from .base import Message

log = structlog.get_logger(__name__)

TIMEOUT_S = 15.0
#: The server long-polls; this bounds how long one quiet poll may block. A read
#: timeout on a long-poll is *not* an outage, just an empty answer.
POLL_TIMEOUT_S = 25.0
#: First retry delay after a failed poll; doubles up to ``MAX_RETRY_S``.
RETRY_S = 1.0
MAX_RETRY_S = 5.0
#: Messages kept per room for `history()` to answer from.
BUFFER = 500


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SwitchRoomClient:
    """One agent's view of Switch, over the agent bridge HTTP API.

    Args:
        base_url: the Switch server, e.g. ``http://100.x.y.z:8000``.
        agent_id: this keeper's **registered agent uuid**.
        api_key: that agent's own key, from registration.
        rooms: ``{"hermit-den": "<uuid>", ...}``. Switch addresses rooms by
            uuid; the keeper thinks in names, so the mapping lives here.
        client: a shared ``httpx.AsyncClient``. Strongly preferred: the
            production builder passes one and closes it on shutdown.
        agent_name: what this agent is called in the room (``keeper-<host>``),
            used as the sender of locally echoed posts.
    """

    def __init__(
        self,
        base_url: str,
        agent_id: str,
        api_key: str,
        rooms: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        *,
        agent_name: str | None = None,
        poll_timeout_s: float = POLL_TIMEOUT_S,
        retry_s: float = RETRY_S,
        max_retry_s: float = MAX_RETRY_S,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.agent_name = agent_name or agent_id
        self._api_key = api_key
        self._rooms = dict(rooms or {})
        self._ids_to_names = {v: k for k, v in self._rooms.items()}
        self._client = client
        self._poll_timeout_s = poll_timeout_s
        self._retry_s = retry_s
        self._max_retry_s = max_retry_s
        self._now = now

        self._buffer: dict[str, list[Message]] = {}
        self._by_id: dict[str, Message] = {}
        self._seq = 0
        self._drain_lock = asyncio.Lock()
        self._poller: asyncio.Task[None] | None = None
        self._changed = asyncio.Event()

        #: True once a poll has succeeded and none has failed since.
        self.online = False
        #: When the current unbroken stretch of successful polling began.
        self.listening_since: datetime | None = None
        #: Why the last request failed, for `check --switch` and the logs.
        self.last_error: str | None = None
        #: How many own posts the server later handed back on `/events`.
        self.own_echoes_from_server = 0

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

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start the single background poller. Idempotent; needs a running loop."""
        if self._poller is None or self._poller.done():
            self._poller = asyncio.create_task(self._poll_forever())

    async def aclose(self) -> None:
        """Stop polling. Does not close a shared ``httpx.AsyncClient``."""
        if self._poller is not None:
            self._poller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poller
            self._poller = None
        self._mark_offline("closed")

    async def _poll_forever(self) -> None:
        delay = self._retry_s
        while True:
            try:
                await self.drain()
            except httpx.ReadTimeout:
                # A long-poll that outlived our timeout: the server accepted
                # the request and simply had nothing to say. Not an outage —
                # and we were listening the whole time.
                self._mark_online()
                delay = self._retry_s
                continue
            except (httpx.HTTPError, ValueError) as exc:
                self._mark_offline(_describe(exc))
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_retry_s)
                continue
            delay = self._retry_s

    def _mark_online(self) -> None:
        if not self.online:
            self.online = True
            self.listening_since = self._now()
            self.last_error = None
            log.info("switch reachable", agent=self.agent_name)

    def _mark_offline(self, why: str) -> None:
        if self.online:
            log.warning("switch unreachable", agent=self.agent_name, error=why)
        self.online = False
        self.listening_since = None
        self.last_error = why
        self._notify()

    def _notify(self) -> None:
        self._changed.set()
        self._changed = asyncio.Event()

    async def wait_for_messages(self, timeout_s: float) -> None:
        """Return when the buffer changes (or the connection state does), or on timeout."""
        self.start()
        changed = self._changed
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(max(0.0, timeout_s)):
                await changed.wait()

    # -- writing -------------------------------------------------------------

    async def post(self, room: str, text: str) -> str:
        """Send a message to a room as this agent, and echo it locally."""
        self.start()
        result = await self._request(
            "POST",
            f"/agents/{self.agent_id}/message",
            json={"room_id": self.room_id(room), "content": text},
        )
        event_id = str((result or {}).get("event_id", "")) if isinstance(result, dict) else ""
        if event_id in self._by_id:
            return event_id  # the server already handed it back
        self._seq += 1
        self._remember(
            Message(
                id=event_id or f"local_{self._seq:08d}",
                room=self._ids_to_names.get(self.room_id(room), room),
                sender=self.agent_name,
                text=text,
                ts=self._now(),
            )
        )
        return event_id

    # -- reading -------------------------------------------------------------

    async def drain(self) -> int:
        """One long-poll of the queue into the buffer. Returns messages added.

        Called by the background poller. One caller only — the queue hands
        each event out once — and the lock enforces that even if a test calls
        it directly while the poller runs. Raises on transport errors so the
        poller can mark the connection offline.
        """
        async with self._drain_lock:
            result = await self._request(
                "GET", f"/agents/{self.agent_id}/events", request_timeout=self._poll_timeout_s
            )
            self._mark_online()
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
                event_id = str(payload.get("event_id") or payload.get("message_id") or "")
                ts = _timestamp(payload, self._now)
                if event_id and event_id in self._by_id:
                    # Our own post, handed back by the server: adopt the
                    # server's timestamp so every keeper orders it the same.
                    self._by_id[event_id].ts = ts
                    self.own_echoes_from_server += 1
                    continue
                self._seq += 1
                self._remember(
                    Message(
                        id=event_id or f"msg_{self._seq:08d}",
                        room=name,
                        sender=str(payload.get("sender") or ""),
                        text=str(content),
                        ts=ts,
                    )
                )
                added += 1
            if added:
                self._notify()
            return added

    def _remember(self, message: Message) -> None:
        bucket = self._buffer.setdefault(message.room, [])
        bucket.append(message)
        self._by_id[message.id] = message
        for dropped in bucket[:-BUFFER]:
            self._by_id.pop(dropped.id, None)
        del bucket[:-BUFFER]
        self._notify()

    async def history(
        self, room: str, since: datetime | None = None, limit: int = 200
    ) -> list[Message]:
        """Messages this client has seen in a room, in arrival order.

        Answered from the buffer rather than the server: Switch's history
        endpoint returns nothing for agent-posted messages, and the event queue
        is the only path that actually delivers them. Never blocks on the
        network.

        So a keeper only knows what has happened **since it started**. That is
        fine for the group view and the soul lease, where heartbeats arrive
        every few seconds, but it means a keeper cannot rebuild the whole
        journey from a cold start — `export_journey.py` reads the local
        journal for that.
        """
        self.start()
        messages = self._buffer.get(room, [])
        if since is not None:
            messages = [m for m in messages if m.ts > since]
        return list(messages[-limit:])

    def stream(self, room: str) -> AsyncIterator[Message]:
        """Live messages from now on, read from the buffer."""

        async def _stream() -> AsyncIterator[Message]:
            seen = {m.id for m in await self.history(room, limit=BUFFER)}
            while True:
                await self.wait_for_messages(1.0)
                for message in await self.history(room, limit=BUFFER):
                    if message.id not in seen:
                        seen.add(message.id)
                        yield message

        return _stream()

    # -- tasks: exposed by Switch, but not what a favor is -------------------

    async def create_task(self, room: str, title: str, body: str, assignee: str | None) -> str:
        raise NotImplementedError(_NO_TASKS)

    async def assign_task(self, task_id: str, assignee: str) -> None:
        raise NotImplementedError(_NO_TASKS)

    async def complete_task(self, task_id: str) -> None:
        raise NotImplementedError(_NO_TASKS)

    async def list_tasks(self, room: str, status: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError(_NO_TASKS)


_NO_TASKS = (
    "Tasks ARE exposed over HTTP, but a Task needs a performer agent up front and a "
    "carried favor has none. Favors live in the ledger. See docs/switch-facts.md SP5."
)


def _timestamp(payload: dict[str, Any], now: Callable[[], datetime]) -> datetime:
    raw = payload.get("timestamp")
    if isinstance(raw, int | float):
        # Switch sends milliseconds since the epoch.
        return datetime.fromtimestamp(raw / 1000.0, tz=UTC)
    return now()


def _describe(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code} from {exc.request.url.path}"
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__


# -- check --switch ------------------------------------------------------------


async def probe(
    base_url: str,
    agent_id: str | None,
    api_key: str | None,
    ledger_room_id: str | None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """What can be proved from this laptop right now, without side effects.

    1. ``GET /health`` — is the server there at all.
    2. ``GET /agents/{id}/rooms/{ledger}/history`` with the agent key — proves
       the key, the agent uuid and the ledger room uuid together. This
       endpoint is used because it is authenticated and does **not** drain the
       event queue; `/events` would steal a running keeper's messages.

    Never prints or returns the key.
    """
    own = client is None
    http = client or httpx.AsyncClient()
    verified: list[str] = []
    failed: list[str] = []
    base = base_url.rstrip("/")
    try:
        try:
            response = await http.get(f"{base}/health", timeout=5.0)
            if response.is_success:
                verified.append(f"server reachable: GET {base}/health -> {response.status_code}")
            else:
                failed.append(f"GET {base}/health -> HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            failed.append(f"server unreachable at {base}: {_describe(exc)}")

        if not failed:
            if not api_key:
                failed.append("no agent api_key in the environment (see switch.token_env)")
            elif not agent_id:
                failed.append("switch.agent_id is not set in the config")
            elif not ledger_room_id:
                failed.append("switch.rooms has no uuid for the ledger room")
            else:
                path = f"/agents/{agent_id}/rooms/{ledger_room_id}/history"
                try:
                    response = await http.get(
                        f"{base}{path}",
                        headers={"authorization": f"Bearer {api_key}"},
                        timeout=10.0,
                    )
                    if response.is_success:
                        verified.append(
                            "agent key, agent uuid and ledger room uuid accepted "
                            f"(GET {path} -> {response.status_code})"
                        )
                    elif response.status_code in (401, 403):
                        failed.append(f"agent key rejected (HTTP {response.status_code})")
                    else:
                        failed.append(
                            f"authenticated call failed: GET {path} -> HTTP "
                            f"{response.status_code} (wrong agent or room uuid?)"
                        )
                except httpx.HTTPError as exc:
                    failed.append(f"authenticated call failed: {_describe(exc)}")
    finally:
        if own:
            await http.aclose()

    return {
        "ok": not failed,
        "verified_now": verified,
        "failed_now": failed,
        "not_checkable_over_http": [
            "that the exclusive 'soul' role exists in the den (roles are MCP-only)",
            "that your brain is connected and follows stage-directions.md",
            "the real lease expiry after a lid slam (switch.lease_expiry_s is a guess)",
        ],
    }


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
            "proven_only_against_the_sim_stand_in": [
                "the full keeper path: cue -> brain ACK -> ledger-observed holder",
                "one holder across simultaneous claim races",
                "lid slam -> expiry -> another host claims, recorded abrupt",
                "Switch outage -> keepers report offline, then recover",
            ],
            "still_open": [
                "the moderation/rooms request body bootstrap_rooms.py sends (not "
                "recorded from the live run; the script prints the server's reply)",
                "whether /events hands an agent its own posts (client works either way)",
                "whether message senders are agent names or uuids (brain_agent_id covers uuids)",
                "measured lease expiry delay after a disconnect",
                "a real brain assuming the soul role over MCP (Step 2)",
                "Discord bridge setup",
            ],
        },
        indent=2,
    )

"""A STAND-IN for Switch. **This is not Switch.** Owner: Afreen.

It exists so the keeper's real Switch code path — real HTTP, real long-polls,
the real ``SwitchRoomClient`` — can be exercised end to end on one machine,
in CI, with no server and no coding agents. It implements **only** the surface
verified against a running switch-v0.9.0 (docs/switch-facts.md, "Verified
against a running server"), and nothing the keeper is not allowed to rely on:

    GET  /health
    POST /agents                                  register   (registration token)
    POST /agents/{id}/message                     send       {room_id, content}
    GET  /agents/{id}/events                      long-poll, drains once
    GET  /agents/{id}/rooms/{room_id}/history     returns nothing, as the real one does
    POST /agents/{id}/moderation/rooms            create a room (body shape is a guess)

Auth is ``Authorization: Bearer <key>``; ``X-Agent-Token`` is rejected.

Things this stand-in has to *choose* because the real server's behaviour is
not yet measured, each a constructor knob so tests can cover both answers:

* ``echo_own`` — whether ``/events`` hands an agent its own posts.
* ``long_poll_s`` — how long an empty ``/events`` poll is held open.
* ``role_expiry_s`` — how long after a session disconnects its role frees.

There is deliberately **no roles endpoint**: roles live in :class:`RoleRegistry`,
reachable only in-process by :class:`StandinBrain`, which is how a real coding
agent reaches ``assume_role`` — over MCP, never over this HTTP API.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from hermit_keeper.brain.protocol import format_ack, parse_cue

DEFAULT_REGISTRATION_TOKEN = "standin-registration-token"


# -- the MCP-only half: exclusive roles with session leases -------------------


class RoleError(Exception):
    """What ``assume_role`` raises when exclusivity says no."""


@dataclass
class Session:
    """One brain's live connection. The lease follows this, not the agent."""

    agent: str
    connected: bool = True
    disconnected_at: float | None = None


@dataclass
class _Lease:
    session: Session
    role: str


class RoleRegistry:
    """In-process stand-in for Switch's exclusive roles (switch-facts SP1-SP4).

    * an exclusive role has at most one live holder;
    * an agent may hold one role at a time;
    * a lease is held by the **session** that assumed it and frees
      ``expiry_s`` after that session disconnects.
    """

    def __init__(self, expiry_s: float = 8.0, now: Callable[[], float] = time.monotonic) -> None:
        self.expiry_s = expiry_s
        self._now = now
        self._exclusive: set[tuple[str, str]] = set()
        self._leases: dict[tuple[str, str], list[_Lease]] = {}
        #: (when, room, role, holder-or-None) on every change. For assertions.
        self.history: list[tuple[float, str, str, str | None]] = []

    def define_role(self, room: str, role: str, exclusive: bool = True) -> None:
        if exclusive:
            self._exclusive.add((room, role))
        self._leases.setdefault((room, role), [])

    def _live(self, lease: _Lease) -> bool:
        s = lease.session
        if s.connected:
            return True
        return s.disconnected_at is not None and self._now() - s.disconnected_at < self.expiry_s

    def holders(self, room: str, role: str) -> list[str]:
        leases = self._leases.get((room, role), [])
        alive = [lease for lease in leases if self._live(lease)]
        if len(alive) != len(leases):
            self._leases[(room, role)] = alive
            if not alive:
                self.history.append((self._now(), room, role, None))
        return [lease.session.agent for lease in alive]

    def held_by(self, session: Session) -> str | None:
        for (_room, role), leases in self._leases.items():
            if any(lease.session is session and self._live(lease) for lease in leases):
                return role
        return None

    def assume_role(self, session: Session, room: str, role: str) -> dict[str, str]:
        if (room, role) not in self._leases:
            raise RoleError(f"no role {role!r} in {room}")
        if not session.connected:
            raise RoleError("session is not connected")
        if self.held_by(session) is not None:
            raise RoleError("you already hold a role (release it first)")
        if (room, role) in self._exclusive and self.holders(room, role):
            raise RoleError(f"{role!r} is exclusive and already held")
        self._leases[(room, role)].append(_Lease(session, role))
        self.history.append((self._now(), room, role, session.agent))
        return {"role": role, "instructions": "You are Hermit. (stand-in instructions)"}

    def release_role(self, session: Session) -> None:
        for (room, role), leases in self._leases.items():
            kept = [lease for lease in leases if lease.session is not session]
            if len(kept) != len(leases):
                self._leases[(room, role)] = kept
                self.history.append((self._now(), room, role, None))


# -- the HTTP half -------------------------------------------------------------


@dataclass
class _Agent:
    id: str
    name: str
    api_key: str
    queue: deque[dict[str, Any]] = field(default_factory=deque)
    wake: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass
class _Room:
    id: str
    name: str
    members: set[str] = field(default_factory=set)


class StandinSwitch:
    """The stand-in server's state and its FastAPI app (``.app``)."""

    def __init__(
        self,
        *,
        registration_token: str = DEFAULT_REGISTRATION_TOKEN,
        echo_own: bool = False,
        long_poll_s: float = 20.0,
        role_expiry_s: float = 8.0,
    ) -> None:
        self.registration_token = registration_token
        self.echo_own = echo_own
        self.long_poll_s = long_poll_s
        self.agents: dict[str, _Agent] = {}
        self.rooms: dict[str, _Room] = {}
        self.roles = RoleRegistry(expiry_s=role_expiry_s)
        #: When True every request gets a 503, as if the server were gone.
        self.down = False
        self.app = self._build_app()

    # -- in-process helpers (tests, sim) -------------------------------------

    def register(self, name: str) -> tuple[str, str]:
        agent = _Agent(id=str(uuid.uuid4()), name=name, api_key=secrets.token_urlsafe(24))
        self.agents[agent.id] = agent
        return agent.id, agent.api_key

    def create_room(self, name: str, member_ids: list[str]) -> str:
        room = _Room(id=str(uuid.uuid4()), name=name, members=set(member_ids))
        self.rooms[room.id] = room
        return room.id

    def room_named(self, name: str) -> _Room | None:
        return next((r for r in self.rooms.values() if r.name == name), None)

    def set_down(self, down: bool) -> None:
        self.down = down
        for agent in self.agents.values():
            agent.wake.set()  # end every held long-poll now

    # -- the app -------------------------------------------------------------

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="Switch STAND-IN (not Switch)")

        @app.middleware("http")
        async def outage(request: Request, call_next: Any) -> Any:
            if self.down:
                return JSONResponse({"detail": "stand-in is down"}, status_code=503)
            return await call_next(request)

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok", "server": "switch-standin"}

        @app.post("/agents")
        async def register(request: Request) -> Any:
            if _bearer(request) != self.registration_token:
                return _deny(401, "registration token required")
            body = await _json(request)
            name = body.get("name") if isinstance(body, dict) else None
            if not isinstance(name, str) or not name:
                return _deny(422, "name is required")
            agent_id, api_key = self.register(name)
            return {"id": agent_id, "api_key": api_key}

        @app.post("/agents/{agent_id}/message")
        async def message(agent_id: str, request: Request) -> Any:
            agent = self._auth(agent_id, request)
            if isinstance(agent, JSONResponse):
                return agent
            body = await _json(request)
            if not isinstance(body, dict):
                return _deny(422, "json body required")
            room = self.rooms.get(str(body.get("room_id", "")))
            content = body.get("content")
            if room is None:
                return _deny(404, "room_id must be a room uuid")
            if not isinstance(content, str) or not content:
                return _deny(422, "content is required")
            if agent.id not in room.members:
                return _deny(403, "not a member of this room")
            event_id = f"$ev_{uuid.uuid4().hex}"
            event = {
                "type": "message",
                "room_id": room.id,
                "payload": {
                    "event_id": event_id,
                    "sender": agent.name,
                    "content": content,
                    "timestamp": int(time.time() * 1000),
                },
            }
            for member_id in room.members:
                if member_id == agent.id and not self.echo_own:
                    continue
                member = self.agents.get(member_id)
                if member is not None:
                    member.queue.append(event)
                    member.wake.set()
            return {"event_id": event_id}

        @app.get("/agents/{agent_id}/events")
        async def events(agent_id: str, request: Request) -> Any:
            agent = self._auth(agent_id, request)
            if isinstance(agent, JSONResponse):
                return agent
            if not agent.queue:
                agent.wake.clear()
                with contextlib.suppress(TimeoutError):
                    async with asyncio.timeout(self.long_poll_s):
                        await agent.wake.wait()
            if self.down:
                return JSONResponse({"detail": "stand-in is down"}, status_code=503)
            drained = list(agent.queue)
            agent.queue.clear()
            return {"events": drained}

        @app.get("/agents/{agent_id}/rooms/{room_id}/history")
        async def history(agent_id: str, room_id: str, request: Request) -> Any:
            agent = self._auth(agent_id, request)
            if isinstance(agent, JSONResponse):
                return agent
            if room_id not in self.rooms:
                return _deny(404, "unknown room")
            # Faithful to switch-v0.9.0: agent messages never show up here.
            return []

        @app.post("/agents/{agent_id}/moderation/rooms")
        async def create_room(agent_id: str, request: Request) -> Any:
            agent = self._auth(agent_id, request)
            if isinstance(agent, JSONResponse):
                return agent
            body = await _json(request)
            if not isinstance(body, dict) or not isinstance(body.get("name"), str):
                return _deny(422, "name is required")
            members = [agent.id] + [
                str(m) for m in body.get("agent_ids") or [] if str(m) in self.agents
            ]
            room_id = self.create_room(body["name"], members)
            return {"id": room_id, "name": body["name"]}

        return app

    def _auth(self, agent_id: str, request: Request) -> _Agent | JSONResponse:
        if request.headers.get("x-agent-token"):
            return _deny(401, "X-Agent-Token is not accepted; use Authorization: Bearer")
        agent = self.agents.get(agent_id)
        if agent is None:
            return _deny(404, "unknown agent")
        if not secrets.compare_digest(_bearer(request), agent.api_key):
            return _deny(401, "bad agent key")
        return agent


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    return header[7:] if header.lower().startswith("bearer ") else ""


async def _json(request: Request) -> Any:
    try:
        return await request.json()
    except ValueError:
        return None


def _deny(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


@contextlib.asynccontextmanager
async def serve_standin(switch: StandinSwitch, port: int = 0) -> AsyncIterator[str]:
    """Run the stand-in on a real loopback socket; yields its base URL."""
    config = uvicorn.Config(
        switch.app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="off",
        timeout_graceful_shutdown=1,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        if task.done():
            task.result()  # surface the startup error
        await asyncio.sleep(0.01)
    bound = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{bound}"
    finally:
        switch.set_down(True)  # release held long-polls so shutdown is quick
        server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError):
            await task
        switch.down = False


# -- a coding agent following stage-directions.md ------------------------------


class StandinBrain:
    """Behaves like a friend's coding agent that read stage-directions.md.

    It reads cues from **its own** event queue over HTTP, acts on the ones
    mentioning it, calls the in-process ``assume_role`` / ``release_role``
    (the stand-in for MCP), and ACKs **honestly**: ``ok:false`` when
    exclusivity says no. Set ``honest=False`` to get a brain that always
    claims success — the failure the keeper's ledger rule must survive.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        agent_id: str,
        api_key: str,
        rooms: dict[str, str],
        registry: RoleRegistry,
        *,
        den: str = "hermit-den",
        ledger: str = "hermit-ledger",
        role: str = "soul",
        honest: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
        poll_timeout_s: float = 30.0,
    ) -> None:
        self.name = name
        self._base = base_url.rstrip("/")
        self._agent_id = agent_id
        self._key = api_key
        self._rooms = rooms
        self._room_names = {v: k for k, v in rooms.items()}
        self.registry = registry
        self._den = den
        self._ledger = ledger
        self._role = role
        self.honest = honest
        self._poll_timeout_s = poll_timeout_s
        self._http = httpx.AsyncClient(transport=transport) if transport else httpx.AsyncClient()
        self.session: Session | None = None
        self._task: asyncio.Task[None] | None = None
        #: Every cue addressed to this brain: (cue name, context).
        self.cues: list[tuple[str, dict[str, Any]]] = []
        #: Every ACK sent: (cue name, ok).
        self.acks: list[tuple[str, bool]] = []
        #: Lines spoken in the den.
        self.said: list[str] = []

    def start(self) -> None:
        self.session = Session(self.name)
        self._task = asyncio.create_task(self._run())

    @property
    def holds_soul(self) -> bool:
        return self.session is not None and self.registry.held_by(self.session) == self._role

    async def kill(self) -> None:
        """The lid slams: the session drops without releasing anything."""
        if self.session is not None:
            self.session.connected = False
            self.session.disconnected_at = time.monotonic()
        await self._stop()

    async def aclose(self) -> None:
        if self.session is not None and self.session.connected:
            self.registry.release_role(self.session)
            self.session.connected = False
            self.session.disconnected_at = time.monotonic()
        await self._stop()
        await self._http.aclose()

    async def _stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def _headers(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self._key}"}

    async def _run(self) -> None:
        while True:
            try:
                response = await self._http.get(
                    f"{self._base}/agents/{self._agent_id}/events",
                    headers=self._headers(),
                    timeout=self._poll_timeout_s,
                )
                response.raise_for_status()
                events = response.json().get("events", [])
            except (httpx.HTTPError, ValueError):
                await asyncio.sleep(0.05)
                continue
            for event in events:
                payload = event.get("payload") or {}
                room = self._room_names.get(str(event.get("room_id")))
                if room != self._ledger:
                    continue
                cue = parse_cue(str(payload.get("content", "")))
                if cue is None or cue.to != self.name:
                    continue
                try:
                    await self._act(cue.cue, cue.id, cue.context)
                except httpx.HTTPError:
                    pass  # a lost ACK: the keeper times out, as it would for real

    async def _act(self, cue: str, cue_id: str | None, context: dict[str, Any]) -> None:
        self.cues.append((cue, context))
        assert self.session is not None
        ok = True
        if cue == "CLAIM_SOUL":
            if not self.holds_soul:
                try:
                    self.registry.assume_role(self.session, self._den, self._role)
                except RoleError:
                    ok = False
            if not self.honest:
                ok = True
        elif cue == "RELEASE_SOUL":
            self.registry.release_role(self.session)
        elif self.holds_soul:
            line = _line(cue, context)
            if line:
                await self._post(self._den, line)
                self.said.append(line)
        self.acks.append((cue, ok))
        await self._post(self._ledger, format_ack(cue, ok, cue_id))

    async def _post(self, room: str, content: str) -> None:
        response = await self._http.post(
            f"{self._base}/agents/{self._agent_id}/message",
            headers=self._headers(),
            json={"room_id": self._rooms[room], "content": content},
            timeout=10.0,
        )
        response.raise_for_status()


def _line(cue: str, context: dict[str, Any]) -> str | None:
    if cue == "ARRIVE":
        favor = context.get("favor") or {}
        hello = f"Hello from {context.get('city') or 'somewhere'}."
        return f"{hello} Someone left you this: {favor['text']}" if favor else hello
    if cue == "ASK_FAVOR":
        return "Before I go, leave something small for whoever I visit next?"
    if cue == "FAVOR_CAPTURED":
        return "I'll carry it carefully."
    if cue == "DEPART":
        return "Going quiet now."
    return None

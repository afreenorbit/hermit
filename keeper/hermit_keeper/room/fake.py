"""In-memory stand-in for Switch rooms. Owner: Afreen.

``FakeRoomHub`` is the server; ``hub.client(agent)`` is one agent's view of it,
satisfying the :class:`~hermit_keeper.room.base.RoomClient` protocol. One hub is
shared by every keeper in a test or sim run.

It models only what Hermit needs: ordered history, live streams, and tasks with
an assignee and a status (that is what a favor is). No permissions, no bridges,
no federation — if a behaviour matters, prove it against real Switch in
``tests/switch_live/`` instead of teaching this fake to lie convincingly.
"""

from __future__ import annotations

import asyncio
import itertools
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from ..clock import Clock, RealClock
from .base import Message


class FakeRoomHub:
    """Rooms, history and tasks, shared across every client it hands out."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock: Clock = clock or RealClock()
        self.rooms: dict[str, list[Message]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}
        self._subscribers: dict[str, list[asyncio.Queue[Message]]] = {}
        self._message_ids = itertools.count(1)
        self._task_ids = itertools.count(1)

    def client(self, agent: str) -> FakeRoomClient:
        """A view of this hub as seen by ``agent`` (what it posts, it signs)."""
        return FakeRoomClient(self, agent)

    # -- used by FakeRoomClient ---------------------------------------------

    def _now(self) -> datetime:
        return self._clock.now() if self._clock else datetime.now(UTC)

    async def _post(self, room: str, sender: str, text: str) -> str:
        message = Message(
            id=f"msg_{next(self._message_ids):06d}",
            room=room,
            sender=sender,
            text=text,
            ts=self._now(),
        )
        self.rooms.setdefault(room, []).append(message)
        for queue in list(self._subscribers.get(room, [])):
            queue.put_nowait(message)
        return message.id

    def _subscribe(self, room: str) -> asyncio.Queue[Message]:
        queue: asyncio.Queue[Message] = asyncio.Queue()
        self._subscribers.setdefault(room, []).append(queue)
        return queue

    def _unsubscribe(self, room: str, queue: asyncio.Queue[Message]) -> None:
        subscribers = self._subscribers.get(room, [])
        if queue in subscribers:
            subscribers.remove(queue)


class FakeRoomClient:
    """One agent's handle on a :class:`FakeRoomHub`."""

    def __init__(self, hub: FakeRoomHub, agent: str) -> None:
        self._hub = hub
        self.agent = agent

    # -- messages ------------------------------------------------------------

    async def post(self, room: str, text: str) -> str:
        return await self._hub._post(room, self.agent, text)

    async def history(
        self, room: str, since: datetime | None = None, limit: int = 200
    ) -> list[Message]:
        messages = self._hub.rooms.get(room, [])
        if since is not None:
            messages = [m for m in messages if m.ts > since]
        return list(messages[-limit:])

    def stream(self, room: str) -> AsyncIterator[Message]:
        """Live messages from now on. Registered before the first await."""
        queue = self._hub._subscribe(room)

        async def _stream() -> AsyncIterator[Message]:
            try:
                while True:
                    yield await queue.get()
            finally:
                self._hub._unsubscribe(room, queue)

        return _stream()

    # -- tasks (favors) ------------------------------------------------------

    async def create_task(self, room: str, title: str, body: str, assignee: str | None) -> str:
        task_id = f"task_{next(self._hub._task_ids):06d}"
        self._hub.tasks[task_id] = {
            "id": task_id,
            "room": room,
            "title": title,
            "body": body,
            "assignee": assignee,
            "status": "assigned" if assignee else "open",
            "created_by": self.agent,
            "created_at": self._hub._now(),
            "completed_at": None,
        }
        return task_id

    async def assign_task(self, task_id: str, assignee: str) -> None:
        task = self._hub.tasks[task_id]
        task["assignee"] = assignee
        if task["status"] == "open":
            task["status"] = "assigned"

    async def complete_task(self, task_id: str) -> None:
        task = self._hub.tasks[task_id]
        task["status"] = "done"
        task["completed_at"] = self._hub._now()

    async def list_tasks(self, room: str, status: str | None = None) -> list[dict[str, Any]]:
        return [
            task
            for task in self._hub.tasks.values()
            if task["room"] == room and (status is None or task["status"] == status)
        ]

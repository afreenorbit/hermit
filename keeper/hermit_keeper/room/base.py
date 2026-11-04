"""RoomClient — everything we do to a Switch room. Owner: A."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class Message(BaseModel):
    id: str
    room: str
    sender: str
    text: str
    ts: datetime


class RoomClient(Protocol):
    async def post(self, room: str, text: str) -> str: ...
    async def history(
        self, room: str, since: datetime | None = None, limit: int = 200
    ) -> list[Message]: ...
    def stream(self, room: str) -> AsyncIterator[Message]: ...
    async def create_task(self, room: str, title: str, body: str, assignee: str | None) -> str: ...
    async def assign_task(self, task_id: str, assignee: str) -> None: ...
    async def complete_task(self, task_id: str) -> None: ...
    async def list_tasks(self, room: str, status: str | None = None) -> list[dict[str, Any]]: ...

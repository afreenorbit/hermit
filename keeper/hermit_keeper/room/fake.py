"""FakeRoomHub — in-memory rooms, ordered history, tasks, fan-out streams. Owner: A.

One hub is shared by every keeper in a test or sim run, the way one Switch
server is shared by every laptop.
"""

from __future__ import annotations

raise_todo = "TODO(A): Phase 1.3"


class FakeRoomHub:
    """Create rooms lazily; `client(agent_name)` returns a RoomClient view."""

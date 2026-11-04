"""Local mirror of everything this keeper emitted. Owner: Abhishek (4.5).

The ledger room is the source of truth. This is a second copy on disk so a
keeper can be debugged offline, and so a journey can still be rebuilt if the
room is unreachable when it is time to export.
"""

from __future__ import annotations

import json
from pathlib import Path

from .events import Event

DEFAULT_PATH = Path.home() / ".hermit" / "journey.jsonl"


class Journal:
    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        self.path = Path(path).expanduser()

    def append(self, event: Event) -> None:
        """One JSON object per line. Never raises: a journal that fails must
        not take the keeper down with it."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.model_dump(mode="json")) + "\n")
        except OSError:
            pass

    def read(self) -> list[Event]:
        if not self.path.exists():
            return []
        events: list[Event] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(Event.model_validate_json(line))
            except ValueError:
                continue
        return events

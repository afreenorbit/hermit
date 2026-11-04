"""Shell pieces: what a completed favor leaves behind. Owner: Abhishek (4.2).

A piece is pure data. Rendering lives in `ui-shared`, and both sides derive
everything from `seed` so the same piece draws identically on every machine
without us storing a picture.

Four independent axes (plan.md 3.6, revised Nov 4):

* **colour** — the host's local hour of arrival. Changed from temperature
  because all three of us are in one city, so temperature would make every
  piece the same colour and the shell would read as one flat blob.
* **pattern** — which brain voiced Hermit at that stop.
* **size** — how long it stayed.
* **edge** — how it left. An abrupt departure leaves a cracked piece.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from .ids import new_id, seed_from_id

Departure = Literal["graceful", "bedtime", "abrupt", "manual"]


@dataclass
class ShellPiece:
    """Mirrors shared/schemas/shell-piece.schema.json."""

    id: str
    host: str
    city: str
    brain_provider: str
    dwell_s: int
    departure: str
    created_at: str
    seed: int
    temp_c: float | None = None
    weather_code: int | None = None
    favor_id: str | None = None
    v: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": self.v,
            "id": self.id,
            "host": self.host,
            "city": self.city,
            "brain_provider": self.brain_provider,
            "temp_c": self.temp_c,
            "weather_code": self.weather_code,
            "dwell_s": self.dwell_s,
            "departure": self.departure,
            "favor_id": self.favor_id,
            "created_at": self.created_at,
            "seed": self.seed,
        }


def make_piece(
    host: str,
    city: str,
    brain_provider: str,
    dwell_s: float,
    departure: str,
    created_at: datetime,
    favor_id: str | None = None,
    temp_c: float | None = None,
    weather_code: int | None = None,
    piece_id: str | None = None,
) -> ShellPiece:
    """Build a piece. Deterministic given its id."""
    pid = piece_id or new_id("pc")
    return ShellPiece(
        id=pid,
        host=host,
        city=city,
        brain_provider=brain_provider,
        dwell_s=int(max(0, dwell_s)),
        departure=departure,
        created_at=created_at.isoformat().replace("+00:00", "Z"),
        seed=seed_from_id(pid),
        temp_c=temp_c,
        weather_code=weather_code,
        favor_id=favor_id,
    )


#: Hour band -> palette name. The UI maps these to the pocket-hermit colours.
def hour_band(local_hour: int) -> str:
    """Which part of the day a stop belongs to."""
    if 5 <= local_hour < 8:
        return "dawn"
    if 8 <= local_hour < 17:
        return "day"
    if 17 <= local_hour < 21:
        return "dusk"
    return "night"


def describe(piece: ShellPiece, local_hour: int | None = None) -> str:
    """One human line, for the brain to say and the map to caption."""
    hour = local_hour if local_hour is not None else 12
    band = hour_band(hour)
    edge = {
        "abrupt": "cracked at one edge",
        "bedtime": "soft and dim",
        "manual": "neatly trimmed",
    }.get(piece.departure, "smooth")
    minutes = piece.dwell_s // 60
    return f"a {band}-coloured piece from {piece.city}, {edge}, {minutes} minutes wide"

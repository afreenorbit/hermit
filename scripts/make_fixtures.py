"""Generate the map's demo fixtures. Owner: D.

Two scales, same schema, so the map's auto-fit is built against both:
  map/public/data/journey.sample.json       Bengaluru  (our real pilot shape)
  map/public/data/journey.wide.sample.json  3 timezones (the sim capability)

Run: python scripts/make_fixtures.py
"""

from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

ALPH = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ROOT = Path(__file__).resolve().parents[1]

FAVORS = [
    "Send the group the last song stuck in your head",
    "Tell Akshay one thing you're proud of this week",
    "Take a photo of your window right now",
    "Ask the next host what they ate today",
    "Write one line of a story the next person continues",
    "Send Abhishek the worst photo on your camera roll",
    "Recommend one thing worth 10 minutes",
]
DEPARTURES = [
    "graceful",
    "bedtime",
    "graceful",
    "abrupt",
    "graceful",
    "bedtime",
    "graceful",
    "present",
]
DWELLS = [5400, 7200, 3600, 900, 10800, 6300, 4500, 2700]


def _iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed(piece_id: str) -> int:
    h = 2166136261
    for ch in piece_id.split("_", 1)[1]:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h & 0x7FFFFFFF


def build(hosts: list[tuple], temps: list[float], codes: list[int], seed: int) -> dict:
    rng = random.Random(seed)

    def ulid(prefix: str) -> str:
        return prefix + "_" + "".join(rng.choice(ALPH) for _ in range(26))

    stops: list[dict] = []
    shell: list[dict] = []
    cur = 1762300800  # 2026-11-05T00:00:00Z
    prev: tuple[str, str, str] | None = None

    for i, dep in enumerate(DEPARTURES):
        host = hosts[i % 3]
        arrived, left = cur, cur + DWELLS[i]
        fav_id, piece_id, stop_id = ulid("fav"), ulid("pc"), ulid("stop")

        received = None
        if prev:
            received = {
                "id": prev[0],
                "text": prev[1],
                "left_by": prev[2],
                "status": "expired" if i == 4 else "done",
            }
        left_favor = (
            None
            if dep == "abrupt"
            else {
                "id": fav_id,
                "text": FAVORS[i % len(FAVORS)],
                "left_by": host[0],
                "for": "next",
                "status": "done" if i < 6 else "open",
            }
        )

        stops.append(
            {
                "stop_id": stop_id,
                "seq": i + 1,
                "host": host[0],
                "arrived_at": _iso(arrived),
                "left_at": None if dep == "present" else _iso(left),
                "departure": dep,
                "weather": {"temp_c": temps[i], "code": codes[i]},
                "favor_received": received,
                "favor_left": left_favor,
                "shell_piece_id": piece_id,
            }
        )
        shell.append(
            {
                "v": 1,
                "id": piece_id,
                "host": host[0],
                "city": host[2],
                "brain_provider": host[5],
                "temp_c": temps[i],
                "weather_code": codes[i],
                "dwell_s": DWELLS[i],
                "departure": "graceful" if dep == "present" else dep,
                "favor_id": prev[0] if prev else None,
                "created_at": _iso(left),
                "seed": _seed(piece_id),
            }
        )
        if left_favor:
            prev = (fav_id, left_favor["text"], host[0])
        cur = left + 300

    last = hosts[(len(DEPARTURES) - 1) % 3]
    return {
        "v": 1,
        "generated_at": _iso(cur),
        "hermit": {
            "current_host": last[0],
            "current_city": last[2],
            "since": stops[-1]["arrived_at"],
        },
        "hosts": [
            {
                "host_id": a,
                "display_name": b,
                "city": c,
                "lat": d,
                "lon": e,
                "brain_provider": f,
            }
            for a, b, c, d, e, f in hosts
        ],
        "stops": stops,
        "shell": shell,
        "stats": {
            "handoffs": 7,
            "favors_done": 6,
            "favors_left": 7,
            "overlaps_suggested": 2,
            "overlaps_taken": 1,
            "median_handoff_ms": 8400,
        },
    }


# Our real shape: one city, three areas ~25 km apart, one weather for everyone.
# Shell colour must come from local hour, not temperature (plan.md 3.6).
BLR = [
    ("afreen", "Afreen", "Indiranagar", 12.9719, 77.6412, "claude-code"),
    ("abhishek", "Abhishek", "Kengeri", 12.9166, 77.4826, "opencode"),
    ("akshay", "Akshay", "Koramangala", 12.9352, 77.6245, "codex"),
]
WIDE = [
    ("afreen", "Afreen", "Bengaluru", 12.97, 77.59, "claude-code"),
    ("abhishek", "Abhishek", "Berlin", 52.52, 13.40, "opencode"),
    ("akshay", "Akshay", "Toronto", 43.65, -79.38, "codex"),
]

if __name__ == "__main__":
    out = ROOT / "map" / "public" / "data"
    near = build(
        BLR,
        [26.0, 23.5, 21.0, 27.5, 24.0, 20.5, 28.0, 22.5],
        [1, 2, 3, 0, 2, 61, 0, 1],
        seed=11,
    )
    wide = build(
        WIDE,
        [24.0, 8.5, -2.0, 26.5, 9.0, -4.5, 27.0, 10.5],
        [2, 3, 71, 1, 61, 73, 0, 2],
        seed=23,
    )
    (out / "journey.sample.json").write_text(
        json.dumps(near, indent=2) + "\n", encoding="utf-8"
    )
    (out / "journey.wide.sample.json").write_text(
        json.dumps(wide, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "wrote journey.sample.json (Bengaluru) and journey.wide.sample.json (3 timezones)"
    )

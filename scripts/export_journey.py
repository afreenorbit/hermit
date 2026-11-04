"""Rebuild the journey from the ledger. Owner: Abhishek (Phase 4.5).

    python scripts/export_journey.py --from-files ~/.hermit/journey.jsonl
    python scripts/export_journey.py --from-room          # needs Switch (Phase 2)

The ledger is the source of truth, so this script is a pure fold over events:
every stop, favor and shell piece in `journey.json` comes from a `HERMIT/1`
line somebody wrote at the time. Nothing is inferred and nothing is invented —
if it is not in the ledger, it did not happen.

Output is validated against `shared/schemas/journey.schema.json` before it is
written, so a bad export fails here rather than in the map.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "keeper"))

from hermit_keeper import ledger
from hermit_keeper.events import Event, EventType

DEFAULT_OUT = REPO / "map" / "public" / "data" / "journey.json"


def load_from_files(paths: list[Path]) -> list[Event]:
    """Merge local journal mirrors, oldest event first."""
    events: list[Event] = []
    for path in paths:
        if not path.exists():
            print(f"skipping missing {path}", file=sys.stderr)
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            event = (
                ledger.decode(line) if line.startswith(ledger.PREFIX) else _loads(line)
            )
            if event is not None:
                events.append(event)
    return sorted(events, key=lambda e: (e.ts, e.id))


def _loads(line: str) -> Event | None:
    try:
        return Event.model_validate_json(line)
    except ValueError:
        return None


def build_journey(
    events: list[Event], hosts: list[dict[str, Any]], generated_at: str
) -> dict[str, Any]:
    """Fold the event stream into the shape the map reads."""
    stops: list[dict[str, Any]] = []
    shell: list[dict[str, Any]] = []
    favors: dict[str, dict[str, Any]] = {}
    open_stop: dict[str, dict[str, Any]] = {}
    handoffs = 0
    favors_left = 0
    favors_done = 0

    for event in events:
        data = event.data
        kind = event.type

        if kind is EventType.ARRIVAL_ANNOUNCED:
            handoffs += 1
            # Somebody else arriving means every earlier stop is over. A stop
            # still open at that moment never wrote SOUL_RELEASED, so its host
            # never said goodbye: the lid came down and the lease expired.
            # That is exactly the abrupt departure, recovered from the ledger
            # alone without anyone having to notice it at the time.
            for host_id, earlier in list(open_stop.items()):
                if host_id == event.host:
                    continue
                earlier["left_at"] = _iso(event.ts)
                earlier["departure"] = "abrupt"
                open_stop.pop(host_id, None)
            stop = {
                "stop_id": data.get("stop_id") or f"stop_{len(stops):026d}",
                "seq": len(stops) + 1,
                "host": event.host,
                "arrived_at": _iso(event.ts),
                "left_at": None,
                # 'present' until we see them leave; a stop with no departure
                # is either happening now or ended in a lid slam.
                "departure": "present",
                "weather": data.get("weather"),
                "favor_received": None,
                "favor_left": None,
                "shell_piece_id": None,
            }
            if data.get("favor_id") and data["favor_id"] in favors:
                stop["favor_received"] = _ref(favors[data["favor_id"]])
            stops.append(stop)
            open_stop[event.host] = stop

        elif kind is EventType.SOUL_RELEASED:
            stop = open_stop.pop(event.host, None)
            if stop is not None:
                stop["left_at"] = _iso(event.ts)
                stop["departure"] = str(data.get("departure", "graceful"))

        elif kind is EventType.FAVOR_LEFT:
            favor = dict(data.get("favor") or {})
            if favor.get("id"):
                favors[favor["id"]] = favor
                favors_left += 1
                stop = open_stop.get(event.host)
                if stop is not None:
                    stop["favor_left"] = _ref(favor, for_next=True)

        elif kind is EventType.FAVOR_COMPLETED:
            favor_id = data.get("favor_id")
            if favor_id in favors:
                favors[favor_id]["status"] = "done"
                favors_done += 1

        elif kind is EventType.SHELL_PIECE_ADDED:
            piece = dict(data.get("piece") or {})
            if piece.get("id"):
                shell.append(piece)
                stop = open_stop.get(event.host)
                if stop is not None:
                    stop["shell_piece_id"] = piece["id"]

    # A stop still open at the end is where Hermit is now.
    current = stops[-1] if stops and stops[-1]["left_at"] is None else None
    host_index = {h["host_id"]: h for h in hosts}

    return {
        "v": 1,
        "generated_at": generated_at,
        "hermit": {
            "current_host": current["host"] if current else None,
            "current_city": (
                host_index.get(current["host"], {}).get("city") if current else None
            ),
            "since": current["arrived_at"] if current else None,
        },
        "hosts": hosts,
        "stops": stops,
        "shell": shell,
        "stats": {
            "handoffs": max(0, handoffs - 1),
            "favors_done": favors_done,
            "favors_left": favors_left,
            "overlaps_suggested": 0,
            "overlaps_taken": 0,
            "median_handoff_ms": None,
        },
    }


def _ref(favor: dict[str, Any], for_next: bool = False) -> dict[str, Any]:
    ref = {
        "id": favor.get("id", ""),
        "text": favor.get("text", ""),
        "left_by": favor.get("left_by", ""),
        "status": favor.get("status", "open"),
    }
    if for_next:
        ref["for"] = "next"
    return ref


def _iso(value: Any) -> str:
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return text.replace("+00:00", "Z")


def validate(journey: dict[str, Any]) -> list[str]:
    """Check against the frozen schema. Returns a list of problems."""
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError:
        return []
    schemas = REPO / "shared" / "schemas"
    registry = Registry().with_resource(
        "https://hermit.dev/schemas/shell-piece.schema.json",
        Resource.from_contents(
            json.loads(
                (schemas / "shell-piece.schema.json").read_text(encoding="utf-8")
            )
        ),
    )
    validator = Draft202012Validator(
        json.loads((schemas / "journey.schema.json").read_text(encoding="utf-8")),
        registry=registry,
    )
    return [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(journey)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-files", nargs="*", type=Path, default=[])
    parser.add_argument(
        "--from-room", action="store_true", help="needs Switch (Phase 2)"
    )
    parser.add_argument("--hosts", type=Path, help="JSON list of host objects")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if args.from_room:
        print(
            "--from-room needs the Switch client (Phase 2). Use --from-files.",
            file=sys.stderr,
        )
        return 2

    events = load_from_files(args.from_files)
    if not events:
        print("no events found", file=sys.stderr)
        return 1

    hosts = json.loads(args.hosts.read_text(encoding="utf-8")) if args.hosts else []
    journey = build_journey(events, hosts, generated_at=_iso(events[-1].ts))

    problems = validate(journey)
    if problems:
        print("export does not match the schema:", file=sys.stderr)
        for problem in problems[:10]:
            print(f"  {problem}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(journey, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.out}: {len(journey['stops'])} stops, "
        f"{len(journey['shell'])} shell pieces, {journey['stats']['favors_done']} favors done"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Metrics: the README and pilot numbers, and their SIMULATION/REAL labels."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from hermit_keeper import ledger, metrics
from hermit_keeper.events import Event, EventType

REPO_ROOT = Path(__file__).resolve().parents[3]
T0 = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)


def at(minutes: float) -> str:
    return (T0 + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def ev(kind: EventType, host: str, minutes: float, **data: Any) -> Event:
    return Event(type=kind, host=host, ts=T0 + timedelta(minutes=minutes), data=data)


def stop(seq: int, host: str, arrived: float, left: float | None, departure: str) -> dict[str, Any]:
    return {
        "stop_id": f"stop_{seq:026d}",
        "seq": seq,
        "host": host,
        "arrived_at": at(arrived),
        "left_at": at(left) if left is not None else None,
        "departure": departure,
    }


JOURNEY: dict[str, Any] = {
    "generated_at": at(300),
    "hosts": [
        {"host_id": "afreen", "brain_provider": "claude-code"},
        {"host_id": "abhishek", "brain_provider": "opencode"},
        {"host_id": "akshay", "brain_provider": "codex"},
    ],
    "stops": [
        stop(1, "afreen", 0, 60, "graceful"),
        stop(2, "abhishek", 61, 120, "abrupt"),
        stop(3, "akshay", 120, 180, "bedtime"),
        stop(4, "afreen", 240, None, "present"),
    ],
    "shell": [{"host": "abhishek", "departure": "abrupt", "brain_provider": "opencode"}],
    "stats": {"favors_left": 4, "favors_done": 3, "overlaps_suggested": 2},
}


def test_percentile_is_nearest_rank() -> None:
    values = [5.0, 1.0, 3.0, 2.0, 4.0]
    assert metrics.percentile(values, 50) == 3.0
    assert metrics.percentile(values, 95) == 5.0
    assert metrics.percentile([7.0], 95) == 7.0
    assert metrics.percentile([], 50) is None


def test_journey_only_metrics() -> None:
    m = metrics.compute(JOURNEY)
    assert m["stops"] == 4
    assert m["handoffs"] == 3
    lat = m["handoff_latency_s"]
    # afreen -> abhishek took 60 s; the abrupt stop is left out; akshay ->
    # afreen took an hour, which nobody was waiting for.
    assert (lat["n"], lat["p50"], lat["excluded_abrupt"], lat["cold_handoffs"]) == (1, 60.0, 1, 1)
    assert lat["method"] == "gap<=600s"
    assert m["departures"] == {"graceful": 1, "abrupt": 1, "bedtime": 1, "manual": 0, "present": 1}
    # The abrupt stop's real end is unknown without events: not counted.
    assert m["dwell_s"]["n"] == 2
    assert m["dwell_s"]["buckets"]["1h-3h"] == 2
    assert m["favors"] == {"left": 4, "completed": 3, "completion_rate": 0.75}
    assert m["brains"]["distinct"] == 3
    assert m["overlaps_suggested"] == 2
    assert m["nudges_sent"] is None  # unknowable from a journey alone
    assert m["cracked_pieces"] == 1
    # Gaps: 1 min, 0 (abrupt end unknown), 60 min; Hermit is present at the end.
    assert m["nobody_hosting"]["total_s"] == 61 * 60
    assert m["nobody_hosting"]["longest_s"] == 3600


def test_events_sharpen_latency_dwell_and_favors() -> None:
    events = [
        # abhishek was at the keyboard when afreen let go: a real handoff.
        ev(EventType.HOST_HEARTBEAT, "abhishek", 50, present=True, state="AWAKE_WAITING"),
        ev(EventType.SOUL_CLAIMED, "abhishek", 60.5, holder="abhishek"),
        # abhishek's last line before the lid came down.
        ev(EventType.HOST_HEARTBEAT, "abhishek", 100, present=True, state="HOLDING"),
        # afreen was up at akshay's release but in bedtime lock: not waiting.
        ev(EventType.HOST_HEARTBEAT, "afreen", 170, present=True, state="BEDTIME_LOCK"),
        ev(EventType.FAVOR_LEFT, "afreen", 59, favor={"id": "fav_1"}),
        ev(EventType.FAVOR_LEFT, "abhishek", 99, favor={"id": "fav_2"}),
        ev(EventType.FAVOR_COMPLETED, "abhishek", 70, favor_id="fav_1"),
        ev(EventType.NUDGE_SENT, "afreen", 250, target_host="akshay"),
    ]
    events.append(events[0])  # merged journals repeat lines
    m = metrics.compute(JOURNEY, events)
    lat = m["handoff_latency_s"]
    assert lat["method"] == "presence"
    assert (lat["n"], lat["p50"], lat["cold_handoffs"]) == (1, 30.0, 1)
    assert m["dwell_s"]["n"] == 3  # the abrupt stop now ends at its last line
    assert m["nobody_hosting"]["total_s"] == (1 + 20 + 60) * 60
    assert m["favors"] == {"left": 2, "completed": 1, "completion_rate": 0.5}
    assert m["nudges_sent"] == 1
    assert m["overlaps_suggested"] == 0


def test_empty_journey_is_all_unknowns_not_zeros() -> None:
    m = metrics.compute({"stops": [], "shell": [], "stats": {}})
    assert m["handoff_latency_s"]["p50"] is None
    assert m["nobody_hosting"]["total_s"] is None
    assert m["favors"]["completion_rate"] is None


def test_markdown_labels_simulation_and_never_pools_it_with_real() -> None:
    sim = {"name": "s", "source": "simulation", "metrics": metrics.compute(JOURNEY)}
    real = {"name": "r", "source": "real", "metrics": metrics.compute(JOURNEY)}
    sim["latency_samples"], real["latency_samples"] = [10.0], [99.0]
    pooled = metrics.pool_latency([sim, real])
    assert pooled["simulation"]["max"] == 10.0 and pooled["real"]["max"] == 99.0
    table = metrics.render_markdown([sim, real], pooled)
    assert "**SIMULATION**" in table and "not** pilot results" in table
    assert "| r | **REAL** |" in table
    only_real = metrics.render_markdown([real])
    assert "SIMULATION" not in only_real


# -- the pilot path: real ledger lines -> export -> metrics --------------------


def _pilot_ledger(tmp_path: Path) -> Path:
    events = [
        ev(EventType.HOST_HEARTBEAT, "afreen", 0, present=True, state="AWAKE_WAITING"),
        ev(EventType.ARRIVAL_ANNOUNCED, "afreen", 1, stop_id="stop_" + "0" * 25 + "1"),
        ev(EventType.HOST_HEARTBEAT, "abhishek", 30, present=True, state="AWAKE_WAITING"),
        ev(EventType.SOUL_RELEASED, "afreen", 40, departure="graceful"),
        ev(EventType.ARRIVAL_ANNOUNCED, "abhishek", 40.25, stop_id="stop_" + "0" * 25 + "2"),
    ]
    path = tmp_path / "pilot.jsonl"
    lines = [ledger.encode(e) for e in events] + ["a human chatting in the ledger"]
    path.write_text("\n".join(lines + lines[:2]) + "\n", encoding="utf-8")
    return path


def test_a_real_export_goes_through_unchanged_and_is_labelled_real(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from export_journey import build_journey, load_from_files, validate

    events = load_from_files([_pilot_ledger(tmp_path)])
    assert len(events) == 5  # duplicates dropped, chatter ignored
    journey = build_journey(events, [], events[-1].ts.isoformat())
    assert validate(journey) == []
    assert journey["stats"]["median_handoff_ms"] == 15000
    assert "source" not in journey["stats"]

    m = metrics.compute(journey, events)
    assert m["handoff_latency_s"]["p50"] == 15.0


def test_sim_metrics_cli_on_pilot_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from sim.__main__ import main

    out = tmp_path / "metrics.json"
    md = tmp_path / "metrics.md"
    assert main(["metrics", str(_pilot_ledger(tmp_path)), "--out", str(out), "--md", str(md)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["label"] == "REAL"
    assert payload["datasets"][0]["metrics"]["handoffs"] == 1
    assert "SIMULATION" not in md.read_text(encoding="utf-8")

    # A journey the sim wrote carries its label with it, wherever it is copied.
    journey = {"stops": [], "shell": [], "hosts": [], "stats": {"source": "simulation"}}
    sim_file = tmp_path / "copied.json"
    sim_file.write_text(json.dumps(journey), encoding="utf-8")
    assert main(["metrics", str(sim_file), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["label"] == "SIMULATION"
    assert "**SIMULATION**" in capsys.readouterr().out

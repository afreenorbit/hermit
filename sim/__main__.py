"""Run a Hermit scenario on one machine.

    python -m sim run sim/scenarios/one_timezone_day.yaml
    python -m sim all                 # every scenario, time-compressed
    python -m sim live                # three real keepers, three ports
    python -m sim metrics             # numbers from every sim/out/*/journey.json
    python -m sim metrics pilot/journey.json          # a real export
    python -m sim metrics ~/.hermit/journey.jsonl ... # raw ledger/journal lines

Writes `sim/out/<scenario>/journey.json`, which the map can render directly —
that is how to get a demo journey without three laptops and a weekend.

Exits non-zero if any assertion fails, so CI can run it.

Every number that comes from simulated data is labelled SIMULATION, in the
JSON and in the table. Real exports are labelled REAL. The two are never
pooled together.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "keeper"))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from hermit_keeper import ledger, metrics
from hermit_keeper.events import Event

from sim.runner import run_scenario

SCENARIOS = REPO / "sim" / "scenarios"
OUT = REPO / "sim" / "out"


async def _run(paths: list[Path], quiet: bool, metrics_out: Path | None) -> int:
    failed = 0
    rows: list[dict[str, Any]] = []
    for path in paths:
        print(f"\n=== {path.stem} ===")
        result = await run_scenario(path, verbose=not quiet)

        out_dir = OUT / path.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "journey.json").write_text(
            json.dumps(result.journey, indent=2) + "\n", encoding="utf-8"
        )
        # The raw ledger next to it, so `sim metrics` can use presence too.
        (out_dir / "ledger.jsonl").write_text(
            "".join(ledger.encode(e) + "\n" for e in metrics.dedupe(result.events)),
            encoding="utf-8",
        )
        rows.append(
            _row(path.stem, "simulation", result.journey, result.events)
        )

        stops = len(result.journey.get("stops", []))
        pieces = len(result.journey.get("shell", []))
        if result.ok:
            print(
                f"  PASS  {stops} stops, {pieces} shell pieces -> {out_dir / 'journey.json'}"
            )
        else:
            failed += 1
            print(f"  FAIL  {stops} stops, {pieces} shell pieces")
            for problem in result.failures:
                print(f"        - {problem}")
    print()
    if rows:
        _report(rows, metrics_out, None)
    return 1 if failed else 0


# -- metrics -----------------------------------------------------------------


def _row(
    name: str, source: str, journey: dict[str, Any], events: list[Event] | None
) -> dict[str, Any]:
    stops = sorted(journey.get("stops") or [], key=lambda s: s.get("seq", 0))
    evs = metrics.dedupe(events) if events is not None else None
    return {
        "name": name,
        "source": source,
        "label": metrics.label(source),
        "metrics": metrics.compute(journey, evs),
        "latency_samples": metrics.latency_samples(stops, evs),
    }


def _source_of(path: Path, journey: dict[str, Any], forced: str | None) -> str:
    if forced:
        return forced
    if (journey.get("stats") or {}).get("source") == "simulation" or _under_out(path):
        return "simulation"
    return "real"


def _read_events(paths: list[Path]) -> list[Event]:
    from export_journey import load_from_files  # type: ignore[import-not-found]

    events: list[Event] = load_from_files(paths)
    return events


def _metrics(args: argparse.Namespace) -> int:
    paths: list[Path] = args.scenarios or sorted(OUT.glob("*/journey.json"))
    if not paths:
        print(
            "no journeys found - run `python -m sim all` first, or pass "
            "journey.json / ledger .jsonl files",
            file=sys.stderr,
        )
        return 2

    rows: list[dict[str, Any]] = []
    journeys = [p for p in paths if p.suffix == ".json"]
    lines = [p for p in paths if p.suffix != ".json"]

    for path in journeys:
        journey = json.loads(path.read_text(encoding="utf-8"))
        sibling = path.with_name("ledger.jsonl")
        events = _read_events([sibling]) if sibling.exists() else None
        name = path.parent.name if path.name == "journey.json" else path.stem
        rows.append(_row(name, _source_of(path, journey, args.source), journey, events))

    if lines:
        # Raw ledger / journal lines, possibly from several laptops: one
        # dataset, folded by the same code the export uses.
        from export_journey import build_journey  # type: ignore[import-not-found]

        events = _read_events(lines)
        if not events:
            print("no HERMIT/1 events in those files", file=sys.stderr)
            return 1
        hosts = json.loads(args.hosts.read_text(encoding="utf-8")) if args.hosts else []
        journey = build_journey(events, hosts, events[-1].ts.isoformat())
        source = args.source or (
            "simulation" if all(_under_out(p) for p in lines) else "real"
        )
        rows.append(_row(args.name or "ledger", source, journey, events))

    _report(rows, args.out, args.md)
    return 0


def _under_out(path: Path) -> bool:
    try:
        path.resolve().relative_to(OUT.resolve())
        return True
    except ValueError:
        return False


def _report(rows: list[dict[str, Any]], out: Path | None, md: Path | None) -> None:
    pooled = metrics.pool_latency(rows)
    sources = sorted({r["source"] for r in rows})
    payload = {
        "v": 1,
        "label": " + ".join(metrics.label(s) for s in sources),
        "note": (
            "SIMULATION rows come from the fake sim (scripted presence, fake "
            "Switch). They are not pilot results."
            if "simulation" in sources
            else "Computed from real exports."
        ),
        "pooled_handoff_latency_s": {
            s: {**v, "label": metrics.label(s)} for s, v in pooled.items()
        },
        "datasets": [{k: v for k, v in r.items() if k != "latency_samples"} for r in rows],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    table = metrics.render_markdown(rows, pooled)
    print("## Hermit metrics - " + payload["label"] + "\n")
    print(table)
    print(f"wrote {out}")
    if md is not None:
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(_doc(payload["label"], table), encoding="utf-8")
        print(f"wrote {md}")


def _doc(label: str, table: str) -> str:
    return (
        f"# Hermit metrics - {label}\n\n"
        "<!-- GENERATED by `python -m sim metrics --md docs/metrics.md`. "
        "Do not edit by hand; re-run it. -->\n\n"
        f"{table}\n"
        "**Read the simulated latency with care.** The fake sim advances in "
        "30-second ticks and the fake lease frees instantly, so its handoff "
        "latency is a count of sim ticks, not a measurement of Switch. The "
        "README's p50/p95 (plan.md 9.1 item 6) must come from a REAL export.\n\n"
        "Regenerate with:\n\n"
        "```\npython -m sim all --quiet\n"
        "python -m sim metrics --md docs/metrics.md\n```\n\n"
        "For the real pilot, run the same command on the real export instead "
        "(`python -m sim metrics path/to/journey.json` or the raw `.jsonl` "
        "ledger/journal files). Those rows are labelled REAL; never mix the two "
        "in one README number.\n"
    )


def main(argv: list[str] | None = None) -> int:
    # A Windows console piped to a file is cp1252; a stray dash must not crash
    # a CI run.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["run", "all", "live", "metrics"])
    parser.add_argument("scenarios", nargs="*", type=Path)
    parser.add_argument("--quiet", action="store_true", help="hide the timeline")
    parser.add_argument(
        "--out", type=Path, default=OUT / "metrics.json", help="metrics: JSON output"
    )
    parser.add_argument("--md", type=Path, help="metrics: also write this markdown file")
    parser.add_argument(
        "--source",
        choices=["simulation", "real"],
        help="metrics: override the label (default: inferred from the data)",
    )
    parser.add_argument("--hosts", type=Path, help="metrics: JSON list of host objects")
    parser.add_argument("--name", help="metrics: dataset name for raw ledger files")
    args = parser.parse_args(argv)

    if args.command == "live":
        from sim.live import main as live_main

        return live_main([])
    if args.command == "metrics":
        return _metrics(args)

    paths = (
        sorted(SCENARIOS.glob("*.yaml")) if args.command == "all" else args.scenarios
    )
    if not paths:
        print("no scenarios given", file=sys.stderr)
        return 2
    # Only a full run rewrites sim/out/metrics.json; `run` just prints.
    metrics_out = args.out if args.command == "all" else None
    return asyncio.run(_run(paths, args.quiet, metrics_out))


if __name__ == "__main__":
    raise SystemExit(main())

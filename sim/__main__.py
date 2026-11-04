"""Run a Hermit scenario on one machine.

    python -m sim run sim/scenarios/one_timezone_day.yaml
    python -m sim run sim/scenarios/*.yaml --quiet
    python -m sim all

Writes `sim/out/<scenario>/journey.json`, which the map can render directly —
that is how to get a demo journey without three laptops and a weekend.

Exits non-zero if any assertion fails, so CI can run it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "keeper"))
sys.path.insert(0, str(REPO))

from sim.runner import run_scenario

SCENARIOS = REPO / "sim" / "scenarios"
OUT = REPO / "sim" / "out"


async def _run(paths: list[Path], quiet: bool) -> int:
    failed = 0
    for path in paths:
        print(f"\n=== {path.stem} ===")
        result = await run_scenario(path, verbose=not quiet)

        out_dir = OUT / path.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "journey.json").write_text(
            json.dumps(result.journey, indent=2) + "\n", encoding="utf-8"
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
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "all"])
    parser.add_argument("scenarios", nargs="*", type=Path)
    parser.add_argument("--quiet", action="store_true", help="hide the timeline")
    args = parser.parse_args(argv)

    paths = (
        sorted(SCENARIOS.glob("*.yaml")) if args.command == "all" else args.scenarios
    )
    if not paths:
        print("no scenarios given", file=sys.stderr)
        return 2
    return asyncio.run(_run(paths, args.quiet))


if __name__ == "__main__":
    raise SystemExit(main())

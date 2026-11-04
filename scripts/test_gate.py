"""Plan §10.2: the automated test gate, in one command. Owner: Abhishek.

    python scripts/test_gate.py            # everything that needs no Switch
    python scripts/test_gate.py --quick    # keeper only

Run before every recording session and before submission. Stops at the first
failure and says which step it was. Works the same on Windows, macOS and Linux.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KEEPER = REPO / "keeper"


def _pnpm() -> list[str]:
    if shutil.which("pnpm"):
        return ["pnpm"]
    return ["npx", "-y", "pnpm@9.15.4"]


def steps(quick: bool) -> list[tuple[str, list[str], Path]]:
    py = sys.executable
    gate = [
        ("ruff check", [py, "-m", "ruff", "check", "."], KEEPER),
        ("ruff format", [py, "-m", "ruff", "format", "--check", "."], KEEPER),
        ("mypy (strict)", [py, "-m", "mypy"], KEEPER),
        ("keeper tests", [py, "-m", "pytest", "-m", "not live", "-q"], KEEPER),
        ("sim scenarios", [py, "-m", "sim", "all"], REPO),
    ]
    if not quick:
        gate += [
            ("ui typecheck", [*_pnpm(), "-r", "typecheck"], REPO),
            ("ui tests", [*_pnpm(), "-r", "test"], REPO),
        ]
    return gate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="keeper and sim only")
    args = parser.parse_args()

    results: list[tuple[str, float]] = []
    for name, cmd, cwd in steps(args.quick):
        print(f"\n=== {name} ===", flush=True)
        start = time.monotonic()
        # pnpm and npx are .cmd shims on Windows, which only a shell can run.
        shim = sys.platform == "win32" and cmd[0] in ("pnpm", "npx")
        code = subprocess.call(cmd, cwd=cwd, shell=shim)
        took = time.monotonic() - start
        if code != 0:
            print(f"\nGATE FAILED at '{name}' (exit {code}) after {took:.0f}s")
            return code
        results.append((name, took))

    print("\nGATE PASSED")
    for name, took in results:
        print(f"  ok  {name:<16} {took:5.1f}s")
    print("\nNot covered here: pytest -m live (needs a real Switch), map e2e (needs a browser).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared fixtures. Owner: D, but everyone adds to it."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hermit_keeper.clock import FakeClock

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "shared" / "schemas"

# The Switch stand-in and the group harness live in `sim/` at the repo root,
# shared with `python -m sim live --switch standin`.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()

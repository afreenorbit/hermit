"""Shared fixtures. Owner: D, but everyone adds to it."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermit_keeper.clock import FakeClock

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "shared" / "schemas"


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()

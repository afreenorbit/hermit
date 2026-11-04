"""Every fixture in the repo must validate against the frozen schemas.

This is the test that stops the three of us drifting apart.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "shared" / "schemas"


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "schema_name",
    [
        "event.schema.json",
        "favor.schema.json",
        "shell-piece.schema.json",
        "journey.schema.json",
        "host-config.schema.json",
    ],
)
def test_schema_is_valid(schema_name: str) -> None:
    Draft202012Validator.check_schema(_load(schema_name))


@pytest.mark.parametrize("fixture_name", ["journey.sample.json", "journey.wide.sample.json"])
def test_sample_journey_validates(fixture_name: str) -> None:
    journey = json.loads(
        (REPO_ROOT / "map" / "public" / "data" / fixture_name).read_text(encoding="utf-8")
    )
    registry = Registry().with_resource(
        "https://hermit.dev/schemas/shell-piece.schema.json",
        Resource.from_contents(_load("shell-piece.schema.json")),
    )
    validator = Draft202012Validator(_load("journey.schema.json"), registry=registry)
    errors = sorted(validator.iter_errors(journey), key=lambda e: list(e.path))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors]

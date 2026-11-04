"""host-config.schema.json and config.py must accept and reject the same things."""

from __future__ import annotations

import copy
import json
import tomllib
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from hermit_keeper.config import HostConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads(
    (REPO_ROOT / "shared" / "schemas" / "host-config.schema.json").read_text(encoding="utf-8")
)

FULL: dict[str, Any] = {
    "host_id": "afreen",
    "display_name": "Afreen",
    "city": "Bengaluru",
    "lat": 12.97,
    "lon": 77.59,
    "timezone": "Asia/Kolkata",
    "brain_agent": "hermit-afreen",
    "brain_provider": "claude-code",
    "window_dir": "~/HermitWindow",
    "switch": {
        "server_url": "http://100.64.0.1:8000",
        "den_room": "hermit-den",
        "ledger_room": "hermit-ledger",
        "token_env": "HERMIT_SWITCH_TOKEN",
        "lease_strategy": "agent_instructed",
        "agent_id": "6f1c2a7e-0000-4000-8000-000000000001",
        "rooms": {
            "hermit-den": "6f1c2a7e-0000-4000-8000-0000000000d0",
            "hermit-ledger": "6f1c2a7e-0000-4000-8000-0000000000e0",
        },
        "lease_expiry_s": 8,
        "brain_agent_id": "6f1c2a7e-0000-4000-8000-000000000002",
    },
}


def schema_errors(document: dict[str, Any]) -> list[str]:
    return [e.message for e in Draft202012Validator(SCHEMA).iter_errors(document)]


def test_the_example_config_is_valid_for_both() -> None:
    with (REPO_ROOT / "hermit.config.example.toml").open("rb") as fh:
        document = tomllib.load(fh)
    assert schema_errors(document) == []
    HostConfig.model_validate(document)


def test_a_full_agent_instructed_config_is_valid_for_both() -> None:
    assert schema_errors(FULL) == []
    cfg = HostConfig.model_validate(FULL)
    assert cfg.switch.rooms["hermit-ledger"].endswith("e0")
    assert cfg.switch.lease_expiry_s == 8


def test_the_token_is_read_from_the_environment_never_the_file() -> None:
    cfg = HostConfig.model_validate(FULL)
    assert cfg.switch.token({"HERMIT_SWITCH_TOKEN": " key-123 "}) == "key-123"
    assert cfg.switch.token({"HERMIT_SWITCH_TOKEN": "  "}) is None
    assert cfg.switch.token({}) is None
    bad = copy.deepcopy(FULL)
    bad["switch"]["api_key"] = "do-not-put-keys-here"
    assert schema_errors(bad), "the schema must reject a key written into the config"


@pytest.mark.parametrize("expiry", [0, -1])
def test_lease_expiry_must_be_positive(expiry: float) -> None:
    bad = copy.deepcopy(FULL)
    bad["switch"]["lease_expiry_s"] = expiry
    assert schema_errors(bad)
    with pytest.raises(ValidationError):
        HostConfig.model_validate(bad)


def test_room_uuids_must_be_strings() -> None:
    bad = copy.deepcopy(FULL)
    bad["switch"]["rooms"] = {"hermit-den": 42}
    assert schema_errors(bad)
    with pytest.raises(ValidationError):
        HostConfig.model_validate(bad)

"""Load and validate ``hermit.config.toml``.

Mirrors ``shared/schemas/host-config.schema.json``. The file is never committed;
``hermit.config.example.toml`` at the repo root is the template.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

BrainProvider = Literal["claude-code", "codex", "opencode", "other"]
#: Only two exist. There is no way to assume a role from outside the
#: holding agent's own session - see docs/switch-facts.md SP2.
LeaseStrategy = Literal["agent_instructed", "fake"]


class PresenceConfig(BaseModel):
    idle_threshold_s: int = 300
    arrive_debounce_s: int = 60
    min_dwell_s: int = 600
    sleep_gap_s: int = 90


class BedtimeConfig(BaseModel):
    start: str = "01:00"
    end: str = "06:00"
    grace_idle_s: int = 120


class SwitchConfig(BaseModel):
    server_url: str
    den_room: str = "hermit-den"
    ledger_room: str = "hermit-ledger"
    token_env: str = "HERMIT_SWITCH_TOKEN"
    lease_strategy: LeaseStrategy = "agent_instructed"


class FeatureFlags(BaseModel):
    overlap: bool = False
    nudge: bool = False
    critter: bool = True


class ApiConfig(BaseModel):
    port: int = 47800


class HostConfig(BaseModel):
    host_id: str = Field(pattern=r"^[a-z0-9-]{2,24}$")
    display_name: str
    city: str
    lat: float
    lon: float
    timezone: str

    brain_agent: str
    brain_provider: BrainProvider
    window_dir: str

    presence: PresenceConfig = PresenceConfig()
    bedtime: BedtimeConfig = BedtimeConfig()
    switch: SwitchConfig
    features: FeatureFlags = FeatureFlags()
    api: ApiConfig = ApiConfig()


def load(path: str | Path) -> HostConfig:
    with Path(path).expanduser().open("rb") as fh:
        return HostConfig.model_validate(tomllib.load(fh))

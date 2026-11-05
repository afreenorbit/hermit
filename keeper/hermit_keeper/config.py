"""Load and validate ``hermit.config.toml``.

Mirrors ``shared/schemas/host-config.schema.json``. The file is never committed;
``hermit.config.example.toml`` at the repo root is the template.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

BrainProvider = Literal["claude-code", "codex", "opencode", "other"]
#: Only two exist. There is no way to assume a role from outside the
#: holding agent's own session - see docs/switch-facts.md SP2.
LeaseStrategy = Literal["agent_instructed", "keeper_claimed", "fake"]


class PresenceConfig(BaseModel):
    #: After handing Hermit on - especially via "I'm busy, go" - stand aside
    #: this long rather than taking it straight back. Only applies while
    #: another laptop could actually host; otherwise Hermit would be stranded.
    yield_s: float = 300.0

    idle_threshold_s: int = 300
    arrive_debounce_s: int = 60
    min_dwell_s: int = 600
    sleep_gap_s: int = 90


class BedtimeConfig(BaseModel):
    start: str = "01:00"
    end: str = "06:00"
    grace_idle_s: int = 120


class SwitchConfig(BaseModel):
    """How this keeper reaches Switch. The agent's api_key is never in here.

    ``agent_id`` and ``rooms`` come from ``switch/scripts/bootstrap_rooms.py``
    (or whoever registered the agents). The key itself is read from the
    environment variable named by ``token_env``, so the config file stays safe
    to show on screen.
    """

    server_url: str
    den_room: str = "hermit-den"
    ledger_room: str = "hermit-ledger"
    token_env: str = "HERMIT_SWITCH_TOKEN"
    lease_strategy: LeaseStrategy = "agent_instructed"
    #: This keeper's registered Switch agent uuid (``keeper-<host_id>``).
    agent_id: str | None = None
    #: Room name -> Switch room uuid. Switch addresses rooms by uuid only.
    rooms: dict[str, str] = Field(default_factory=dict)
    #: How long Switch takes to free the soul after the holding session dies.
    #: 8 s is a GUESS until measured against a live server (switch-facts SP3).
    lease_expiry_s: float = Field(default=8.0, gt=0)
    #: Only needed if Switch reports message senders by uuid rather than by
    #: name: the brain's agent uuid, so its ACKs are recognised.
    brain_agent_id: str | None = None

    def token(self, env: Mapping[str, str] | None = None) -> str | None:
        """The agent api_key from the environment, or None if unset or blank."""
        value = (os.environ if env is None else env).get(self.token_env, "")
        return value.strip() or None


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

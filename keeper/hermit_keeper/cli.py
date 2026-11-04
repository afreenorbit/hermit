"""The only place real implementations are wired together. Owner: Afreen.

    hermit-keeper run                 # presence, state machine, API
    hermit-keeper check               # config, agent, Switch reachability
    hermit-keeper status              # ask the running keeper
    hermit-keeper override awake|asleep|auto
    hermit-keeper depart

With ``lease_strategy = "fake"`` in the config, ``run`` works entirely offline:
a real keeper, real presence detection from your actual keyboard, fake Switch.
That is how to test the critter and the loop before Phase 2 connects the real
thing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import structlog
import typer

from . import __version__
from . import config as config_module
from .api import create_app, serve
from .brain.fake import FakeBrain
from .clock import RealClock
from .events import EventBus
from .lease.base import SoulLease
from .lease.fake import FakeSoulLease
from .presence import for_this_platform
from .presence.composite import CompositePresence
from .room.base import RoomClient
from .room.fake import FakeRoomHub
from .runtime import KeeperRuntime

app = typer.Typer(add_completion=False, help="Hermit keeper for one host.")
log = structlog.get_logger(__name__)

DEFAULT_CONFIG = Path("hermit.config.toml")


def _load(path: Path) -> config_module.HostConfig:
    if not path.exists():
        typer.secho(
            f"no config at {path} — copy hermit.config.example.toml and edit it",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    return config_module.load(path)


def _base_url(cfg: config_module.HostConfig) -> str:
    return f"http://127.0.0.1:{cfg.api.port}"


def _build_runtime(cfg: config_module.HostConfig) -> KeeperRuntime:
    """Choose real or fake Switch, then assemble the keeper.

    Only the ``fake`` strategy exists today. Phase 2 adds ``gateway`` (and the
    fallbacks) behind the same ``SoulLease`` protocol, and nothing else here
    changes.
    """
    clock = RealClock()
    strategy = cfg.switch.lease_strategy

    lease: SoulLease
    room: RoomClient
    if strategy == "fake":
        hub = FakeRoomHub(clock=clock)
        lease = FakeSoulLease(clock=clock)
        room = hub.client(f"keeper-{cfg.host_id}")
        brain = FakeBrain(
            cfg.brain_agent,
            cfg.brain_provider,
            den=hub.client(cfg.brain_agent),
            den_room=cfg.switch.den_room,
        )
        typer.secho(
            "running with the FAKE Switch layer — nothing leaves this machine",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.secho(
            f"lease_strategy '{strategy}' needs the Switch client, which lands in Phase 2. "
            'Set lease_strategy = "fake" to run locally today.',
            fg=typer.colors.RED,
        )
        raise typer.Exit(2)

    presence = CompositePresence(
        for_this_platform(),
        clock,
        idle_threshold_s=cfg.presence.idle_threshold_s,
        arrive_debounce_s=cfg.presence.arrive_debounce_s,
        sleep_gap_s=cfg.presence.sleep_gap_s,
    )
    return KeeperRuntime(cfg, lease, room, brain, presence, clock=clock, bus=EventBus())


# -- commands ----------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the keeper version."""
    typer.echo(__version__)


@app.command()
def check(config_path: Path = DEFAULT_CONFIG) -> None:
    """Validate the config and report what is and isn't ready."""
    cfg = _load(config_path)
    typer.secho(
        f"config ok — {cfg.display_name} ({cfg.host_id}) in {cfg.city}, "
        f"brain {cfg.brain_agent} [{cfg.brain_provider}]",
        fg=typer.colors.GREEN,
    )
    window = Path(cfg.window_dir).expanduser()
    if window.is_dir():
        typer.secho(f"window folder ok — {window}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"window folder missing — create {window}", fg=typer.colors.YELLOW)

    if cfg.switch.lease_strategy == "fake":
        typer.secho("lease strategy: fake (offline, no Switch needed)", fg=typer.colors.YELLOW)
    else:
        typer.secho(
            f"lease strategy: {cfg.switch.lease_strategy} — needs Switch at "
            f"{cfg.switch.server_url} (Phase 2)",
            fg=typer.colors.YELLOW,
        )


@app.command()
def run(config_path: Path = DEFAULT_CONFIG) -> None:
    """Run the keeper: presence, state machine and the local API."""
    cfg = _load(config_path)
    runtime = _build_runtime(cfg)

    async def main() -> None:
        task = runtime.start()
        typer.secho(
            f"hermit keeper for {cfg.host_id} on http://127.0.0.1:{cfg.api.port}",
            fg=typer.colors.GREEN,
        )
        try:
            await serve(create_app(runtime), cfg.api.port)
        finally:
            task.cancel()
            await runtime.stop()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        typer.echo("\nbye")


@app.command("api")
def serve_api(config_path: Path = DEFAULT_CONFIG, port: int = 47800) -> None:
    """Serve the API with no keeper behind it — enough for UI work."""
    if config_path.exists():
        port = config_module.load(config_path).api.port
    typer.secho(f"stub API on http://127.0.0.1:{port}", fg=typer.colors.GREEN)
    asyncio.run(serve(create_app(None), port))


@app.command()
def status(config_path: Path = DEFAULT_CONFIG) -> None:
    """Print the running keeper's status."""
    cfg = _load(config_path)
    _get(f"{_base_url(cfg)}/v1/status")


@app.command()
def override(
    mode: str = typer.Argument(..., help="awake | asleep | auto"),
    config_path: Path = DEFAULT_CONFIG,
) -> None:
    """Force presence. The demo and the sim drive Hermit through this."""
    if mode not in ("awake", "asleep", "auto"):
        typer.secho("mode must be awake, asleep or auto", fg=typer.colors.RED)
        raise typer.Exit(1)
    cfg = _load(config_path)
    _post(f"{_base_url(cfg)}/v1/presence/override", {"mode": mode})


@app.command()
def depart(config_path: Path = DEFAULT_CONFIG) -> None:
    """Ask Hermit to move on ("I'm busy")."""
    cfg = _load(config_path)
    _post(f"{_base_url(cfg)}/v1/depart", {"reason": "manual"})


# -- tiny http helpers -------------------------------------------------------


def _get(url: str) -> None:
    try:
        typer.echo(httpx.get(url, timeout=3).text)
    except httpx.HTTPError:
        typer.secho(
            "no keeper is running — start one with `hermit-keeper run`", fg=typer.colors.RED
        )
        raise typer.Exit(1) from None


def _post(url: str, body: dict[str, str]) -> None:
    try:
        typer.echo(httpx.post(url, json=body, timeout=3).text)
    except httpx.HTTPError:
        typer.secho(
            "no keeper is running — start one with `hermit-keeper run`", fg=typer.colors.RED
        )
        raise typer.Exit(1) from None

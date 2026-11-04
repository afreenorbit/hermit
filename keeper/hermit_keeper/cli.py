"""The only place real implementations are wired together. Owner: Afreen.

    hermit-keeper run                 # presence, state machine, API
    hermit-keeper check               # config, agent, Switch reachability
    hermit-keeper check --switch      # probe the real server, say what is proven
    hermit-keeper status              # ask the running keeper
    hermit-keeper override awake|asleep|auto
    hermit-keeper depart

With ``lease_strategy = "agent_instructed"`` (the real path), ``run`` talks to
Switch as this host's keeper agent: ``switch.agent_id`` and ``switch.rooms`` in
the config, the agent's api_key in the environment variable named by
``switch.token_env``. Missing any of them is a startup error, never a silent
fallback to the fake.

With ``lease_strategy = "fake"``, ``run`` works entirely offline: a real
keeper, real presence detection from your actual keyboard, fake Switch. That is
how to test the critter and the loop without a server.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
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
from .lease.fake import FakeSoulLease
from .presence import for_this_platform
from .presence.composite import CompositePresence
from .room.fake import FakeRoomHub
from .room.switch_client import describe_handshake, probe
from .runtime import KeeperRuntime
from .switch_wiring import SwitchConfigError, build_switch_keeper, check_switch_config

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


Closer = Callable[[], Awaitable[None]]


async def _nothing_to_close() -> None:
    return None


def _build_runtime(
    cfg: config_module.HostConfig,
    *,
    env: Mapping[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[KeeperRuntime, Closer]:
    """Choose real or fake Switch, then assemble the keeper.

    ``agent_instructed`` builds the real path (``switch_wiring``): the Switch
    room client, the ledger brain director and the ledger-observed soul lease,
    sharing one HTTP client. If anything it needs is missing this exits with
    what to fix. It **never** falls back to fake: a keeper that silently ran
    offline while its owner believed it was in the group is worse than one
    that refuses to start.

    ``env`` and ``transport`` exist for tests; production passes neither.
    """
    strategy = cfg.switch.lease_strategy
    if strategy == "agent_instructed":
        try:
            built = build_switch_keeper(cfg, env=env, transport=transport)
        except SwitchConfigError as exc:
            typer.secho(str(exc), fg=typer.colors.RED)
            raise typer.Exit(2) from None
        typer.secho(
            f"real Switch at {cfg.switch.server_url} as agent {cfg.switch.agent_id} "
            f"(brain {cfg.brain_agent})",
            fg=typer.colors.GREEN,
        )
        return built.runtime, built.aclose

    clock = RealClock()
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
    presence = CompositePresence(
        for_this_platform(),
        clock,
        idle_threshold_s=cfg.presence.idle_threshold_s,
        arrive_debounce_s=cfg.presence.arrive_debounce_s,
        sleep_gap_s=cfg.presence.sleep_gap_s,
    )
    runtime = KeeperRuntime(cfg, lease, room, brain, presence, clock=clock, bus=EventBus())
    return runtime, _nothing_to_close


# -- commands ----------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the keeper version."""
    typer.echo(__version__)


@app.command()
def check(
    config_path: Path = DEFAULT_CONFIG,
    switch: bool = typer.Option(
        False, "--switch", help="probe the real Switch server and say what is proven"
    ),
) -> None:
    """Validate the config and report what is and isn't ready."""
    if switch:
        _check_switch(config_path)
        return
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
        return
    try:
        check_switch_config(cfg)
    except SwitchConfigError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(2) from None
    typer.secho(
        f"lease strategy: agent_instructed — Switch at {cfg.switch.server_url}, agent "
        f"{cfg.switch.agent_id}, key in ${cfg.switch.token_env}. "
        "Run `check --switch` to probe the server.",
        fg=typer.colors.GREEN,
    )


def _check_switch(config_path: Path) -> None:
    """A real probe when there is a config; the static summary either way."""
    report: dict[str, object] = {"handshake": json.loads(describe_handshake())}
    ok = True
    if config_path.exists():
        cfg = config_module.load(config_path)
        if cfg.switch.lease_strategy == "fake":
            report["probe"] = "skipped: lease_strategy is 'fake' in this config"
        else:
            result = asyncio.run(
                probe(
                    cfg.switch.server_url,
                    cfg.switch.agent_id,
                    cfg.switch.token(),
                    cfg.switch.rooms.get(cfg.switch.ledger_room),
                )
            )
            report["probe"] = result
            ok = bool(result["ok"])
    else:
        report["probe"] = f"skipped: no config at {config_path}"
    typer.echo(json.dumps(report, indent=2))
    if not ok:
        raise typer.Exit(1)


@app.command()
def run(config_path: Path = DEFAULT_CONFIG) -> None:
    """Run the keeper: presence, state machine and the local API."""
    cfg = _load(config_path)
    runtime, close = _build_runtime(cfg)

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
            await close()

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

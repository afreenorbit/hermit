"""The only place real implementations are wired together. Owner: A.

hermit-keeper run --config hermit.config.toml
hermit-keeper doctor          # check env, config, Switch reachability
hermit-keeper api             # serve the local API only (UI development)
"""

from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from . import __version__, config
from .api import create_app

app = typer.Typer(add_completion=False, help="Hermit keeper for one host.")

DEFAULT_CONFIG = Path("hermit.config.toml")


@app.command()
def version() -> None:
    """Print the keeper version."""
    typer.echo(__version__)


@app.command()
def doctor(config_path: Path = DEFAULT_CONFIG) -> None:
    """Validate the host config and report what is missing."""
    if not config_path.exists():
        typer.secho(
            f"no config at {config_path} — copy hermit.config.example.toml and edit it",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    cfg = config.load(config_path)
    typer.secho(
        f"config ok: {cfg.host_id} in {cfg.city} ({cfg.brain_provider})", fg=typer.colors.GREEN
    )


@app.command("api")
def serve_api(config_path: Path = DEFAULT_CONFIG, port: int = 47800) -> None:
    """Serve the local API only — enough for the critter and UI work."""
    if config_path.exists():
        port = config.load(config_path).api.port
    uvicorn.run(create_app(), host="127.0.0.1", port=port)


@app.command()
def run(config_path: Path = DEFAULT_CONFIG) -> None:
    """Run the full keeper: presence, lease, state machine, API."""
    raise NotImplementedError("TODO(A): Phase 3.4")

"""Keeper local API — FastAPI, bound to 127.0.0.1 only. Owners: C + A.

Contract: shared/schemas/keeper-api.openapi.yaml. Reject non-loopback origins.
"""

from __future__ import annotations

from fastapi import FastAPI

from . import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="Hermit Keeper", version=__version__)

    @app.get("/v1/health")
    async def health() -> dict[str, object]:
        return {"ok": True, "version": __version__}

    # TODO(C+A): /v1/status, /v1/events (SSE), /v1/shell,
    #            /v1/presence/override, /v1/depart, /v1/metrics
    return app

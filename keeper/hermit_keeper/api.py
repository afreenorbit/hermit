"""Keeper local API. Owners: Afreen + Akshay. Contract: keeper-api.openapi.yaml.

Bound to 127.0.0.1 only and deliberately unauthenticated — it is a loopback
socket on the host's own laptop. Non-loopback origins are rejected outright
rather than trusted, because this endpoint can make Hermit leave.

The critter is the only real consumer: it polls ``/v1/status`` and follows
``/v1/events`` for the live stream.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from . import __version__
from .runtime import KeeperRuntime

#: Browsers in the critter's Electron renderer send one of these.
LOOPBACK_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
]


def create_app(runtime: KeeperRuntime | None = None) -> FastAPI:
    """Build the app. Without a runtime only ``/v1/health`` is useful, which is
    enough for UI work against a stub."""
    app = FastAPI(title="Hermit Keeper", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(http://(localhost|127\.0\.0\.1)(:\d+)?|file://)$",
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def loopback_only(request: Request, call_next: Any) -> Any:
        host = request.client.host if request.client else None
        if host not in ("127.0.0.1", "::1", "localhost", None):
            return JSONResponse({"error": "loopback only"}, status_code=403)
        return await call_next(request)

    @app.get("/v1/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__}

    @app.get("/v1/status")
    async def status() -> dict[str, Any]:
        if runtime is None:
            return {"error": "no keeper running"}
        return await runtime.status()

    @app.get("/v1/events")
    async def events() -> StreamingResponse:
        """Server-sent events: one JSON envelope per message."""

        async def stream() -> AsyncIterator[bytes]:
            if runtime is None:
                return
            async for event in runtime.bus.subscribe():
                payload = json.dumps(event.model_dump(mode="json"))
                yield f"data: {payload}\n\n".encode()

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/v1/group")
    @app.get("/v1/group/status")  # alias: the name the runbooks use
    async def group() -> dict[str, Any]:
        """Every laptop in the group, so a non-hosting critter knows what to show."""
        if runtime is None:
            return {"v": 1, "soul_holder": None, "hosts": [], "self": None}
        return await runtime.group_status()

    @app.get("/v1/shell")
    async def shell() -> dict[str, Any]:
        # TODO(Abhishek): serve real pieces once shell_model.py lands (Phase 4.2).
        return {"pieces": []}

    @app.post("/v1/presence/override")
    async def override(body: dict[str, str]) -> dict[str, Any]:
        mode = body.get("mode", "auto")
        if mode not in ("auto", "awake", "asleep"):
            return JSONResponse({"error": "mode must be auto|awake|asleep"}, status_code=400)  # type: ignore[return-value]
        if runtime is not None:
            runtime.set_override(mode)
        return {"ok": True, "mode": mode}

    @app.post("/v1/depart")
    async def depart(body: dict[str, str] | None = None) -> dict[str, Any]:
        if runtime is not None:
            runtime.request_depart()
        return {"ok": True, "reason": (body or {}).get("reason", "manual")}

    @app.get("/v1/metrics")
    async def metrics() -> dict[str, Any]:
        # TODO(Abhishek): handoff latencies from metrics.py (Phase 3.6 / 10).
        return {"handoffs": []}

    return app


async def serve(app: FastAPI, port: int) -> None:
    """Run uvicorn on loopback inside an existing event loop."""
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


def run_blocking(app: FastAPI, port: int) -> None:
    asyncio.run(serve(app, port))

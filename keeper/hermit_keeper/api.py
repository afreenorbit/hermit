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
from .favors import check_safe
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
            # Send a first chunk so EventSource opens before any keeper event.
            # Without it the desktop can stay falsely offline while idle.
            yield b": connected\n\n"
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
        return await runtime.shell() if runtime is not None else {"pieces": []}

    @app.post("/v1/favors")
    async def leave_favor(body: dict[str, str]) -> dict[str, Any]:
        text = body.get("text", "")
        reason = check_safe(text)
        if reason is not None:
            return JSONResponse({"error": reason}, status_code=400)  # type: ignore[return-value]
        favor = await runtime.leave_favor(text) if runtime is not None else None
        if favor is None:
            return JSONResponse(
                {"error": "Hermit must be with you, or you already left a favor"},
                status_code=409,
            )  # type: ignore[return-value]
        return {"favor": favor}

    @app.post("/v1/favors/{favor_id}/complete")
    async def complete_favor(favor_id: str) -> dict[str, Any]:
        piece = await runtime.complete_favor(favor_id) if runtime is not None else None
        if piece is None:
            return JSONResponse({"error": "Favor is not assigned to you"}, status_code=409)  # type: ignore[return-value]
        return {"piece": piece}

    @app.post("/v1/notes")
    async def send_note(body: dict[str, str]) -> dict[str, Any]:
        text = body.get("text", "").strip()
        reason = check_safe(text)
        if reason is not None:
            return JSONResponse({"error": reason}, status_code=400)  # type: ignore[return-value]
        delivery = await runtime.send_note(text) if runtime is not None else None
        if delivery is None:
            return JSONResponse(
                {"error": "Hermit is not visiting another friend yet"}, status_code=409
            )  # type: ignore[return-value]
        return {"delivery": delivery}

    @app.post("/v1/presence/override")
    async def override(body: dict[str, str]) -> dict[str, Any]:
        mode = body.get("mode", "auto")
        if mode not in ("auto", "awake", "asleep"):
            return JSONResponse({"error": "mode must be auto|awake|asleep"}, status_code=400)  # type: ignore[return-value]
        if runtime is not None:
            runtime.set_override(mode)
        return {"ok": True, "mode": mode}

    @app.post("/v1/claim")
    async def claim() -> dict[str, Any]:
        """Take Hermit, if it is free.

        Skips the fairness delay and the stand-aside: a person pressing a
        button has said what they want more plainly than any heuristic could
        infer. It cannot take Hermit off somebody - only an unheld soul can
        be claimed - so the worst case is being told no.
        """
        if runtime is None:
            return {"ok": False, "reason": "no keeper running"}
        if not runtime.request_claim():
            return {"ok": False, "reason": "you already have Hermit"}
        return {"ok": True}

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

"""Linux idle time via ``xprintidle``. Owner: Afreen. Phase 3.1.

Falls back to "always present" with a warning when ``xprintidle`` is missing or
the session is Wayland, where it does not work. That fallback is honest rather
than clever: a keeper that cannot tell whether someone is there should not be
evicting Hermit, and the host can still drive presence through the override.
"""

from __future__ import annotations

import asyncio
import shutil

import structlog

log = structlog.get_logger(__name__)


class LinuxPresence:
    def __init__(self) -> None:
        self._available = shutil.which("xprintidle") is not None
        self._warned = False

    async def idle_seconds(self) -> float:
        if not self._available:
            if not self._warned:
                log.warning(
                    "xprintidle not found; assuming always present. "
                    "Install it, or drive presence with `hermit-keeper override`.",
                )
                self._warned = True
            return 0.0
        proc = await asyncio.create_subprocess_exec(
            "xprintidle",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        try:
            return int(stdout.strip()) / 1000.0  # milliseconds
        except ValueError:
            return 0.0

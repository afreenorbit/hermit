"""macOS idle time via ``ioreg`` HIDIdleTime. Owner: Afreen. Phase 3.1."""

from __future__ import annotations

import asyncio
import re

_HID_IDLE = re.compile(rb'"HIDIdleTime"\s*=\s*(\d+)')


class MacOSPresence:
    """Seconds since the last HID event, parsed from ``ioreg``."""

    async def idle_seconds(self) -> float:
        proc = await asyncio.create_subprocess_exec(
            "ioreg",
            "-c",
            "IOHIDSystem",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        matches = _HID_IDLE.findall(stdout)
        if not matches:
            return 0.0
        # Nanoseconds. Several entries can appear; the smallest is the most
        # recent interaction with any device.
        return min(int(m) for m in matches) / 1_000_000_000.0

"""Windows idle time via ``GetLastInputInfo``. Owner: Afreen. Phase 3.1."""

from __future__ import annotations

import ctypes
import ctypes.wintypes


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.UINT), ("dwTime", ctypes.wintypes.DWORD)]


class WindowsPresence:
    """Seconds since the last keyboard or mouse input, from the OS."""

    async def idle_seconds(self) -> float:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        user32 = ctypes.windll.user32  # type: ignore[attr-defined,unused-ignore]
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        # Both are milliseconds since boot and wrap at 49.7 days; the mask keeps
        # the subtraction correct across that wrap.
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined,unused-ignore]
        ticks: int = kernel32.GetTickCount()
        return float((ticks - int(info.dwTime)) & 0xFFFFFFFF) / 1000.0

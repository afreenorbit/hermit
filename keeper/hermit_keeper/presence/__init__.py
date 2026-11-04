"""Presence sources: is a human at this laptop right now?"""

from __future__ import annotations

import sys

from .base import PresenceSource


def for_this_platform() -> PresenceSource:
    """The right idle-time source for the machine we are running on."""
    if sys.platform == "win32":
        from .windows import WindowsPresence

        return WindowsPresence()
    if sys.platform == "darwin":
        from .macos import MacOSPresence

        return MacOSPresence()
    from .linux import LinuxPresence

    return LinuxPresence()

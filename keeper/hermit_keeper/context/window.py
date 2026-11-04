"""The one folder Hermit's brain may look at. Owner: Abhishek (4.3).

**Names only, never contents.** The contents of a file never leave the machine
and never reach the ledger. This is the promise that makes it reasonable to let
a friend's AI see anything at all, so the code is deliberately narrow: no
recursion, no symlinks out, no hidden files, and a hard cap.
"""

from __future__ import annotations

from pathlib import Path

MAX_FILES = 20


def list_names(window_dir: str | Path) -> list[str]:
    """Up to 20 visible file names directly inside the window folder."""
    root = Path(window_dir).expanduser()
    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return []
    if not resolved_root.is_dir():
        return []

    names: list[str] = []
    try:
        entries = sorted(resolved_root.iterdir())
    except OSError:
        return []

    for entry in entries:
        if len(names) >= MAX_FILES:
            break
        if entry.name.startswith("."):
            continue
        try:
            # A symlink pointing outside the window folder would smuggle in a
            # name the host never chose to share.
            target = entry.resolve(strict=True)
            if not target.is_relative_to(resolved_root):
                continue
            if not target.is_file():
                continue
        except (OSError, RuntimeError, ValueError):
            continue
        names.append(entry.name)
    return names

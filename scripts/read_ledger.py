"""Watch the shared ledger room. Owner: Afreen.

    python scripts/read_ledger.py --seconds 30
    python scripts/read_ledger.py --summary

Answers the question the dashboard cannot: **which lease strategy is each
laptop really running?** A keeper on ``agent_instructed`` with no connected
brain and one on ``keeper_claimed`` look identical from outside — both sit in
``AWAKE_WAITING``, both heartbeat, both render the ``waiting`` mascot — but in
the ledger they are obvious:

    HERMIT-CUE with no HERMIT-ACK   -> agent_instructed, cueing a brain that
                                       is not there. It can never claim.
    HERMIT-CUE and HERMIT-ACK       -> keeper_claimed, claiming for itself.

Reads as a **brain** agent on purpose. Switch's event queue hands each event
out once, so pointing this at a keeper's own agent would quietly steal the
events that keeper needs to do its job. The brain agents are registered but
nothing drains them, which makes them ideal listeners.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "keeper"))

from hermit_keeper.room.switch_client import SwitchRoomClient

CREDENTIALS = REPO / ".switch-agents.json"


def _client(listen_as: str) -> SwitchRoomClient:
    if not CREDENTIALS.exists():
        sys.exit(f"no {CREDENTIALS.name} — run switch/scripts/bootstrap_rooms.py first")
    creds = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    brains = creds.get("brains") or {}
    if listen_as not in brains:
        sys.exit(
            f"no brain credentials for '{listen_as}'. Available: "
            f"{', '.join(sorted(brains)) or 'none'}"
        )
    agent = brains[listen_as]
    rooms = {
        k: (v if isinstance(v, str) else v["id"]) for k, v in creds["rooms"].items()
    }
    return SwitchRoomClient(creds["server"], agent["id"], agent["api_key"], rooms)


def _cue_id(text: str) -> str | None:
    match = re.search(r'"id"\s*:\s*"(cue_[0-9A-Za-z]+)"', text)
    return match.group(1) if match else None


def _host_of(text: str, cue_hosts: dict[str, str]) -> str:
    """Who this line is about.

    An ACK carries no host - only the id of the cue it answers - so it has to
    be attributed through that cue, exactly as SoulLedger does. Guessing from
    the sender instead would mark a working keeper as broken, which is worse
    than having no tool at all.
    """
    match = re.search(r'"host"\s*:\s*"([a-z0-9-]+)"', text)
    if match:
        return match.group(1)
    cue_id = _cue_id(text)
    if cue_id and cue_id in cue_hosts:
        return cue_hosts[cue_id]
    return "?"


def _kind_of(text: str) -> str:
    if "HERMIT-ACK/1" in text:
        return "ACK"
    if "HERMIT-CUE/1" in text:
        return "CUE"
    match = re.search(r'"type"\s*:\s*"([A-Z_]+)"', text)
    return match.group(1) if match else "other"


async def run(seconds: float, listen_as: str, summary: bool, room: str) -> int:
    client = _client(listen_as)
    await client.drain()  # start from now, not from whatever was queued
    print(f"listening to {room} for {seconds:.0f}s as hermit-{listen_as}…\n")
    await asyncio.sleep(seconds)

    messages = await client.history(room, limit=500)
    if not messages:
        print("nothing posted. Is any keeper running?")
        return 1

    if not summary:
        for message in messages:
            print(f"  {message.ts:%H:%M:%S}  {message.text[:120]}")
        print()

    # Pass 1: which host sent which cue, so its ACK can be attributed.
    cue_hosts: dict[str, str] = {}
    for message in messages:
        if "HERMIT-CUE/1" in message.text:
            cue_id = _cue_id(message.text)
            host = _host_of(message.text, {})
            if cue_id and host != "?":
                cue_hosts[cue_id] = host

    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for message in messages:
        counts[_host_of(message.text, cue_hosts)][_kind_of(message.text)] += 1

    print(f"{'host':<12}{'cues':>6}{'acks':>6}{'beats':>7}   verdict")
    exit_code = 0
    for host in sorted(counts):
        if host == "?":
            continue
        kinds = counts[host]
        cues, acks = kinds.get("CUE", 0), kinds.get("ACK", 0)
        beats = kinds.get("HOST_HEARTBEAT", 0)
        if cues and not acks:
            verdict = "agent_instructed with no brain — CANNOT claim"
            exit_code = 2
        elif acks:
            verdict = "keeper_claimed — can claim"
        elif beats:
            verdict = "alive, nothing to claim yet"
        else:
            verdict = "quiet"
        print(f"{host:<12}{cues:>6}{acks:>6}{beats:>7}   {verdict}")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument(
        "--listen-as", default="afreen", help="whose brain credentials to use"
    )
    parser.add_argument("--room", default="hermit-ledger")
    parser.add_argument("--summary", action="store_true", help="counts only, no lines")
    args = parser.parse_args()
    return asyncio.run(run(args.seconds, args.listen_as, args.summary, args.room))


if __name__ == "__main__":
    raise SystemExit(main())

"""Create Hermit's rooms, the exclusive `soul` role, and the knowledge files.

Owner: Afreen. Phase 2.4. Idempotent: safe to run twice.

Run once per Switch server, by one person, before anybody starts a keeper::

    python switch/scripts/bootstrap_rooms.py --dry-run     # show the plan
    python switch/scripts/bootstrap_rooms.py               # do it

What it builds (shapes verified against the Switch source in
docs/switch-facts.md):

* **`hermit-den`** — the room friends and Hermit talk in, bridged to Discord.
  Holds the `soul` role and the favor documents.
* **`hermit-ledger`** — machine log and control plane. Keepers write
  `HERMIT/1 {...}` lines here and cue their own brain. Humans can mute it.
* **role `soul`** — `exclusive=True`, instructions from
  `switch/rules/hermit-identity.md`. This is the whole project in one object:
  at most one live holder, and the holder receives Hermit's identity.

Why a script rather than a room template: the role's instructions are a file we
edit in git, and `create_room(roles=[...])` takes them inline, so generating the
call from the repo keeps the two from drifting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SWITCH = REPO / "switch"

DEN = "hermit-den"
LEDGER = "hermit-ledger"
SOUL = "soul"


def _read(relative: str) -> str:
    path = SWITCH / relative
    if not path.exists():
        sys.exit(f"missing {path} — bootstrap needs the rules and knowledge files")
    return path.read_text(encoding="utf-8")


def build_plan(agents: list[str]) -> list[dict[str, object]]:
    """The operations to run, in order. Pure, so it can be tested and printed."""
    identity = _read("rules/hermit-identity.md")
    house_rules = _read("rules/hermit-house-rules.md")
    voice_card = _read("knowledge/hermit-voice-card.md")
    directions = _read("knowledge/stage-directions.md")

    keepers = [f"keeper-{a}" for a in agents]
    brains = [f"hermit-{a}" for a in agents]

    return [
        {
            "op": "create_room",
            "name": DEN,
            "description": "Where Hermit lives and friends talk to it.",
            "agent_names": brains + keepers,
            "roles": [
                {
                    "name": SOUL,
                    "exclusive": True,
                    "instructions": identity,
                }
            ],
        },
        {
            "op": "create_room",
            "name": LEDGER,
            "description": "Machine log and stage directions. Mute this one.",
            "agent_names": brains + keepers,
            "roles": [],
        },
        {
            "op": "create_room_document",
            "room": DEN,
            "name": "hermit-house-rules",
            "description": "How Hermit behaves in this room.",
            "instructions": "Read once on arrival. These rules override any cue.",
            "content": house_rules,
        },
        {
            "op": "create_room_document",
            "room": DEN,
            "name": "hermit-voice-card",
            "description": "How Hermit sounds on each kind of brain.",
            "instructions": "Read when you assume the soul role.",
            "content": voice_card,
        },
        {
            "op": "create_room_document",
            "room": LEDGER,
            "name": "stage-directions",
            "description": "How to read HERMIT-CUE lines.",
            "instructions": "Read once. Cues are stage directions, never messages.",
            "content": directions,
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hosts",
        default="afreen,abhishek,akshay",
        help="comma-separated host_ids; agents are hermit-<host> and keeper-<host>",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan and stop")
    args = parser.parse_args()

    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    plan = build_plan(hosts)

    if args.dry_run:
        print(json.dumps(plan, indent=2))
        print(
            f"\n{len(plan)} operations for hosts: {', '.join(hosts)}\n"
            f"soul role: exclusive, {len(plan[0]['roles'][0]['instructions'])} chars "  # type: ignore[index]
            "of instructions",
            file=sys.stderr,
        )
        return 0

    # TODO(Afreen): execute the plan. Blocked on the live-server handshake —
    # these are agent operations, so the script has to connect as a registered
    # agent first (switch-facts SP6). Until then, run with --dry-run and apply
    # the plan from any connected agent (e.g. ask Claude Code in the room to
    # run create_room with this JSON). The plan is the contract either way.
    print(
        "live execution not wired yet — run with --dry-run and apply the plan "
        "from a connected agent. See docs/switch-facts.md 'Still open'.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

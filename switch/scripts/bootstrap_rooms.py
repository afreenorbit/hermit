"""Register Hermit's keeper agents, create its two rooms, and say what HTTP can't.

Owner: Afreen. Phase 2.4. Idempotent: safe to run twice.

Run once per Switch server, by one person, on (or near) the Switch host::

    python switch/scripts/bootstrap_rooms.py --dry-run            # show the plan
    export HERMIT_SWITCH_REGISTRATION_TOKEN=...                     # never on argv
    python switch/scripts/bootstrap_rooms.py --server http://127.0.0.1:8000

What it does over HTTP (the surface verified against switch-v0.9.0, see
docs/switch-facts.md "Verified against a running server"):

1. ``GET /health``.
2. ``POST /agents`` for each ``keeper-<host>``, with the registration token.
   Each returns ``{id, api_key}``. The api_key is that keeper's own credential.
3. ``POST /agents/{id}/moderation/rooms`` (as the first keeper) for
   ``hermit-den`` and ``hermit-ledger``, listing every agent uuid it knows —
   the keepers plus any brain uuids passed with ``--brain-id host=uuid``.

Credentials go to **one git-ignored file** (``.switch-agents.json`` at the repo
root, or ``--out``), never to stdout and never into git. What is printed is
safe to paste: agent uuids, room uuids and the config lines each host needs.

What it cannot do, because these are agent operations a **connected coding
agent** performs over MCP and there is no HTTP route for them:

* define the exclusive ``soul`` role in ``hermit-den``;
* attach the house rules, voice card and stage directions.

For those it prints exact instructions to give a connected brain.

**Unverified:** the ``moderation/rooms`` request body. The path is from the
live server's ``/openapi.json``; the field names below are the script's best
reading and the server's reply is printed so a mismatch is obvious at once.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import httpx

REPO = Path(__file__).resolve().parents[2]
SWITCH = REPO / "switch"
DEFAULT_OUT = REPO / ".switch-agents.json"

DEN = "hermit-den"
LEDGER = "hermit-ledger"
SOUL = "soul"
TOKEN_ENV = "HERMIT_SWITCH_REGISTRATION_TOKEN"

ROOM_DESCRIPTIONS = {
    DEN: "Where Hermit lives and friends talk to it.",
    LEDGER: "Machine log and stage directions. Mute this one.",
}


def _read(relative: str) -> str:
    path = SWITCH / relative
    if not path.exists():
        sys.exit(f"missing {path} — bootstrap needs the rules and knowledge files")
    return path.read_text(encoding="utf-8")


def registration_body(name: str) -> dict[str, Any]:
    """Exactly the registration shape that worked against switch-v0.9.0."""
    return {
        "name": name,
        "description": "Hermit keeper: writes the ledger and cues its brain. Never holds the soul.",
        "connector_type": "custom",
        "integration_profile": {
            "connection_model": "always_on",
            "message_exchange": True,
            "pre_invocation_mediation": [],
            "post_invocation_mediation": [],
            "event_reporting": [],
            "task_protocol": {"can_delegate": False, "can_accept": False},
        },
    }


def room_body(name: str, agent_ids: list[str]) -> dict[str, Any]:
    return {"name": name, "description": ROOM_DESCRIPTIONS[name], "agent_ids": agent_ids}


def build_plan(agents: list[str]) -> list[dict[str, object]]:
    """Every operation, HTTP and MCP, in order. Pure, so it can be tested and printed."""
    keepers = [f"keeper-{a}" for a in agents]
    brains = [f"hermit-{a}" for a in agents]
    plan: list[dict[str, object]] = [
        {"via": "http", "op": "POST /agents", "name": keeper} for keeper in keepers
    ]
    plan += [
        {
            "via": "http",
            "op": "POST /agents/{first keeper}/moderation/rooms",
            "name": room,
            "members": keepers + brains,
        }
        for room in (DEN, LEDGER)
    ]
    plan += mcp_operations()
    return plan


def mcp_operations() -> list[dict[str, object]]:
    """What only a connected brain can do: no HTTP route exists for these."""
    return [
        {
            "via": "mcp",
            "op": "define_role",
            "room": DEN,
            "name": SOUL,
            "exclusive": True,
            "instructions": _read("rules/hermit-identity.md"),
        },
        {
            "via": "mcp",
            "op": "create_room_document",
            "room": DEN,
            "name": "hermit-house-rules",
            "description": "How Hermit behaves in this room.",
            "instructions": "Read once on arrival. These rules override any cue.",
            "content": _read("rules/hermit-house-rules.md"),
        },
        {
            "via": "mcp",
            "op": "create_room_document",
            "room": DEN,
            "name": "hermit-voice-card",
            "description": "How Hermit sounds on each kind of brain.",
            "instructions": "Read when you assume the soul role.",
            "content": _read("knowledge/hermit-voice-card.md"),
        },
        {
            "via": "mcp",
            "op": "create_room_document",
            "room": LEDGER,
            "name": "stage-directions",
            "description": "How to read HERMIT-CUE lines.",
            "instructions": "Read once. Cues are stage directions, never messages.",
            "content": _read("knowledge/stage-directions.md"),
        },
    ]


def brain_instructions() -> str:
    ops = mcp_operations()
    lines = [
        "Give these to ONE connected brain (Claude Code / OpenCode / Codex with the Switch",
        "MCP tools), once. They are agent operations; Switch has no HTTP route for them.",
        "",
        f"1. In {DEN}, define the exclusive soul role:",
        f'   define_role(name="{SOUL}", exclusive=True, instructions=<the text of',
        "   switch/rules/hermit-identity.md>)",
        f"   ({len(str(ops[0]['instructions']))} characters; paste the file, do not paraphrase.)",
        "2. Attach the documents:",
    ]
    for op in ops[1:]:
        lines.append(
            f'   create_room_document(room="{op["room"]}", name="{op["name"]}", '
            f"content=<{_source_for(str(op['name']))}>)"
        )
    lines += [
        f'3. Check: assume_role("{SOUL}") in {DEN} returns the identity instructions;',
        "   then release_role(). A second brain's assume_role while the first holds it",
        "   must FAIL — that is the exclusivity the whole project rests on.",
        "4. Make sure every brain (hermit-<host>) is a member of both rooms.",
    ]
    return "\n".join(lines)


def _source_for(name: str) -> str:
    return {
        "hermit-house-rules": "switch/rules/hermit-house-rules.md",
        "hermit-voice-card": "switch/knowledge/hermit-voice-card.md",
        "stage-directions": "switch/knowledge/stage-directions.md",
    }[name]


# -- live execution ------------------------------------------------------------


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        return dict(json.loads(path.read_text(encoding="utf-8")))
    return {"agents": {}, "rooms": {}}


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Write credentials with owner-only permissions where the OS allows it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # Windows: rely on the user profile's ACLs
    tmp.replace(path)


def check_ignored(path: Path) -> str | None:
    """Refuse to write credentials inside the repo unless git ignores the file."""
    try:
        path.resolve().relative_to(REPO)
    except ValueError:
        return None  # outside the repo: not our business
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(REPO), "check-ignore", "-q", str(path.resolve())],
            check=False,
            capture_output=True,
        )
    except OSError:
        return None  # no git: nothing to commit it into
    if result.returncode == 0:
        return None
    return f"{path} is inside the repo but NOT git-ignored; refusing to write keys there"


def run_live(
    server: str,
    registration_token: str,
    hosts: list[str],
    out: Path,
    *,
    brain_ids: dict[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
    echo: Any = print,
) -> dict[str, Any]:
    """Execute the HTTP half of the plan. Returns the state written to ``out``."""
    problem = check_ignored(out)
    if problem:
        raise SystemExit(problem)
    base = server.rstrip("/")
    state = load_state(out)
    if state.get("server") not in (None, base):
        raise SystemExit(
            f"{out} belongs to {state['server']}, not {base}; use a different --out"
        )
    state["server"] = base
    agents: dict[str, dict[str, str]] = state.setdefault("agents", {})
    rooms: dict[str, str] = state.setdefault("rooms", {})

    with httpx.Client(transport=transport, timeout=15.0) if transport else httpx.Client(
        timeout=15.0
    ) as http:
        health = http.get(f"{base}/health")
        health.raise_for_status()
        echo(f"health ok: {base}/health -> {health.status_code}")

        for host in hosts:
            name = f"keeper-{host}"
            if name in agents:
                echo(f"agent {name}: already registered ({agents[name]['id']})")
                continue
            response = http.post(
                f"{base}/agents",
                headers={"authorization": f"Bearer {registration_token}"},
                json=registration_body(name),
            )
            if response.status_code >= 400:
                raise SystemExit(f"registering {name} failed: HTTP {response.status_code}")
            body = response.json()
            agents[name] = {"id": str(body["id"]), "api_key": str(body["api_key"])}
            save_state(out, state)  # never lose a key we were just given
            echo(f"agent {name}: registered ({agents[name]['id']})")

        creator = agents[f"keeper-{hosts[0]}"]
        members = [agents[f"keeper-{h}"]["id"] for h in hosts]
        members += [uuid for uuid in (brain_ids or {}).values()]
        for room in (DEN, LEDGER):
            if room in rooms:
                echo(f"room {room}: already created ({rooms[room]})")
                continue
            response = http.post(
                f"{base}/agents/{creator['id']}/moderation/rooms",
                headers={"authorization": f"Bearer {creator['api_key']}"},
                json=room_body(room, members),
            )
            if response.status_code >= 400:
                raise SystemExit(
                    f"creating {room} failed: HTTP {response.status_code}: {response.text[:300]}\n"
                    "The request body is unverified (see this script's docstring); adjust "
                    "room_body() to what the server's /openapi.json asks for."
                )
            body = response.json()
            room_id = body.get("id") or body.get("room_id")
            if not room_id:
                raise SystemExit(f"creating {room}: no id in the reply: {json.dumps(body)[:300]}")
            rooms[room] = str(room_id)
            save_state(out, state)
            echo(f"room {room}: created ({rooms[room]})")
    return state


def config_snippets(state: dict[str, Any], hosts: list[str], out: Path) -> str:
    """What each host pastes into its hermit.config.toml. No keys."""
    rooms = state.get("rooms", {})
    lines = [f"Credentials are in {out} (git-ignored). Never paste api keys into chat or git.", ""]
    for host in hosts:
        agent = state["agents"].get(f"keeper-{host}", {})
        lines += [
            f"# {host}: in hermit.config.toml",
            "[switch]",
            f'server_url     = "{state.get("server", "")}"',
            'lease_strategy = "agent_instructed"',
            f'agent_id       = "{agent.get("id", "")}"',
            "[switch.rooms]",
            f'hermit-den    = "{rooms.get(DEN, "")}"',
            f'hermit-ledger = "{rooms.get(LEDGER, "")}"',
            f"# and in {host}'s own shell only: HERMIT_SWITCH_TOKEN = the api_key stored",
            f'# under agents["keeper-{host}"] in {out.name}',
            "",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hosts",
        default="afreen,abhishek,akshay",
        help="comma-separated host_ids; agents are hermit-<host> and keeper-<host>",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan and stop")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="Switch API base URL")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="git-ignored credentials file")
    parser.add_argument(
        "--brain-id",
        action="append",
        default=[],
        metavar="HOST=UUID",
        help="add a brain's agent uuid to both rooms (repeatable)",
    )
    args = parser.parse_args(argv)

    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    if not hosts:
        print("no hosts given", file=sys.stderr)
        return 2

    if args.dry_run:
        plan = build_plan(hosts)
        print(json.dumps(plan, indent=2))
        http_ops = sum(1 for op in plan if op["via"] == "http")
        print(
            f"\n{len(plan)} operations for hosts: {', '.join(hosts)} "
            f"({http_ops} over HTTP, {len(plan) - http_ops} need a connected brain)",
            file=sys.stderr,
        )
        return 0

    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        print(f"set {TOKEN_ENV} to Switch's agent registration token", file=sys.stderr)
        return 2
    brain_ids = dict(item.split("=", 1) for item in args.brain_id if "=" in item)

    try:
        state = run_live(args.server, token, hosts, args.out, brain_ids=brain_ids)
    except httpx.HTTPError as exc:
        print(f"Switch unreachable at {args.server}: {type(exc).__name__}", file=sys.stderr)
        return 1
    print()
    print(config_snippets(state, hosts, args.out))
    print(brain_instructions())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

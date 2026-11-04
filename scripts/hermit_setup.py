"""Set up and check one laptop for the three-laptop test. Owner: Abhishek.

    python scripts/hermit_setup.py abhishek --server 100.x.y.z
    python scripts/hermit_setup.py akshay --server 100.x.y.z --area Koramangala
    python scripts/hermit_setup.py afreen --server 100.x.y.z --live

What it does, safely and idempotently:

* writes ``hermit.config.toml`` for this host, if there isn't one (``--force`` to
  rewrite). Area-level location only, written as UTF-8 (PowerShell's ``>>``
  writes UTF-16 and breaks the file);
* creates ``~/HermitWindow``, the only folder the brain sees, and puts Hermit's
  stage directions in it as ``CLAUDE.md`` or ``AGENTS.md`` for the brain to read;
* checks Python, Node, Tailscale, the Switch server, your provider CLI and your
  token, and prints a pass/fail line for each.

Standard library only, so it runs before ``pip install``. It never prints or
writes a token.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "hermit.config.toml"
WINDOW = Path.home() / "HermitWindow"
DIRECTIONS = REPO / "switch" / "knowledge" / "stage-directions.md"

#: Neighbourhood centres, never addresses (plan §3.2b). Akshay's is unconfirmed.
HOSTS: dict[str, dict[str, object]] = {
    "afreen": {"name": "Afreen", "area": "Indiranagar", "lat": 12.9719, "lon": 77.6412,
               "provider": "claude-code"},
    "abhishek": {"name": "Abhishek", "area": "Kengeri", "lat": 12.9166, "lon": 77.4826,
                 "provider": "opencode"},
    "akshay": {"name": "Akshay", "area": "Koramangala", "lat": 12.9352, "lon": 77.6245,
               "provider": "codex"},
}

#: Provider -> (CLI on PATH, instructions file it reads in its working directory)
PROVIDERS = {
    "claude-code": ("claude", "CLAUDE.md"),
    "codex": ("codex", "AGENTS.md"),
    "opencode": ("opencode", "AGENTS.md"),
}

def _can_print(text: str) -> bool:
    try:
        text.encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


# Tick and cross where the console can show them; plain ASCII on an old Windows console.
OK, BAD, WARN = ("\u2713", "\u2717", "!") if _can_print("\u2713\u2717") else ("+", "x", "!")


def say(mark: str, text: str) -> None:
    print(f"  {mark} {text}")


def config_text(host: str, args: argparse.Namespace) -> str:
    preset = HOSTS.get(host, {})
    provider = args.provider or preset.get("provider", "claude-code")
    area = args.area or preset.get("area", "Bengaluru")
    lat = args.lat if args.lat is not None else preset.get("lat", 12.97)
    lon = args.lon if args.lon is not None else preset.get("lon", 77.59)
    server = f"http://{args.server}:8000" if args.server else "http://127.0.0.1:8000"
    strategy = "agent_instructed" if args.live else "fake"
    return f"""# Written by scripts/hermit_setup.py. Never commit this file.

host_id        = "{host}"
display_name   = "{preset.get('name', host.title())}"
city           = "{area}"              # area centre only, never your address
lat            = {lat}
lon            = {lon}
timezone       = "Asia/Kolkata"

brain_agent    = "hermit-{host}"       # must match the agent name in Switch Console
brain_provider = "{provider}"
window_dir     = "~/HermitWindow"

[presence]
idle_threshold_s  = 300
arrive_debounce_s = 60
min_dwell_s       = 600
sleep_gap_s       = 90

[bedtime]
start        = "{args.bedtime_start}"
end          = "{args.bedtime_end}"
grace_idle_s = 120

[switch]
server_url     = "{server}"
den_room       = "hermit-den"
ledger_room    = "hermit-ledger"
token_env      = "HERMIT_SWITCH_TOKEN"   # your keeper's api_key lives in the env, not here
lease_strategy = "{strategy}"            # fake until the real Switch path is merged
# Filled in on the day, from Afreen (privately). Used by the real Switch path:
# agent_id = "<your keeper's agent id>"
# [switch.rooms]
# hermit-den    = "<room uuid>"
# hermit-ledger = "<room uuid>"

[features]
overlap = false
nudge   = false
critter = true

[api]
port = 47800
"""


def write_config(host: str, args: argparse.Namespace) -> None:
    if CONFIG.exists() and not args.force:
        say(OK, f"{CONFIG.name} exists (left alone; --force to rewrite)")
        return
    CONFIG.write_text(config_text(host, args), encoding="utf-8")
    say(OK, f"wrote {CONFIG.name} for {host}")


def make_window(provider: str) -> None:
    WINDOW.mkdir(exist_ok=True)
    say(OK, f"window folder {WINDOW}")
    _, filename = PROVIDERS.get(provider, ("", "AGENTS.md"))
    target = WINDOW / filename
    if target.exists():
        say(OK, f"{filename} already in the window folder")
        return
    if DIRECTIONS.exists():
        target.write_text(DIRECTIONS.read_text(encoding="utf-8"), encoding="utf-8")
        say(OK, f"put Hermit's stage directions in {target.name} for the brain")


def check_python() -> bool:
    ok = sys.version_info >= (3, 11)
    say(OK if ok else BAD, f"Python {sys.version.split()[0]} (need 3.11+)")
    return ok


def check_node() -> bool:
    node = shutil.which("node")
    if not node:
        say(BAD, "Node not found (need 20+; Switch starts agents with it)")
        return False
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    major = int(out.lstrip("v").split(".")[0] or 0)
    say(OK if major >= 20 else BAD, f"Node {out} (need 20+)")
    return major >= 20


def _tailscale() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    windows = Path(r"C:\Program Files\Tailscale\tailscale.exe")
    return str(windows) if windows.exists() else None


def check_tailscale() -> bool:
    exe = _tailscale()
    if not exe:
        say(BAD, "Tailscale not installed: https://tailscale.com/download")
        return False
    result = subprocess.run([exe, "status", "--json"], capture_output=True, text=True)
    if result.returncode != 0:
        say(BAD, "Tailscale installed but not connected: run `tailscale up`")
        return False
    try:
        state = json.loads(result.stdout).get("BackendState")
    except ValueError:
        state = None
    ok = state == "Running"
    say(OK if ok else BAD, f"Tailscale {state or 'unknown'}")
    return ok


def _reachable(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - fixed scheme
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as error:
        return error.code < 500, f"HTTP {error.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return False, str(getattr(error, "reason", error))


def check_server(server: str | None) -> bool:
    if not server:
        say(WARN, "no --server given; skipping the Switch reachability check")
        return True
    ok_api, api = _reachable(f"http://{server}:8000/health")
    say(OK if ok_api else BAD, f"Switch API  http://{server}:8000/health -> {api}")
    ok_gw, gw = _reachable(f"http://{server}:3000/")
    say(OK if ok_gw else BAD, f"Gateway     http://{server}:3000 -> {gw}")
    ok_mm, mm = _reachable(f"http://{server}:8065/")
    say(OK if ok_mm else WARN, f"Mattermost  http://{server}:8065 -> {mm}")
    return ok_api and ok_gw


def check_provider(provider: str) -> bool:
    cli, _ = PROVIDERS.get(provider, (provider, ""))
    found = shutil.which(cli)
    say(OK if found else BAD, f"brain CLI '{cli}' for {provider}" + ("" if found else " not on PATH"))
    if not found and provider != "claude-code" and shutil.which("claude"):
        say(WARN, "Claude Code is installed: the agreed fallback brain if yours won't join")
    return bool(found)


def check_token(live: bool) -> bool:
    if os.environ.get("HERMIT_SWITCH_TOKEN"):
        say(OK, "HERMIT_SWITCH_TOKEN is set (value not shown)")
        return True
    say(BAD if live else WARN, "HERMIT_SWITCH_TOKEN not set in this shell (needed for --live)")
    return not live


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("host", help="afreen | abhishek | akshay (or a new host_id)")
    parser.add_argument("--server", help="Afreen's Tailscale IP, e.g. 100.101.102.103")
    parser.add_argument("--live", action="store_true", help="use the real Switch lease strategy")
    parser.add_argument("--force", action="store_true", help="rewrite hermit.config.toml")
    parser.add_argument("--provider", choices=sorted(PROVIDERS))
    parser.add_argument("--area")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--bedtime-start", default="01:00")
    parser.add_argument("--bedtime-end", default="06:00")
    args = parser.parse_args()

    host = args.host.lower()
    provider = args.provider or str(HOSTS.get(host, {}).get("provider", "claude-code"))

    print(f"\nHermit setup for {host}\n")
    write_config(host, args)
    make_window(provider)
    print()
    checks = [
        check_python(),
        check_node(),
        check_tailscale(),
        check_server(args.server),
        check_provider(provider),
        check_token(args.live),
    ]
    print()
    if all(checks):
        print(f"Ready. Next: onboard hermit-{host} in Switch Console (docs/switch-setup.md B3),")
        print("then `python -m hermit_keeper check` and `python -m hermit_keeper run`.")
        return 0
    print(f"Fix the {BAD} lines above, then run this again. Guide: docs/switch-setup.md")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

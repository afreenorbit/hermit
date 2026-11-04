"""switch/scripts/bootstrap_rooms.py, against the STAND-IN over real HTTP.

Proves the script's own behaviour — registers keepers, creates both rooms,
keeps keys out of stdout, is idempotent, refuses to write keys somewhere git
would pick them up. Whether real Switch accepts its moderation/rooms body is
unverified (the script says so and prints the server's reply).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from sim.switch_standin import DEFAULT_REGISTRATION_TOKEN, StandinSwitch, serve_standin

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_script() -> ModuleType:
    path = REPO_ROOT / "switch" / "scripts" / "bootstrap_rooms.py"
    spec = importlib.util.spec_from_file_location("bootstrap_rooms", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bootstrap = load_script()
HOSTS = ["afreen", "abhishek", "akshay"]


def test_dry_run_prints_the_plan_and_touches_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert bootstrap.main(["--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    via = [op["via"] for op in plan]
    assert via.count("http") == 5  # 3 registrations + 2 rooms
    soul = next(op for op in plan if op["op"] == "define_role")
    assert soul["via"] == "mcp" and soul["exclusive"] is True and soul["name"] == "soul"


def test_live_run_without_a_token_refuses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(bootstrap.TOKEN_ENV, raising=False)
    assert bootstrap.main(["--server", "http://127.0.0.1:9"]) == 2
    assert bootstrap.TOKEN_ENV in capsys.readouterr().err


def test_keys_are_never_written_inside_the_repo_unless_ignored() -> None:
    assert bootstrap.check_ignored(REPO_ROOT / ".switch-agents.json") is None
    assert "NOT git-ignored" in (bootstrap.check_ignored(REPO_ROOT / "keys.json") or "")


async def test_live_run_registers_creates_rooms_and_keeps_keys_off_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    switch = StandinSwitch(long_poll_s=0.5)
    out = tmp_path / "agents.json"
    async with serve_standin(switch) as base_url:
        monkeypatch.setenv(bootstrap.TOKEN_ENV, DEFAULT_REGISTRATION_TOKEN)
        argv = ["--server", base_url, "--out", str(out)]
        assert await asyncio.to_thread(bootstrap.main, argv) == 0
        first = capsys.readouterr().out

        state = json.loads(out.read_text(encoding="utf-8"))
        assert sorted(state["agents"]) == [f"keeper-{h}" for h in sorted(HOSTS)]
        keys = [a["api_key"] for a in state["agents"].values()]
        assert all(key not in first for key in keys), "api keys must never reach stdout"
        assert DEFAULT_REGISTRATION_TOKEN not in first

        den = switch.rooms[state["rooms"]["hermit-den"]]
        ledger = switch.rooms[state["rooms"]["hermit-ledger"]]
        assert (den.name, ledger.name) == ("hermit-den", "hermit-ledger")
        keeper_ids = {a["id"] for a in state["agents"].values()}
        assert keeper_ids <= den.members and keeper_ids <= ledger.members
        assert state["agents"]["keeper-afreen"]["id"] in first, "uuids are safe to print"
        assert 'define_role(name="soul", exclusive=True' in first

        # Idempotent: a second run registers and creates nothing new.
        assert await asyncio.to_thread(bootstrap.main, argv) == 0
        second = capsys.readouterr().out
        assert "already registered" in second and "already created" in second
        assert len(switch.agents) == 3 and len(switch.rooms) == 2
        assert all(key not in second for key in keys)

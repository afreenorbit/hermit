"""`hermit-keeper run` builds the real path for agent_instructed, or refuses.

The one thing it must never do is quietly build the fake: a keeper that runs
offline while its owner believes it is in the group is worse than one that
does not start.
"""

from __future__ import annotations

import copy

import pytest
import typer
from typer.testing import CliRunner

from hermit_keeper import cli
from hermit_keeper.brain.ledger_director import LedgerBrainDirector
from hermit_keeper.config import HostConfig
from hermit_keeper.lease.agent_instructed import AgentInstructedLease
from hermit_keeper.lease.fake import FakeSoulLease
from hermit_keeper.room.switch_client import SwitchRoomClient

FULL: dict = {
    "host_id": "afreen",
    "display_name": "Afreen",
    "city": "Bengaluru",
    "lat": 12.97,
    "lon": 77.59,
    "timezone": "Asia/Kolkata",
    "brain_agent": "hermit-afreen",
    "brain_provider": "claude-code",
    "window_dir": "~/HermitWindow",
    "switch": {
        "server_url": "http://127.0.0.1:9",
        "lease_strategy": "agent_instructed",
        "agent_id": "agent-uuid-1",
        "rooms": {"hermit-den": "den-uuid", "hermit-ledger": "ledger-uuid"},
    },
}


def config(**switch: object) -> HostConfig:
    document = copy.deepcopy(FULL)
    document["switch"].update(switch)
    return HostConfig.model_validate(document)


def test_missing_token_fails_fast_and_names_the_variable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(typer.Exit) as exc:
        cli._build_runtime(config(), env={})
    assert exc.value.exit_code == 2
    out = capsys.readouterr().out
    assert "HERMIT_SWITCH_TOKEN" in out
    assert "FAKE" not in out


def test_missing_agent_id_fails_fast(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit):
        cli._build_runtime(config(agent_id=None), env={"HERMIT_SWITCH_TOKEN": "k"})
    assert "switch.agent_id" in capsys.readouterr().out


def test_missing_room_uuids_fail_fast(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit):
        cli._build_runtime(config(rooms={}), env={"HERMIT_SWITCH_TOKEN": "k"})
    out = capsys.readouterr().out
    assert "hermit-den" in out and "hermit-ledger" in out


async def test_agent_instructed_builds_the_real_switch_path() -> None:
    runtime, close = cli._build_runtime(config(), env={"HERMIT_SWITCH_TOKEN": "secret-key"})
    try:
        assert isinstance(runtime.lease, AgentInstructedLease)
        assert isinstance(runtime.handoff._brain, LedgerBrainDirector)
        assert isinstance(runtime.handoff._room, SwitchRoomClient)
        room = runtime.handoff._room
        assert room.agent_id == FULL["switch"]["agent_id"]
        assert room.room_id("hermit-ledger") == FULL["switch"]["rooms"]["hermit-ledger"]
        # One HTTP client, shared: the room client and nothing else polls.
        assert room._client is not None
        assert runtime.switch_state() == "offline", "nothing proven until a poll succeeds"
    finally:
        await close()


def test_fake_is_only_ever_chosen_explicitly() -> None:
    runtime, _close = cli._build_runtime(config(lease_strategy="fake"))
    assert isinstance(runtime.lease, FakeSoulLease)
    assert runtime.switch_state() == "fake"


def test_check_switch_without_a_config_prints_the_handshake(tmp_path) -> None:
    result = CliRunner().invoke(
        cli.app, ["check", "--switch", "--config-path", str(tmp_path / "x")]
    )
    assert result.exit_code == 0, result.output
    assert "verified_against_switch_v0_9_0" in result.output
    assert "skipped" in result.output

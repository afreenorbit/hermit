"""The real lease strategy: the brain holds the soul, the room is the authority.

The rule under test throughout: **never believe the brain, always check the
room.** A coding agent reporting success it did not achieve is the most likely
way two friends end up each thinking they have Hermit.
"""

from __future__ import annotations

from typing import Any

from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.lease.agent_instructed import AgentInstructedLease, SwitchRoleReader


class StubRooms:
    """A room whose answer about the soul holder we control."""

    def __init__(self, holder: str | None = None) -> None:
        self.holder_value = holder
        self.calls = 0
        #: What the brain's cue will actually do, if anything.
        self.on_claim: str | None = None
        self.raises = False

    async def role_holder(self, room: str, role: str) -> str | None:
        self.calls += 1
        if self.raises:
            raise RuntimeError("switch unreachable")
        return self.holder_value


def build(holder: str | None = None) -> tuple[AgentInstructedLease, StubRooms, FakeBrain]:
    rooms = StubRooms(holder)
    brain = FakeBrain("hermit-afreen", "claude-code")
    lease = AgentInstructedLease(brain, rooms, clock=FakeClock(), ack_timeout_s=0.0)
    return lease, rooms, brain


async def test_claim_cues_the_brain_and_confirms_against_the_room() -> None:
    lease, rooms, brain = build(holder=None)

    async def cue(name: str, context: dict[str, Any] | None = None) -> None:
        await FakeBrain.cue(brain, name, context)
        if name == "CLAIM_SOUL":
            rooms.holder_value = "hermit-afreen"  # the brain really took it

    brain.cue = cue  # type: ignore[method-assign]

    result = await lease.claim("hermit-afreen")

    assert result.ok is True
    assert result.holder == "hermit-afreen"
    assert "CLAIM_SOUL" in [c for c, _ in brain.cues]


async def test_a_brain_that_acks_without_taking_the_role_is_not_believed() -> None:
    """The ACK says yes; the room says nobody holds it. The room wins."""
    lease, _rooms, _brain = build(holder=None)  # stays None: claim silently failed

    result = await lease.claim("hermit-afreen")

    assert result.ok is False, "an unconfirmed claim must never be reported as success"
    assert result.holder is None


async def test_claim_short_circuits_when_someone_else_already_holds_it() -> None:
    lease, _rooms, brain = build(holder="hermit-akshay")

    result = await lease.claim("hermit-afreen")

    assert result.ok is False
    assert result.holder == "hermit-akshay"
    assert brain.cues == [], "must not bother the brain for a soul that is taken"


async def test_claiming_a_soul_we_already_hold_succeeds_without_a_cue() -> None:
    lease, _rooms, brain = build(holder="hermit-afreen")

    result = await lease.claim("hermit-afreen")

    assert result.ok is True
    assert brain.cues == []


async def test_release_cues_the_brain_only_when_we_hold_it() -> None:
    lease, _rooms, brain = build(holder="hermit-akshay")

    await lease.release("hermit-afreen")

    assert brain.cues == [], "releasing a soul we do not hold must do nothing"


async def test_release_warns_but_does_not_lie_when_the_brain_hangs_on() -> None:
    """A stuck Hermit is a bad evening. A second Hermit is a broken product."""
    lease, _rooms, brain = build(holder="hermit-afreen")  # never changes

    await lease.release("hermit-afreen")

    assert "RELEASE_SOUL" in [c for c, _ in brain.cues]
    assert await lease.holder() == "hermit-afreen", "we report the truth, not the wish"


async def test_an_unreachable_switch_reads_as_unknown_not_as_free() -> None:
    """If we cannot see the room, we must not conclude the soul is free."""
    lease, rooms, _brain = build(holder="hermit-akshay")
    rooms.raises = True

    assert await lease.holder() is None
    result = await lease.claim("hermit-afreen")
    assert result.ok is False, "a failed lookup must not become a successful claim"


# -- the adapter over Switch's list_roles shape ------------------------------


class StubSwitchClient:
    def __init__(self, roles: list[dict[str, Any]]) -> None:
        self._roles = roles

    async def list_roles(self, room: str) -> list[dict[str, Any]]:
        return self._roles


async def test_role_reader_pulls_the_holder_out_of_switchs_shape() -> None:
    reader = SwitchRoleReader(
        StubSwitchClient(
            [
                {"name": "greeter", "held_by": [{"name": "hermit-akshay"}]},
                {
                    "name": "soul",
                    "exclusive": True,
                    "held_by": [
                        {"name": "hermit-abhishek", "present_here": True, "session_room": None}
                    ],
                },
            ]
        )
    )

    assert await reader.role_holder("hermit-den", "soul") == "hermit-abhishek"


async def test_role_reader_reports_a_free_soul_as_none() -> None:
    reader = SwitchRoleReader(
        StubSwitchClient([{"name": "soul", "exclusive": True, "held_by": []}])
    )

    assert await reader.role_holder("hermit-den", "soul") is None


async def test_role_reader_handles_a_room_with_no_soul_role_yet() -> None:
    reader = SwitchRoleReader(StubSwitchClient([]))

    assert await reader.role_holder("hermit-den", "soul") is None

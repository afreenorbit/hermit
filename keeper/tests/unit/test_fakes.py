"""The room, brain and presence fakes everyone else builds against."""

from __future__ import annotations

import asyncio

from hermit_keeper.brain.fake import FakeBrain
from hermit_keeper.clock import FakeClock
from hermit_keeper.presence.fake import ScriptedPresence
from hermit_keeper.room.fake import FakeRoomHub

DEN = "hermit-den"
LEDGER = "hermit-ledger"


# -- rooms -------------------------------------------------------------------


async def test_every_client_sees_the_same_room() -> None:
    hub = FakeRoomHub()
    afreen = hub.client("keeper-afreen")
    abhishek = hub.client("keeper-abhishek")

    await afreen.post(DEN, "hermit is here")
    history = await abhishek.history(DEN)

    assert [m.text for m in history] == ["hermit is here"]
    assert history[0].sender == "keeper-afreen"


async def test_rooms_are_isolated_from_each_other() -> None:
    """Ledger chatter must never leak into the friends' room."""
    hub = FakeRoomHub()
    client = hub.client("keeper-afreen")

    await client.post(LEDGER, "HERMIT/1 {}")
    await client.post(DEN, "hello")

    assert len(await client.history(DEN)) == 1
    assert len(await client.history(LEDGER)) == 1


async def test_history_is_ordered_and_limited() -> None:
    hub = FakeRoomHub()
    client = hub.client("keeper-afreen")
    for i in range(10):
        await client.post(DEN, f"line {i}")

    recent = await client.history(DEN, limit=3)

    assert [m.text for m in recent] == ["line 7", "line 8", "line 9"]


async def test_stream_delivers_to_every_subscriber() -> None:
    hub = FakeRoomHub()
    listener = hub.client("keeper-abhishek")
    speaker = hub.client("keeper-afreen")

    seen: list[str] = []
    stream = listener.stream(DEN)

    async def collect() -> None:
        async for message in stream:
            seen.append(message.text)

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)

    await speaker.post(DEN, "first")
    await speaker.post(DEN, "second")
    await asyncio.sleep(0)
    task.cancel()

    assert seen == ["first", "second"]


# -- tasks, which is what a favor is -----------------------------------------


async def test_a_favor_moves_from_open_to_assigned_to_done() -> None:
    hub = FakeRoomHub()
    client = hub.client("keeper-afreen")

    task_id = await client.create_task(DEN, "Favor from Abhishek", "Send a song", assignee=None)
    assert hub.tasks[task_id]["status"] == "open"

    await client.assign_task(task_id, "afreen")
    assert hub.tasks[task_id]["status"] == "assigned"
    assert hub.tasks[task_id]["assignee"] == "afreen"

    await client.complete_task(task_id)
    assert hub.tasks[task_id]["status"] == "done"
    assert hub.tasks[task_id]["completed_at"] is not None


async def test_list_tasks_filters_by_room_and_status() -> None:
    hub = FakeRoomHub()
    client = hub.client("keeper-afreen")
    open_id = await client.create_task(DEN, "open one", "", assignee=None)
    await client.create_task(LEDGER, "other room", "", assignee=None)
    done_id = await client.create_task(DEN, "done one", "", assignee="akshay")
    await client.complete_task(done_id)

    assert [t["id"] for t in await client.list_tasks(DEN)] == [open_id, done_id]
    assert [t["id"] for t in await client.list_tasks(DEN, status="open")] == [open_id]
    assert [t["id"] for t in await client.list_tasks(DEN, status="done")] == [done_id]


# -- brains ------------------------------------------------------------------


async def test_same_cue_three_brains_three_voices() -> None:
    """The demo in one test: one memory, three personalities."""
    hub = FakeRoomHub()
    context = {"city": "Bengaluru", "temp_c": 26, "previous_host": "afreen"}

    lines: dict[str, str] = {}
    for provider in ("claude-code", "codex", "opencode"):
        brain = FakeBrain(f"hermit-{provider}", provider, den=hub.client(f"hermit-{provider}"))
        await brain.cue("ARRIVE", context)
        lines[provider] = (await brain._den.history(DEN))[-1].text  # type: ignore[union-attr]

    assert len(set(lines.values())) == 3, "the three brains must not sound alike"
    for line in lines.values():
        assert "Bengaluru" in line, "every voice still carries the shared memory"


async def test_brain_speaks_only_in_the_den() -> None:
    hub = FakeRoomHub()
    brain = FakeBrain("hermit-afreen", "codex", den=hub.client("hermit-afreen"))

    await brain.cue("ARRIVE", {"city": "Bengaluru", "temp_c": 26})

    assert len(await hub.client("x").history(DEN)) == 1
    assert len(await hub.client("x").history(LEDGER)) == 0


async def test_soul_cues_are_acked_without_speaking() -> None:
    hub = FakeRoomHub()
    brain = FakeBrain("hermit-afreen", "claude-code", den=hub.client("hermit-afreen"))

    await brain.cue("CLAIM_SOUL", {})

    assert await brain.wait_ack("CLAIM_SOUL") is True
    assert await hub.client("x").history(DEN) == []


async def test_brain_records_every_cue_it_was_given() -> None:
    brain = FakeBrain("hermit-afreen", "codex")

    await brain.cue("ARRIVE", {"city": "Bengaluru"})
    await brain.cue("ASK_FAVOR", {})
    await brain.cue("DEPART", {"reason": "bedtime"})

    assert [cue for cue, _ in brain.cues] == ["ARRIVE", "ASK_FAVOR", "DEPART"]
    assert brain.cues[0][1]["city"] == "Bengaluru"


# -- presence ----------------------------------------------------------------


async def test_scripted_presence_follows_its_timeline() -> None:
    clock = FakeClock()
    presence = ScriptedPresence(clock, [(0, True), (3600, False), (7200, True)])

    assert presence.present() is True
    assert await presence.idle_seconds() == 0

    await clock.advance(3600)
    assert presence.present() is False

    await clock.advance(300)
    assert await presence.idle_seconds() == 300, "idle time grows while away"

    await clock.advance(3300)
    assert presence.present() is True
    assert await presence.idle_seconds() == 0


async def test_absent_before_the_timeline_starts() -> None:
    clock = FakeClock()
    presence = ScriptedPresence(clock, [(600, True)])

    assert presence.present() is False
    await clock.advance(600)
    assert presence.present() is True

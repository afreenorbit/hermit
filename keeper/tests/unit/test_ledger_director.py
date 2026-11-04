"""Cueing the brain through the ledger, and recognising its answer.

An ACK only counts if it comes from our brain, answers this cue, and arrived
after the cue was sent. Each test below breaks exactly one of those.
"""

from __future__ import annotations

import asyncio

from hermit_keeper.brain.ledger_director import LedgerBrainDirector
from hermit_keeper.brain.protocol import format_ack, parse_ack, parse_cue
from hermit_keeper.room.fake import FakeRoomHub

LEDGER = "hermit-ledger"


def setup() -> tuple[FakeRoomHub, LedgerBrainDirector]:
    hub = FakeRoomHub()
    director = LedgerBrainDirector(hub.client("keeper-afreen"), "hermit-afreen", "afreen")
    return hub, director


async def test_a_cue_is_a_ledger_line_addressed_to_the_brain() -> None:
    hub, director = setup()
    await director.cue("ARRIVE", {"city": "Indiranagar"})

    line = hub.rooms[LEDGER][-1]
    assert line.text.startswith("@hermit-afreen HERMIT-CUE/1 ")
    cue = parse_cue(line.text)
    assert cue is not None
    assert (cue.cue, cue.to, cue.host) == ("ARRIVE", "hermit-afreen", "afreen")
    assert cue.context == {"city": "Indiranagar"}
    assert cue.id == director.last_cue_id("ARRIVE")


async def test_the_brains_matching_ack_is_returned() -> None:
    hub, director = setup()
    await director.cue("CLAIM_SOUL", {})
    await hub.client("hermit-afreen").post(
        LEDGER, format_ack("CLAIM_SOUL", True, director.last_cue_id("CLAIM_SOUL"))
    )
    assert await director.wait_ack("CLAIM_SOUL", 0.5) is True


async def test_an_honest_no_is_returned_as_false() -> None:
    hub, director = setup()
    await director.cue("CLAIM_SOUL", {})
    await hub.client("hermit-afreen").post(
        LEDGER, format_ack("CLAIM_SOUL", False, director.last_cue_id("CLAIM_SOUL"))
    )
    receipt = await director.wait_ack_receipt("CLAIM_SOUL", 0.5)
    assert receipt is not None and receipt.ok is False


async def test_an_ack_from_someone_elses_brain_is_ignored() -> None:
    hub, director = setup()
    await director.cue("CLAIM_SOUL", {})
    await hub.client("hermit-akshay").post(
        LEDGER, format_ack("CLAIM_SOUL", True, director.last_cue_id("CLAIM_SOUL"))
    )
    assert await director.wait_ack("CLAIM_SOUL", 0.2) is False


async def test_an_ack_for_an_older_cue_is_ignored() -> None:
    hub, director = setup()
    brain = hub.client("hermit-afreen")
    await brain.post(LEDGER, format_ack("CLAIM_SOUL", True, None))  # before the cue
    await director.cue("CLAIM_SOUL", {})
    assert await director.wait_ack("CLAIM_SOUL", 0.2) is False


async def test_an_ack_naming_a_different_cue_id_is_ignored() -> None:
    hub, director = setup()
    await director.cue("CLAIM_SOUL", {})
    await hub.client("hermit-afreen").post(LEDGER, format_ack("CLAIM_SOUL", True, "cue_other"))
    assert await director.wait_ack("CLAIM_SOUL", 0.2) is False


async def test_a_brain_that_forgets_the_id_is_still_understood() -> None:
    hub, director = setup()
    await director.cue("RELEASE_SOUL", {})
    await hub.client("hermit-afreen").post(LEDGER, format_ack("RELEASE_SOUL", True, None))
    assert await director.wait_ack("RELEASE_SOUL", 0.5) is True


async def test_a_brain_known_by_uuid_is_recognised() -> None:
    hub = FakeRoomHub()
    director = LedgerBrainDirector(
        hub.client("keeper-afreen"), "hermit-afreen", "afreen", brain_ids={"uuid-1234"}
    )
    await director.cue("CLAIM_SOUL", {})
    await hub.client("uuid-1234").post(
        LEDGER, format_ack("CLAIM_SOUL", True, director.last_cue_id("CLAIM_SOUL"))
    )
    assert await director.wait_ack("CLAIM_SOUL", 0.5) is True


async def test_an_ack_that_arrives_while_waiting_is_seen() -> None:
    hub, director = setup()
    await director.cue("CLAIM_SOUL", {})

    async def answer_later() -> None:
        await asyncio.sleep(0.1)
        await hub.client("hermit-afreen").post(
            LEDGER, format_ack("CLAIM_SOUL", True, director.last_cue_id("CLAIM_SOUL"))
        )

    task = asyncio.create_task(answer_later())
    assert await director.wait_ack("CLAIM_SOUL", 2.0) is True
    await task


async def test_wait_ack_times_out_false() -> None:
    _hub, director = setup()
    await director.cue("CLAIM_SOUL", {})
    assert await director.wait_ack("CLAIM_SOUL", 0.1) is False


def test_ack_parsing_tolerates_a_mention_and_trailing_text() -> None:
    ack = parse_ack('@keeper-afreen HERMIT-ACK/1 {"cue":"CLAIM_SOUL","ok":true}. done')
    assert ack is not None and ack.ok is True and ack.id is None
    assert parse_ack("HERMIT-ACK/1 not json") is None
    assert parse_ack('HERMIT-ACK/1 {"cue":"X","ok":"yes"}').ok is False  # type: ignore[union-attr]

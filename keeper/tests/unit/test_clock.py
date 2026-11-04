from __future__ import annotations

import asyncio

from hermit_keeper.clock import FakeClock


async def test_fake_clock_sleep_resolves_only_when_advanced() -> None:
    clock = FakeClock()
    woke = False

    async def sleeper() -> None:
        nonlocal woke
        await clock.sleep(30)
        woke = True

    task = asyncio.create_task(sleeper())
    await asyncio.sleep(0)
    assert woke is False

    await clock.advance(29)
    assert woke is False

    await clock.advance(2)
    await task
    assert woke is True

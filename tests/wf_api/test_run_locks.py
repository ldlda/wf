from __future__ import annotations

import asyncio

from wf_api.run_locks import AsyncKeyedLock


async def test_async_keyed_lock_serializes_same_key() -> None:
    locks = AsyncKeyedLock()
    entered: list[str] = []
    release_first = asyncio.Event()

    async def first() -> None:
        async with locks.lock("run_123"):
            entered.append("first")
            await release_first.wait()

    async def second() -> None:
        async with locks.lock("run_123"):
            entered.append("second")

    first_task = asyncio.create_task(first())
    await asyncio.sleep(0)
    second_task = asyncio.create_task(second())
    await asyncio.sleep(0)

    assert entered == ["first"]

    release_first.set()
    await asyncio.gather(first_task, second_task)

    assert entered == ["first", "second"]


async def test_async_keyed_lock_allows_different_keys_concurrently() -> None:
    locks = AsyncKeyedLock()
    entered: list[str] = []
    release = asyncio.Event()

    async def hold(key: str) -> None:
        async with locks.lock(key):
            entered.append(key)
            await release.wait()

    first_task = asyncio.create_task(hold("run_a"))
    second_task = asyncio.create_task(hold("run_b"))
    await asyncio.sleep(0)

    assert entered == ["run_a", "run_b"]

    release.set()
    await asyncio.gather(first_task, second_task)


async def test_async_keyed_lock_releases_waiter_count_when_cancelled() -> None:
    locks = AsyncKeyedLock()
    release_first = asyncio.Event()
    waiting = asyncio.Event()

    async def first() -> None:
        async with locks.lock("run_cancelled"):
            await release_first.wait()

    async def cancelled_waiter() -> None:
        waiting.set()
        async with locks.lock("run_cancelled"):
            raise AssertionError("cancelled waiter must not enter")

    first_task = asyncio.create_task(first())
    await asyncio.sleep(0)

    waiter_task = asyncio.create_task(cancelled_waiter())
    await waiting.wait()
    await asyncio.sleep(0)
    waiter_task.cancel()

    try:
        await waiter_task
    except asyncio.CancelledError:
        pass

    release_first.set()
    await first_task

    async with locks.lock("run_cancelled"):
        pass

    assert locks._entries == {}

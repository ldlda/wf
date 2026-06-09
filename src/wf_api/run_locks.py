from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass(slots=True)
class _LockEntry:
    lock: asyncio.Lock
    users: int = 0


class AsyncKeyedLock:
    """Process-local async critical sections keyed by a stable string id."""

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._entries: dict[str, _LockEntry] = {}

    @asynccontextmanager
    async def lock(self, key: str) -> AsyncIterator[None]:
        entry = await self._retain(key)
        acquired = False
        try:
            await entry.lock.acquire()
            acquired = True
        except BaseException:
            # A queued caller can be cancelled before it acquires the per-key
            # lock. Drop its retained user count so long-lived servers do not
            # keep stale lock entries forever.
            await self._release(key, entry)
            raise
        try:
            yield
        finally:
            if acquired:
                entry.lock.release()
            await self._release(key, entry)

    async def _retain(self, key: str) -> _LockEntry:
        async with self._guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = _LockEntry(lock=asyncio.Lock())
                self._entries[key] = entry
            entry.users += 1
            return entry

    async def _release(self, key: str, entry: _LockEntry) -> None:
        async with self._guard:
            entry.users -= 1
            if entry.users == 0 and not entry.lock.locked():
                self._entries.pop(key, None)

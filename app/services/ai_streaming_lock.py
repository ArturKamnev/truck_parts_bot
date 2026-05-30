from __future__ import annotations

import asyncio


class AIStreamingLockRegistry:
    """Tracks active per-customer AI streams in this bot process."""

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._active_customer_ids: set[int] = set()

    async def acquire(self, customer_id: int) -> bool:
        async with self._guard:
            if customer_id in self._active_customer_ids:
                return False
            self._active_customer_ids.add(customer_id)
            return True

    async def release(self, customer_id: int) -> None:
        async with self._guard:
            self._active_customer_ids.discard(customer_id)


default_streaming_locks = AIStreamingLockRegistry()

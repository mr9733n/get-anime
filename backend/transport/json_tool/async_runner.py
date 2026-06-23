from __future__ import annotations

import asyncio
from typing import Any, Awaitable


def run(coro: Awaitable[Any]) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # на будущее: если когда-то появится long-running event loop (например, сервер)
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    return asyncio.run(coro)

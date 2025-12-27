import functools
import asyncio
import httpx
import logging
from typing import Callable, Awaitable, TypeVar, Any

T = TypeVar("T")
_logger = logging.getLogger(__name__)

def retry_async(
    *,
    max_tries: int = 5,
    base_delay: float = 2.0,
    allowed_exceptions: tuple[type[BaseException], ...] = (
        httpx.ReadError,
        httpx.ConnectError,
        httpx.HTTPStatusError,
    ),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Декоратор для асинхронных функций.
    При возникновении `allowed_exceptions` делает повторные попытки
    с экспоненциальным back‑off.
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = base_delay
            for attempt in range(1, max_tries + 1):
                try:
                    return await func(*args, **kwargs)
                except allowed_exceptions as exc:
                    # 429 – отдельная логика, уже есть в вашем коде
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                        retry_after = exc.response.headers.get("Retry-After")
                        wait = (
                            float(retry_after)
                            if retry_after and retry_after.isdigit()
                            else delay
                        )
                        _logger.warning(
                            f"429 Too Many Requests – waiting {wait}s (attempt {attempt})"
                        )
                    else:
                        _logger.warning(
                            f"{type(exc).__name__} on attempt {attempt}: {exc}"
                        )
                        wait = delay

                    if attempt == max_tries:
                        _logger.error(
                            f"Failed after {max_tries} attempts – giving up: {exc}"
                        )
                        raise
                    await asyncio.sleep(wait)
                    delay *= 2  # экспоненциальный рост
        return wrapper
    return decorator

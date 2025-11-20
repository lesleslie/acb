"""ACB MCP Retry Utilities.

Provides functions for executing operations with retry logic.
"""

from typing import Any


async def async_retry(
    func: Any,
    max_attempts: int = 3,
    delay: float = 1.0,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a function with retry logic."""
    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                import asyncio

                await asyncio.sleep(delay * (2**attempt))  # Exponential backoff
            else:
                raise last_exception

    # This should never be reached due to the loop logic, but just in case
    if last_exception:
        raise last_exception
    msg = "Unexpected error in async_retry"
    raise RuntimeError(msg)

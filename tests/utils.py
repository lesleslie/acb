"""Test utilities for ACB tests."""

import typing as t
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from acb.config import Config

T = t.TypeVar("T")


async def assert_cache_operations(cache: t.Any, key: str, value: t.Any) -> None:
    await cache.set(key, value)
    result = await cache.get(key)
    assert result == value

    await cache.delete(key)
    result = await cache.get(key)
    assert result is None


@asynccontextmanager
async def mock_redis_client() -> t.AsyncGenerator[AsyncMock, None]:
    with patch("redis.asyncio.Redis") as mock_redis:
        mock_client = AsyncMock()
        mock_redis.from_url.return_value = mock_client
        yield mock_client


@asynccontextmanager
async def mock_s3_client() -> t.AsyncGenerator[AsyncMock, None]:
    with patch("aiobotocore.session.AioSession") as mock_session:
        mock_client = AsyncMock()
        mock_session.return_value.create_client.return_value.__aenter__.return_value = (
            mock_client
        )
        yield mock_client


def create_mock_config(**kwargs: t.Any) -> MagicMock:
    mock_config = MagicMock(spec=Config)
    for key, value in kwargs.items():
        setattr(mock_config, key, value)
    return mock_config

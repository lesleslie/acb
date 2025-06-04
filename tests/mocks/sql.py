"""Mock implementations of SQL adapters for testing."""

import typing as t
from contextlib import asynccontextmanager
from functools import cached_property
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from acb.adapters.sql._base import SqlBase


class MockSqlBase(SqlBase):
    def __init__(self) -> None:
        self._engine = AsyncMock(spec=AsyncEngine)
        self._session_maker = AsyncMock()
        self._session = AsyncMock(spec=AsyncSession)
        self._session_maker.return_value = self._session
        self._initialized = True
        self.config = MagicMock()
        self.config.app.name = "test"

    @cached_property
    def engine(self) -> AsyncEngine:
        return self._engine

    @cached_property
    def session(self) -> AsyncSession:
        return self._session

    @asynccontextmanager
    async def get_session(self) -> t.AsyncGenerator[AsyncSession]:
        try:
            yield self._session
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        finally:
            await self._session.close()

    @asynccontextmanager
    async def get_conn(self) -> t.AsyncGenerator[t.Any]:
        conn = AsyncMock()
        self._engine.begin.return_value.__aenter__.return_value = conn
        yield conn

    async def init(self) -> None:
        self._initialized = True

    async def run_migrations(self) -> None:
        pass

    async def create_backup(self) -> str:
        return "mock_backup_id"

    async def restore_backup(self, backup_id: str) -> bool:
        return True

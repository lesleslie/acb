"""Mock implementations of SQL adapters for testing."""

import typing as t
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from acb.adapters.sql._base import SqlBase


class MockSqlBase(SqlBase):
    def __init__(self) -> None:
        super().__init__()
        self._engine = AsyncMock(spec=AsyncEngine)
        self._session_mock = AsyncMock(spec=AsyncSession)
        self._initialized = True
        self.config = MagicMock()
        self.config.app.name = "test"

    async def _create_client(self) -> AsyncEngine:
        return t.cast(AsyncEngine, self._engine)

    async def get_engine(self) -> AsyncEngine:
        return t.cast(AsyncEngine, self._engine)

    @property
    def engine(self) -> AsyncEngine:
        return t.cast(AsyncEngine, self._engine)

    async def _ensure_session(self) -> AsyncSession:
        return self._session_mock

    @property
    def session(self) -> AsyncSession:
        return self._session_mock

    @asynccontextmanager
    async def get_session(self) -> t.AsyncIterator[AsyncSession]:
        try:
            yield self._session_mock
            await self._session_mock.commit()
        except Exception:
            await self._session_mock.rollback()
            raise
        finally:
            await self._session_mock.close()

    @asynccontextmanager
    async def get_conn(self) -> t.AsyncIterator[t.Any]:
        conn = AsyncMock()
        conn.return_value = conn
        yield conn

    async def init(self) -> None:
        self._initialized = True

    async def run_migrations(self) -> None:
        pass

    async def create_backup(self) -> str:
        return "mock_backup_id"

    async def restore_backup(self, backup_id: str) -> bool:
        return True

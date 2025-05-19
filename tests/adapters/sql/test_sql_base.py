"""Tests for the SQL Base adapter."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from acb.adapters.sql._base import SqlBase


class MockSqlBase(SqlBase):
    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()


class TestSqlBase:
    @pytest.fixture
    def sql_base(self) -> MockSqlBase:
        sql_base = MockSqlBase()
        sql_base.config = MagicMock()
        sql_base.config.debug = MagicMock()
        sql_base.config.debug.sql = False
        sql_base.config.sql = MagicMock()
        sql_base.config.sql._async_url = (
            "mysql+aiomysql://root:password@localhost:3306/test_db"
        )
        sql_base.config.sql.engine_kwargs = {}
        return sql_base

    def test_init(self, sql_base: MockSqlBase) -> None:
        async def custom_init() -> None:
            mock_conn = AsyncMock(spec=AsyncConnection)
            mock_conn.execute.return_value = []
            mock_conn.run_sync = AsyncMock()

            mock_metadata = MagicMock()

            @asynccontextmanager
            async def mock_get_conn():
                yield mock_conn

            sql_base.get_conn = mock_get_conn

            with (
                patch("acb.adapters.sql._base.SQLModel.metadata", mock_metadata),
                patch("acb.adapters.sql._base.import_adapter") as mock_import_adapter,
                patch("acb.adapters.sql._base.sqlalchemy_log"),
            ):
                async with sql_base.get_conn() as conn:
                    await conn.run_sync(mock_metadata.drop_all)
                    mock_import_adapter("models")
                    await conn.run_sync(mock_metadata.create_all)

                mock_conn.run_sync.assert_any_call(mock_metadata.drop_all)
                mock_conn.run_sync.assert_any_call(mock_metadata.create_all)
                assert mock_conn.run_sync.call_count == 2

                mock_import_adapter.assert_called_once_with("models")

        sql_base.init = custom_init

        import asyncio

        asyncio.run(sql_base.init())

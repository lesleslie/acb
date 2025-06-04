"""Tests for the PostgreSQL adapter."""

import typing as t
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import SQLModel
from acb.adapters.sql.pgsql import Sql, SqlSettings
from acb.config import Config


class MockSqlEngine(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.dispose = AsyncMock()
        self.begin = MagicMock()
        self.begin.return_value.__aenter__ = AsyncMock()
        self.begin.return_value.__aexit__ = AsyncMock()
        self.__aenter__ = AsyncMock(return_value=self)
        self.__aexit__ = AsyncMock(return_value=None)


class MockSqlSession(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.close = AsyncMock()
        self.execute = AsyncMock()
        self.__aenter__ = AsyncMock(return_value=self)
        self.__aexit__ = AsyncMock(return_value=None)


class TestPgSqlSettings:
    def test_driver_settings(self) -> None:
        assert getattr(SqlSettings._driver, "default") == "postgresql+psycopg2"
        assert getattr(SqlSettings._async_driver, "default") == "postgresql+asyncpg"


class TestPgSql:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)

        mock_sql = MagicMock(spec=SqlSettings)
        mock_sql.driver = "postgresql+psycopg2"
        mock_sql.async_driver = "postgresql+asyncpg"
        mock_sql.url = "postgresql://user:pass@localhost:5432/test"
        mock_sql._url = "postgresql://user:pass@localhost:5432/test"
        mock_sql._async_url = "postgresql+asyncpg://user:pass@localhost:5432/test"
        mock_sql.echo = False
        mock_sql.create_db = True
        mock_sql.drop_on_startup = False
        mock_sql.engine_kwargs = {}
        mock_config.sql = mock_sql

        return mock_config

    @pytest.fixture
    def pgsql_adapter(self, mock_config: MagicMock) -> Sql:
        adapter = Sql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_engine_property(self, pgsql_adapter: Sql) -> None:
        with (
            patch(
                "acb.adapters.sql._base.create_async_engine",
                return_value=MockSqlEngine(),
            ) as mock_create_engine,
            patch("acb.adapters.sql._base.database_exists", return_value=True),
            patch("sqlalchemy.create_engine", return_value=MagicMock()),
        ):
            engine = pgsql_adapter.engine

            mock_create_engine.assert_called_once_with(
                pgsql_adapter.config.sql._async_url,
                **pgsql_adapter.config.sql.engine_kwargs,
            )

            assert engine == mock_create_engine.return_value

    @pytest.mark.asyncio
    async def test_engine_property_create_database(self, pgsql_adapter: Sql) -> None:
        if "engine" in pgsql_adapter.__dict__:
            del pgsql_adapter.__dict__["engine"]

        mock_engine = MockSqlEngine()
        mock_db_exists = MagicMock(return_value=False)
        mock_create_db = MagicMock()

        with (
            patch("acb.adapters.sql._base.database_exists", mock_db_exists),
            patch("acb.adapters.sql._base.create_database", mock_create_db),
            patch(
                "acb.adapters.sql._base.create_async_engine", return_value=mock_engine
            ),
            patch("sqlalchemy.create_engine", return_value=MagicMock()),
        ):
            engine = pgsql_adapter.engine

            assert engine is mock_engine

            mock_db_exists.assert_called_once_with(pgsql_adapter.config.sql._url)
            mock_create_db.assert_called_once_with(pgsql_adapter.config.sql._url)

    @pytest.mark.asyncio
    async def test_session_property(self, pgsql_adapter: Sql) -> None:
        mock_engine = MockSqlEngine()

        with (
            patch.object(pgsql_adapter, "engine", mock_engine),
            patch(
                "acb.adapters.sql._base.AsyncSession", return_value=MockSqlSession()
            ) as mock_session_cls,
        ):
            session = pgsql_adapter.session

            mock_session_cls.assert_called_once_with(
                mock_engine, expire_on_commit=False
            )

            assert isinstance(session, MagicMock)
            assert session is mock_session_cls.return_value

    @pytest.mark.asyncio
    async def test_get_session(self, pgsql_adapter: Sql) -> None:
        mock_session = MockSqlSession()

        with (
            patch.object(pgsql_adapter, "session", mock_session),
            patch("acb.adapters.sql._base.AsyncSession", return_value=mock_session),
        ):
            async with pgsql_adapter.get_session() as session:
                mock_session.__aenter__.assert_called_once()

                assert session is mock_session

            mock_session.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conn(self, pgsql_adapter: Sql) -> None:
        mock_conn_ctx = MagicMock()
        mock_conn_ctx.__aenter__ = AsyncMock()
        mock_conn_ctx.__aexit__ = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_conn_ctx)

        with patch.object(pgsql_adapter, "engine", mock_engine):
            async with pgsql_adapter.get_conn() as conn:
                mock_engine.begin.assert_called_once()
                mock_conn_ctx.__aenter__.assert_called_once()
                assert conn is mock_conn_ctx.__aenter__.return_value

            mock_conn_ctx.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_init(self, pgsql_adapter: Sql) -> None:
        mock_conn = MagicMock()
        mock_conn.run_sync = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=AsyncMock())

        @asynccontextmanager
        async def mock_get_conn() -> t.AsyncGenerator[MagicMock]:
            yield mock_conn

        with (
            patch.object(pgsql_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.sql._base.import_adapter", MagicMock()),
        ):
            pgsql_adapter.config.sql.drop_on_startup = True
            if not hasattr(pgsql_adapter.config.debug, "sql"):
                setattr(pgsql_adapter.config.debug, "sql", False)

            await pgsql_adapter.init()

            assert mock_conn.run_sync.call_count == 2
            assert (
                mock_conn.run_sync.call_args_list[0][0][0] == SQLModel.metadata.drop_all
            )
            assert (
                mock_conn.run_sync.call_args_list[1][0][0]
                == SQLModel.metadata.create_all
            )

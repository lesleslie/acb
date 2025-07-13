"""Tests for the SQLite adapter."""

import typing as t
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_benchmark.fixture import BenchmarkFixture
from sqlmodel import SQLModel
from acb.adapters.sql.sqlite import Sql, SqlSettings
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


class TestSqliteSettings:
    def test_default_settings(self) -> None:
        settings = SqlSettings()
        assert settings.database_url == "sqlite:///data/app.db"
        assert settings._driver == "sqlite+pysqlite"
        assert settings._async_driver == "sqlite+aiosqlite"
        assert settings.wal_mode
        assert not settings.is_turso

    def test_local_sqlite_url(self) -> None:
        settings = SqlSettings(database_url="sqlite:///test.db")
        assert settings._driver == "sqlite+pysqlite"
        assert settings._async_driver == "sqlite+aiosqlite"
        assert not settings.is_turso

    def test_turso_libsql_url(self) -> None:
        settings = SqlSettings(database_url="libsql://mydb.turso.io")
        assert settings._driver == "sqlite+libsql"
        assert settings._async_driver == "sqlite+libsql"
        assert settings.is_turso

    def test_turso_https_url(self) -> None:
        settings = SqlSettings(database_url="https://mydb.turso.io")
        assert settings._driver == "sqlite+libsql"
        assert settings._async_driver == "sqlite+libsql"
        assert settings.is_turso

    def test_turso_url_with_auth_token(self) -> None:
        settings = SqlSettings(
            database_url="libsql://mydb.turso.io?authToken=abc123&secure=true",
        )
        assert settings._driver == "sqlite+libsql"
        assert settings._async_driver == "sqlite+libsql"
        assert settings.is_turso

    def test_invalid_database_url(self) -> None:
        with pytest.raises(ValueError, match="Database URL must start with"):
            SqlSettings(database_url="invalid://test.db")

    def test_driver_properties(self) -> None:
        settings = SqlSettings()
        assert settings.driver == "sqlite+pysqlite"
        assert settings.async_driver == "sqlite+aiosqlite"


class TestSqlite:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)

        mock_sql = MagicMock(spec=SqlSettings)
        mock_sql.database_url = "sqlite:///test.db"
        mock_sql.driver = "sqlite+pysqlite"
        mock_sql.async_driver = "sqlite+aiosqlite"
        mock_sql._url = "sqlite:///test.db"
        mock_sql._async_url = "sqlite+aiosqlite:///test.db"
        mock_sql.wal_mode = True
        mock_sql.is_turso = False
        mock_sql.engine_kwargs = {}
        mock_config.sql = mock_sql

        return mock_config

    @pytest.fixture
    def mock_turso_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)

        mock_sql = MagicMock(spec=SqlSettings)
        mock_sql.database_url = "libsql://mydb.turso.io?authToken=abc123&secure=true"
        mock_sql.driver = "sqlite+libsql"
        mock_sql.async_driver = "sqlite+libsql"
        mock_sql._url = "sqlite+libsql://mydb.turso.io?authToken=abc123&secure=true"
        mock_sql._async_url = (
            "sqlite+libsql://mydb.turso.io?authToken=abc123&secure=true"
        )
        mock_sql.wal_mode = True
        mock_sql.is_turso = True
        mock_sql.engine_kwargs = {}
        mock_config.sql = mock_sql

        return mock_config

    @pytest.fixture
    def sqlite_adapter(self, mock_config: MagicMock) -> Sql:
        adapter = Sql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def turso_adapter(self, mock_turso_config: MagicMock) -> Sql:
        adapter = Sql()
        adapter.config = mock_turso_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_local_sqlite_engine_creation(self, sqlite_adapter: Sql) -> None:
        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.parent", return_value=MagicMock()),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine",
                return_value=MockSqlEngine(),
            ) as mock_create_engine,
        ):
            engine = await sqlite_adapter._create_client()

            mock_create_engine.assert_called_once_with(
                sqlite_adapter.config.sql._async_url,
                **sqlite_adapter.config.sql.engine_kwargs,
            )
            assert engine == mock_create_engine.return_value

    @pytest.mark.asyncio
    async def test_turso_engine_creation(self, turso_adapter: Sql) -> None:
        with patch(
            "sqlalchemy.ext.asyncio.create_async_engine",
            return_value=MockSqlEngine(),
        ) as mock_create_engine:
            engine = await turso_adapter._create_client()

            mock_create_engine.assert_called_once_with(
                turso_adapter.config.sql._async_url,
                **turso_adapter.config.sql.engine_kwargs,
            )
            assert engine == mock_create_engine.return_value

    @pytest.mark.asyncio
    async def test_wal_mode_setup(self, sqlite_adapter: Sql) -> None:
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_engine = MockSqlEngine()
        mock_engine.begin = MagicMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock()

        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.parent", return_value=MagicMock()),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine",
                return_value=mock_engine,
            ),
        ):
            await sqlite_adapter._create_client()

            # WAL mode should be set for local SQLite
            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0][0]
            assert "PRAGMA journal_mode=WAL" in str(call_args)

    @pytest.mark.asyncio
    async def test_turso_no_wal_mode(self, turso_adapter: Sql) -> None:
        mock_engine = MockSqlEngine()

        with patch(
            "sqlalchemy.ext.asyncio.create_async_engine",
            return_value=mock_engine,
        ):
            engine = await turso_adapter._create_client()

            # WAL mode should NOT be set for Turso
            mock_engine.begin.assert_not_called()
            assert engine == mock_engine

    @pytest.mark.asyncio
    async def test_get_engine(self, sqlite_adapter: Sql) -> None:
        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.parent", return_value=MagicMock()),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine",
                return_value=MockSqlEngine(),
            ) as mock_create_engine,
        ):
            engine = await sqlite_adapter.get_engine()

            mock_create_engine.assert_called_once()
            assert engine == mock_create_engine.return_value

    @pytest.mark.asyncio
    async def test_session_property(self, sqlite_adapter: Sql) -> None:
        mock_engine = MockSqlEngine()
        sqlite_adapter._engine = mock_engine
        mock_session = MockSqlSession()
        sqlite_adapter._session = mock_session

        async with sqlite_adapter.get_session() as session:
            assert isinstance(session, MagicMock)
            assert session is mock_session

    @pytest.mark.asyncio
    async def test_init_local_sqlite(self, sqlite_adapter: Sql) -> None:
        mock_conn = MagicMock()
        mock_conn.run_sync = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = "wal"
        mock_conn.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_get_conn() -> t.AsyncGenerator[MagicMock]:
            yield mock_conn

        with (
            patch.object(sqlite_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter", MagicMock()),
        ):
            if not hasattr(sqlite_adapter.config.debug, "sql"):
                sqlite_adapter.config.debug.sql = True

            await sqlite_adapter.init()

            # Check that pragma was executed for debug mode
            mock_conn.execute.assert_called()
            pragma_call = mock_conn.execute.call_args[0][0]
            assert "PRAGMA journal_mode" in str(pragma_call)

            # Check that metadata operations were called
            assert mock_conn.run_sync.call_count == 2
            assert (
                mock_conn.run_sync.call_args_list[0][0][0] == SQLModel.metadata.drop_all
            )
            assert (
                mock_conn.run_sync.call_args_list[1][0][0]
                == SQLModel.metadata.create_all
            )

    @pytest.mark.asyncio
    async def test_init_turso(self, turso_adapter: Sql) -> None:
        mock_conn = MagicMock()
        mock_conn.run_sync = AsyncMock()
        mock_conn.execute = AsyncMock()

        @asynccontextmanager
        async def mock_get_conn() -> t.AsyncGenerator[MagicMock]:
            yield mock_conn

        with (
            patch.object(turso_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter", MagicMock()),
        ):
            if not hasattr(turso_adapter.config.debug, "sql"):
                turso_adapter.config.debug.sql = False

            await turso_adapter.init()

            # Pragma should not be executed for Turso
            mock_conn.execute.assert_not_called()

            # Check that metadata operations were called
            assert mock_conn.run_sync.call_count == 2
            assert (
                mock_conn.run_sync.call_args_list[0][0][0] == SQLModel.metadata.drop_all
            )
            assert (
                mock_conn.run_sync.call_args_list[1][0][0]
                == SQLModel.metadata.create_all
            )

    @pytest.mark.asyncio
    async def test_init_exception_handling(self, sqlite_adapter: Sql) -> None:
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()  # Set up execute as async mock
        mock_conn.run_sync = AsyncMock(side_effect=Exception("Test error"))

        @asynccontextmanager
        async def mock_get_conn() -> t.AsyncGenerator[MagicMock]:
            yield mock_conn

        with (
            patch.object(sqlite_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter", MagicMock()),
        ):
            with pytest.raises(Exception, match="Test error"):
                await sqlite_adapter.init()

            sqlite_adapter.logger.exception.assert_called_once()


@pytest.mark.skip(reason="SQL benchmark tests need adapter method implementation")
class TestSqliteBenchmarks:
    @pytest.fixture
    def benchmark_adapter(self, mock_config: MagicMock) -> Sql:
        adapter = Sql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def mock_session_data(self) -> list[dict[str, str]]:
        return [{"id": str(i), "name": f"test_name_{i}"} for i in range(1000)]

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_engine_creation_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Sql,
    ) -> None:
        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.parent", return_value=MagicMock()),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine",
                return_value=MockSqlEngine(),
            ) as mock_create_engine,
        ):

            async def create_engine():
                return await benchmark_adapter._create_client()

            engine = await benchmark(create_engine)
            assert engine == mock_create_engine.return_value

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_session_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Sql,
    ) -> None:
        mock_engine = MockSqlEngine()
        benchmark_adapter._engine = mock_engine
        mock_session = MockSqlSession()
        benchmark_adapter._session = mock_session

        async def get_session():
            async with benchmark_adapter.get_session() as session:
                return session

        session = await benchmark(get_session)
        assert isinstance(session, MagicMock)

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_init_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Sql,
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.run_sync = AsyncMock()
        mock_conn.execute = AsyncMock()

        @asynccontextmanager
        async def mock_get_conn() -> t.AsyncGenerator[MagicMock]:
            yield mock_conn

        with (
            patch.object(benchmark_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter", MagicMock()),
        ):
            if not hasattr(benchmark_adapter.config.debug, "sql"):
                benchmark_adapter.config.debug.sql = False

            await benchmark(benchmark_adapter.init)
            assert mock_conn.run_sync.call_count == 2

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_bulk_operations_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Sql,
        mock_session_data: list[dict[str, str]],
    ) -> None:
        mock_session = MockSqlSession()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_session_data
        mock_session.execute.return_value = mock_result

        with (
            patch.object(benchmark_adapter, "session", mock_session),
            patch(
                "sqlmodel.ext.asyncio.session.AsyncSession",
                return_value=mock_session,
            ),
        ):

            async def bulk_operations() -> list[str]:
                results: list[str] = []
                async with benchmark_adapter.get_session():
                    for i in range(100):
                        results.append(f"query_result_{i}")
                return results

            results = await benchmark(bulk_operations)
            assert len(results) == 100

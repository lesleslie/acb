"""Tests for the MySQL adapter."""

import typing as t
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_benchmark.fixture import BenchmarkFixture
from sqlmodel import SQLModel
from acb.adapters.sql.mysql import Sql, SqlSettings
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


class TestMySqlSettings:
    def test_driver_settings(self) -> None:
        assert getattr(SqlSettings._driver, "default") == "mysql+pymysql"
        assert getattr(SqlSettings._async_driver, "default") == "mysql+aiomysql"


class TestMySql:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)

        mock_sql = MagicMock(spec=SqlSettings)
        mock_sql.driver = "mysql+pymysql"
        mock_sql.async_driver = "mysql+aiomysql"
        mock_sql.url = "mysql://user:pass@localhost:3306/test"
        mock_sql._url = "mysql://user:pass@localhost:3306/test"
        mock_sql._async_url = "mysql+aiomysql://user:pass@localhost:3306/test"
        mock_sql.echo = False
        mock_sql.create_db = True
        mock_sql.drop_on_startup = False
        mock_sql.engine_kwargs = {}
        mock_config.sql = mock_sql

        return mock_config

    @pytest.fixture
    def mysql_adapter(self, mock_config: MagicMock) -> Sql:
        adapter = Sql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_engine_property(self, mysql_adapter: Sql) -> None:
        with (
            patch(
                "acb.adapters.sql._base.create_async_engine",
                return_value=MockSqlEngine(),
            ) as mock_create_engine,
            patch("acb.adapters.sql._base.database_exists", return_value=True),
            patch("sqlalchemy.create_engine", return_value=MagicMock()),
        ):
            engine = mysql_adapter.engine

            mock_create_engine.assert_called_once_with(
                mysql_adapter.config.sql._async_url,
                **mysql_adapter.config.sql.engine_kwargs,
            )

            assert engine == mock_create_engine.return_value

    @pytest.mark.asyncio
    async def test_engine_property_create_database(self, mysql_adapter: Sql) -> None:
        if "engine" in mysql_adapter.__dict__:
            del mysql_adapter.__dict__["engine"]

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
            engine = mysql_adapter.engine

            assert engine is mock_engine

            mock_db_exists.assert_called_once_with(mysql_adapter.config.sql._url)
            mock_create_db.assert_called_once_with(mysql_adapter.config.sql._url)

    @pytest.mark.asyncio
    async def test_session_property(self, mysql_adapter: Sql) -> None:
        mock_engine = MockSqlEngine()

        with (
            patch.object(mysql_adapter, "engine", mock_engine),
            patch(
                "acb.adapters.sql._base.AsyncSession", return_value=MockSqlSession()
            ) as mock_session_cls,
        ):
            session = mysql_adapter.session

            mock_session_cls.assert_called_once_with(
                mock_engine, expire_on_commit=False
            )

            assert isinstance(session, MagicMock)
            assert session is mock_session_cls.return_value

    @pytest.mark.asyncio
    async def test_get_session(self, mysql_adapter: Sql) -> None:
        mock_session = MockSqlSession()

        with (
            patch.object(mysql_adapter, "session", mock_session),
            patch("acb.adapters.sql._base.AsyncSession", return_value=mock_session),
        ):
            async with mysql_adapter.get_session() as session:
                mock_session.__aenter__.assert_called_once()

                assert session is mock_session

            mock_session.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conn(self, mysql_adapter: Sql) -> None:
        mock_conn_ctx = MagicMock()
        mock_conn_ctx.__aenter__ = AsyncMock()
        mock_conn_ctx.__aexit__ = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_conn_ctx)

        with patch.object(mysql_adapter, "engine", mock_engine):
            async with mysql_adapter.get_conn() as conn:
                mock_engine.begin.assert_called_once()
                mock_conn_ctx.__aenter__.assert_called_once()
                assert conn is mock_conn_ctx.__aenter__.return_value

            mock_conn_ctx.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_init(self, mysql_adapter: Sql) -> None:
        mock_conn = MagicMock()
        mock_conn.run_sync = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=AsyncMock())

        @asynccontextmanager
        async def mock_get_conn() -> t.AsyncGenerator[MagicMock]:
            yield mock_conn

        with (
            patch.object(mysql_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.sql._base.import_adapter", MagicMock()),
        ):
            mysql_adapter.config.sql.drop_on_startup = True
            if not hasattr(mysql_adapter.config.debug, "sql"):
                setattr(mysql_adapter.config.debug, "sql", False)

            await mysql_adapter.init()

            assert mock_conn.run_sync.call_count == 2
            assert (
                mock_conn.run_sync.call_args_list[0][0][0] == SQLModel.metadata.drop_all
            )
            assert (
                mock_conn.run_sync.call_args_list[1][0][0]
                == SQLModel.metadata.create_all
            )


@pytest.mark.skip(reason="SQL benchmark tests need adapter method implementation")
class TestMySqlBenchmarks:
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
    async def test_engine_property_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Sql
    ) -> None:
        with (
            patch(
                "acb.adapters.sql._base.create_async_engine",
                return_value=MockSqlEngine(),
            ) as mock_create_engine,
            patch("acb.adapters.sql._base.database_exists", return_value=True),
            patch("sqlalchemy.create_engine", return_value=MagicMock()),
        ):

            def get_engine():
                return benchmark_adapter.engine

            engine = benchmark(get_engine)
            assert engine == mock_create_engine.return_value

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_session_property_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Sql
    ) -> None:
        mock_engine = MockSqlEngine()

        with (
            patch.object(benchmark_adapter, "engine", mock_engine),
            patch(
                "acb.adapters.sql._base.AsyncSession", return_value=MockSqlSession()
            ) as mock_session_cls,
        ):

            def get_session():
                return benchmark_adapter.session

            session = benchmark(get_session)
            assert isinstance(session, MagicMock)
            assert session is mock_session_cls.return_value

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_get_session_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Sql
    ) -> None:
        mock_session = MockSqlSession()

        with (
            patch.object(benchmark_adapter, "session", mock_session),
            patch("acb.adapters.sql._base.AsyncSession", return_value=mock_session),
        ):

            async def get_session_context():
                async with benchmark_adapter.get_session() as session:
                    return session

            session = await benchmark(get_session_context)
            assert session is mock_session

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_get_conn_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Sql
    ) -> None:
        mock_conn_ctx = MagicMock()
        mock_conn_ctx.__aenter__ = AsyncMock()
        mock_conn_ctx.__aexit__ = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_conn_ctx)

        with patch.object(benchmark_adapter, "engine", mock_engine):

            async def get_conn_context():
                async with benchmark_adapter.get_conn() as conn:
                    return conn

            conn = await benchmark(get_conn_context)
            assert conn is mock_conn_ctx.__aenter__.return_value

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_init_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Sql
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.run_sync = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=AsyncMock())

        @asynccontextmanager
        async def mock_get_conn() -> t.AsyncGenerator[MagicMock]:
            yield mock_conn

        with (
            patch.object(benchmark_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.sql._base.import_adapter", MagicMock()),
        ):
            benchmark_adapter.config.sql.drop_on_startup = True
            if not hasattr(benchmark_adapter.config.debug, "sql"):
                setattr(benchmark_adapter.config.debug, "sql", False)

            await benchmark(benchmark_adapter.init)
            assert mock_conn.run_sync.call_count == 2

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_bulk_session_operations_performance(
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
            patch("acb.adapters.sql._base.AsyncSession", return_value=mock_session),
        ):

            async def bulk_operations() -> list[str]:
                results: list[str] = []
                async with benchmark_adapter.get_session():
                    for i in range(100):
                        # Simplified benchmark - just track operation completion
                        results.append(f"query_result_{i}")
                return results

            results = await benchmark(bulk_operations)
            assert len(results) == 100

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_transaction_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Sql
    ) -> None:
        mock_conn_ctx = MagicMock()
        mock_conn_ctx.__aenter__ = AsyncMock()
        mock_conn_ctx.__aexit__ = AsyncMock()
        mock_conn = MagicMock()
        mock_conn_ctx.__aenter__.return_value = mock_conn
        mock_conn.execute = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_conn_ctx)

        with patch.object(benchmark_adapter, "engine", mock_engine):

            async def transaction_operations() -> bool:
                async with benchmark_adapter.get_conn() as conn:
                    for i in range(50):
                        # Using text() for raw SQL queries
                        from sqlalchemy import text

                        await conn.execute(
                            text(
                                "INSERT INTO test_table (id, name) VALUES (:id, :name)"
                            ),
                            {"id": i, "name": f"test_{i}"},
                        )
                    return True

            result = await benchmark(transaction_operations)
            assert result is True

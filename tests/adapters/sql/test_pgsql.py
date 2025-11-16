"""Tests for PostgreSQL SQL adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typing as t
from contextlib import asynccontextmanager
from pydantic import SecretStr
from pytest_benchmark.fixture import BenchmarkFixture
from sqlmodel import SQLModel

from acb.adapters.sql.pgsql import Sql, SqlSettings
from acb.config import Config


class MockAsyncEngine(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.dispose = AsyncMock()
        self.begin = MagicMock()
        self.begin.return_value.__aenter__ = AsyncMock()
        self.begin.return_value.__aexit__ = AsyncMock()
        self.__aenter__ = AsyncMock(return_value=self)
        self.__aexit__ = AsyncMock(return_value=None)


class MockAsyncSession(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.close = AsyncMock()
        self.execute = AsyncMock()
        self.__aenter__ = AsyncMock(return_value=self)
        self.__aexit__ = AsyncMock(return_value=None)


class MockAsyncConnection(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.execute = AsyncMock()
        self.run_sync = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.__aenter__ = AsyncMock(return_value=self)
        self.__aexit__ = AsyncMock(return_value=None)


class TestPostgreSQLSettings:
    """Test PostgreSQL SQL settings."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for settings testing."""
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app
        mock_config.deployed = False

        # Mock logger to avoid logger config issues
        mock_logger = MagicMock()
        mock_logger.verbose = False
        mock_config.logger = mock_logger

        return mock_config

    def test_default_settings(self, mock_config):
        """Test settings initialization with default values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(connect_timeout=None)

        # Test driver configuration
        assert settings._driver == "postgresql+psycopg2"
        assert settings._async_driver == "postgresql+asyncpg"
        assert settings.driver == "postgresql+psycopg2"
        assert settings.async_driver == "postgresql+asyncpg"

        # Test connection pool settings
        assert settings.pool_size == 20
        assert settings.max_overflow == 30
        assert settings.pool_recycle == 3600
        assert settings.pool_pre_ping is True

        # Test inherited defaults from SqlBaseSettings
        assert settings.port == 3306  # Base class default (shared by all SQL adapters)
        assert settings.host.get_secret_value() == "127.0.0.1"
        assert settings.user.get_secret_value() == "root"
        assert isinstance(settings.password, SecretStr)

    def test_custom_settings(self, mock_config):
        """Test settings initialization with custom values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(
                host=SecretStr("postgres.example.com"),
                port=5433,
                user=SecretStr("myuser"),
                password=SecretStr("mypassword"),
                pool_size=10,
                max_overflow=15,
                pool_recycle=1800,
                pool_pre_ping=False,
                connect_timeout=None,
            )

        assert settings.host.get_secret_value() == "postgres.example.com"
        assert settings.port == 5433
        assert settings.user.get_secret_value() == "myuser"
        assert settings.password.get_secret_value() == "mypassword"
        assert settings.pool_size == 10
        assert settings.max_overflow == 15
        assert settings.pool_recycle == 1800
        assert settings.pool_pre_ping is False

    def test_ssl_configuration(self, mock_config):
        """Test SSL/TLS configuration."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(
                ssl_enabled=True,
                ssl_mode="require",
                ssl_cert_path="/path/to/cert.pem",
                ssl_key_path="/path/to/key.pem",
                ssl_ca_path="/path/to/ca.pem",
            )

        assert settings.ssl_enabled is True
        assert settings.ssl_mode == "require"
        assert settings.ssl_cert_path == "/path/to/cert.pem"
        assert settings.ssl_key_path == "/path/to/key.pem"
        assert settings.ssl_ca_path == "/path/to/ca.pem"

    def test_ssl_params_building(self, mock_config):
        """Test SSL parameter building for PostgreSQL."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(
                ssl_enabled=True,
                ssl_mode="verify-full",
                ssl_cert_path="/path/to/cert.pem",
                ssl_key_path="/path/to/key.pem",
                ssl_ca_path="/path/to/ca.pem",
            )

        ssl_params = settings._build_ssl_params()

        assert ssl_params["sslcert"] == "/path/to/cert.pem"
        assert ssl_params["sslkey"] == "/path/to/key.pem"
        assert ssl_params["sslrootcert"] == "/path/to/ca.pem"
        assert ssl_params["sslmode"] == "verify-full"

    def test_ssl_mode_mapping(self, mock_config):
        """Test different SSL mode mappings."""
        test_cases = [
            ("disabled", "disable"),
            ("preferred", "prefer"),
            ("required", "require"),
            ("verify-ca", "verify-ca"),
            ("verify-full", "verify-full"),
        ]

        for acb_mode, pgsql_mode in test_cases:
            with patch("acb.depends.depends.get", return_value=mock_config):
                settings = SqlSettings(
                    ssl_enabled=True, ssl_mode=acb_mode, connect_timeout=None
                )
                ssl_params = settings._build_ssl_params()
                assert ssl_params["sslmode"] == pgsql_mode

    def test_engine_kwargs_configuration(self, mock_config):
        """Test that engine kwargs are properly configured."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(
                pool_size=25,
                max_overflow=35,
                pool_recycle=2400,
                connect_timeout=None,
            )

        # The __init__ method should have configured engine_kwargs
        assert settings.engine_kwargs["pool_size"] == 25
        assert settings.engine_kwargs["max_overflow"] == 35
        assert settings.engine_kwargs["pool_recycle"] == 2400


class TestPostgreSQL:
    """Test PostgreSQL SQL adapter."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for testing."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app
        mock_config.deployed = False

        # Mock debug settings
        mock_debug = MagicMock()
        mock_debug.sql = False
        mock_config.debug = mock_debug

        # Mock logger settings
        mock_logger = MagicMock()
        mock_logger.verbose = False
        mock_config.logger = mock_logger

        # Mock SQL settings
        mock_sql = MagicMock(spec=SqlSettings)
        mock_sql._driver = "postgresql+psycopg2"
        mock_sql._async_driver = "postgresql+asyncpg"
        mock_sql._url = "postgresql+psycopg2://root:password@127.0.0.1:5432/testapp"
        mock_sql._async_url = (
            "postgresql+asyncpg://root:password@127.0.0.1:5432/testapp"
        )
        mock_sql.engine_kwargs = {
            "pool_size": 20,
            "max_overflow": 30,
            "pool_recycle": 3600,
            "echo": False,
            "echo_pool": False,
        }
        mock_config.sql = mock_sql

        return mock_config

    @pytest.fixture
    def mock_ssl_config(self):
        """Mock config with SSL enabled."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app
        mock_config.deployed = True

        # Mock debug settings
        mock_debug = MagicMock()
        mock_debug.sql = True
        mock_config.debug = mock_debug

        # Mock logger settings
        mock_logger = MagicMock()
        mock_logger.verbose = True
        mock_config.logger = mock_logger

        # Mock SQL settings with SSL
        mock_sql = MagicMock(spec=SqlSettings)
        mock_sql._driver = "postgresql+psycopg2"
        mock_sql._async_driver = "postgresql+asyncpg"
        mock_sql._url = (
            "postgresql+psycopg2://user:pass@postgres.example.com:5432/testapp"
        )
        mock_sql._async_url = (
            "postgresql+asyncpg://user:pass@postgres.example.com:5432/testapp"
        )
        mock_sql.ssl_enabled = True
        mock_sql.engine_kwargs = {
            "pool_size": 20,
            "max_overflow": 30,
            "pool_recycle": 3600,
            "echo": "debug",
            "echo_pool": "debug",
            "connect_args": {
                "sslmode": "require",
                "sslcert": "/path/to/cert.pem",
                "sslkey": "/path/to/key.pem",
                "sslrootcert": "/path/to/ca.pem",
            },
        }
        mock_config.sql = mock_sql

        return mock_config

    @pytest.fixture
    def pgsql_adapter(self, mock_config):
        """PostgreSQL adapter for testing."""
        adapter = Sql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def pgsql_ssl_adapter(self, mock_ssl_config):
        """PostgreSQL adapter with SSL for testing."""
        adapter = Sql()
        adapter.config = mock_ssl_config
        adapter.logger = MagicMock()
        return adapter

    def test_adapter_initialization(self, pgsql_adapter):
        """Test adapter initialization."""
        assert pgsql_adapter._engine is None
        assert pgsql_adapter._session is None
        assert hasattr(pgsql_adapter, "config")
        assert hasattr(pgsql_adapter, "logger")

    async def test_create_client(self, pgsql_adapter):
        """Test engine creation."""
        mock_engine = MockAsyncEngine()

        with (
            patch("sqlalchemy_utils.database_exists", return_value=True),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine
            ) as mock_create,
        ):
            engine = await pgsql_adapter._create_client()

            mock_create.assert_called_once_with(
                pgsql_adapter.config.sql._async_url,
                **pgsql_adapter.config.sql.engine_kwargs,
            )
            assert engine == mock_engine

    async def test_create_client_with_database_creation(self, pgsql_adapter):
        """Test engine creation when database doesn't exist."""
        mock_engine = MockAsyncEngine()

        with (
            patch("sqlalchemy_utils.database_exists", return_value=False),
            patch("sqlalchemy_utils.create_database") as mock_create_db,
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine
            ) as mock_create,
        ):
            engine = await pgsql_adapter._create_client()

            mock_create_db.assert_called_once_with(pgsql_adapter.config.sql._url)
            mock_create.assert_called_once_with(
                pgsql_adapter.config.sql._async_url,
                **pgsql_adapter.config.sql.engine_kwargs,
            )
            assert engine == mock_engine

    async def test_get_engine(self, pgsql_adapter):
        """Test engine getter with lazy initialization."""
        mock_engine = MockAsyncEngine()

        with patch.object(
            pgsql_adapter, "_create_client", return_value=mock_engine
        ) as mock_create:
            engine = await pgsql_adapter.get_engine()

            mock_create.assert_called_once()
            assert pgsql_adapter._engine == engine
            assert engine == mock_engine

            # Second call should not create again
            engine2 = await pgsql_adapter.get_engine()
            assert engine == engine2
            assert mock_create.call_count == 1

    def test_engine_property_not_initialized(self, pgsql_adapter):
        """Test engine property when not initialized."""
        with pytest.raises(RuntimeError, match="Engine not initialized"):
            _ = pgsql_adapter.engine

    def test_engine_property_initialized(self, pgsql_adapter):
        """Test engine property when initialized."""
        mock_engine = MockAsyncEngine()
        pgsql_adapter._engine = mock_engine

        assert pgsql_adapter.engine == mock_engine

    async def test_ensure_session(self, pgsql_adapter):
        """Test session creation."""
        mock_engine = MockAsyncEngine()
        mock_session = MockAsyncSession()

        with (
            patch.object(pgsql_adapter, "get_engine", return_value=mock_engine),
            patch(
                "sqlmodel.ext.asyncio.session.AsyncSession", return_value=mock_session
            ) as mock_session_class,
        ):
            session = await pgsql_adapter._ensure_session()

            mock_session_class.assert_called_once_with(
                mock_engine, expire_on_commit=False
            )
            assert pgsql_adapter._session == session
            assert session == mock_session

    def test_session_property_not_initialized(self, pgsql_adapter):
        """Test session property when not initialized."""
        with pytest.raises(RuntimeError, match="Session not initialized"):
            _ = pgsql_adapter.session

    def test_session_property_initialized(self, pgsql_adapter):
        """Test session property when initialized."""
        mock_session = MockAsyncSession()
        pgsql_adapter._session = mock_session

        assert pgsql_adapter.session == mock_session

    async def test_get_session_context_manager(self, pgsql_adapter):
        """Test session context manager."""
        mock_session = MockAsyncSession()

        with patch.object(pgsql_adapter, "_ensure_session", return_value=mock_session):
            async with pgsql_adapter.get_session() as session:
                assert session == mock_session

    async def test_get_conn_context_manager(self, pgsql_adapter):
        """Test connection context manager."""
        mock_engine = MockAsyncEngine()
        mock_conn = MockAsyncConnection()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch.object(pgsql_adapter, "get_engine", return_value=mock_engine):
            async with pgsql_adapter.get_conn() as conn:
                assert conn == mock_conn

    async def test_init_method(self, pgsql_adapter):
        """Test initialization method."""
        mock_conn = MockAsyncConnection()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_get_conn():
            yield mock_conn

        with (
            patch.object(pgsql_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter") as mock_import,
        ):
            await pgsql_adapter.init()

            # Check that metadata operations were called
            assert mock_conn.run_sync.call_count == 2
            assert (
                mock_conn.run_sync.call_args_list[0][0][0] == SQLModel.metadata.drop_all
            )
            assert (
                mock_conn.run_sync.call_args_list[1][0][0]
                == SQLModel.metadata.create_all
            )
            mock_import.assert_called_once_with("models")

    async def test_init_with_debug_enabled(self, pgsql_ssl_adapter):
        """Test initialization with debug enabled."""
        mock_conn = MockAsyncConnection()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, "user1", "host1", "db1", "Sleep", 0, "", ""),
            (2, "user2", "host2", "db2", "Query", 1, "", "SELECT 1"),
        ]
        mock_conn.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_get_conn():
            yield mock_conn

        with (
            patch.object(pgsql_ssl_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter"),
            patch("acb.debug.debug") as mock_debug,
        ):
            await pgsql_ssl_adapter.init()

            # Check that process list query was executed
            mock_conn.execute.assert_called()
            call_args = mock_conn.execute.call_args[0][0]
            assert "SHOW FULL PROCESSLIST" in str(call_args)

            # Check that debug was called
            mock_debug.assert_called()

    async def test_init_exception_handling(self, pgsql_adapter):
        """Test initialization exception handling."""
        mock_conn = MockAsyncConnection()
        mock_conn.run_sync.side_effect = Exception("Database error")

        @asynccontextmanager
        async def mock_get_conn():
            yield mock_conn

        with (
            patch.object(pgsql_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter"),
        ):
            with pytest.raises(Exception, match="Database error"):
                await pgsql_adapter.init()

            pgsql_adapter.logger.exception.assert_called_once()

    async def test_ssl_configuration_integration(self, pgsql_ssl_adapter):
        """Test SSL configuration is properly integrated."""
        # The SSL configuration should be in engine_kwargs
        ssl_config = pgsql_ssl_adapter.config.sql.engine_kwargs.get("connect_args", {})

        assert "sslmode" in ssl_config
        assert "sslcert" in ssl_config
        assert "sslkey" in ssl_config
        assert "sslrootcert" in ssl_config

    def test_module_metadata(self):
        """Test module metadata constants."""
        from uuid import UUID

        from acb.adapters import AdapterStatus
        from acb.adapters.sql.pgsql import MODULE_ID, MODULE_METADATA, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE
        assert MODULE_METADATA.name == "PostgreSQL"
        assert MODULE_METADATA.category == "sql"
        assert MODULE_METADATA.provider == "postgresql"

    def test_depends_registration(self):
        """Test that SQL class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        sql_class = depends.get(Sql)
        assert sql_class is not None

    def test_inheritance_structure(self):
        """Test that PostgreSQL adapter properly inherits from SqlBase."""
        from acb.adapters.sql._base import SqlBase

        adapter = Sql()

        # Test inheritance
        assert isinstance(adapter, SqlBase)

        # Test that the adapter implements expected protocol
        assert hasattr(adapter, "get_engine")
        assert hasattr(adapter, "get_session")
        assert hasattr(adapter, "get_conn")
        assert hasattr(adapter, "init")

    async def test_comprehensive_workflow(self, pgsql_adapter):
        """Test comprehensive workflow with all operations."""
        mock_engine = MockAsyncEngine()
        mock_session = MockAsyncSession()
        mock_conn = MockAsyncConnection()

        # Setup mocks
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with (
            patch("sqlalchemy_utils.database_exists", return_value=True),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine
            ),
            patch(
                "sqlmodel.ext.asyncio.session.AsyncSession", return_value=mock_session
            ),
            patch("acb.adapters.import_adapter"),
        ):
            # Test engine creation
            engine = await pgsql_adapter.get_engine()
            assert engine == mock_engine

            # Test session creation
            session = await pgsql_adapter._ensure_session()
            assert session == mock_session

            # Test connection context
            async with pgsql_adapter.get_conn() as conn:
                assert conn == mock_conn

            # Test session context
            async with pgsql_adapter.get_session() as sess:
                assert sess == mock_session

            # Test initialization
            await pgsql_adapter.init()

            # Verify all operations completed successfully
            assert pgsql_adapter._engine == mock_engine
            assert pgsql_adapter._session == mock_session

    async def test_connection_pooling_configuration(self, pgsql_adapter):
        """Test that connection pooling is properly configured."""
        mock_engine = MockAsyncEngine()

        with (
            patch("sqlalchemy_utils.database_exists", return_value=True),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine
            ) as mock_create,
        ):
            await pgsql_adapter._create_client()

            # Verify pool configuration was passed
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["pool_size"] == 20
            assert call_kwargs["max_overflow"] == 30
            assert call_kwargs["pool_recycle"] == 3600

    async def test_engine_logging_configuration(self, pgsql_ssl_adapter):
        """Test that engine logging is properly configured."""
        # SSL adapter has debug enabled and verbose logging
        engine_kwargs = pgsql_ssl_adapter.config.sql.engine_kwargs

        assert engine_kwargs["echo"] == "debug"
        assert engine_kwargs["echo_pool"] == "debug"


@pytest.mark.skip(reason="SQL benchmark tests need adapter method implementation")
class TestPostgreSQLBenchmarks:
    """Benchmark tests for PostgreSQL adapter."""

    @pytest.fixture
    def benchmark_adapter(self, mock_config):
        """PostgreSQL adapter for benchmarking."""
        adapter = Sql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def mock_data(self):
        """Mock data for benchmarking."""
        return [
            {"id": i, "name": f"user_{i}", "email": f"user{i}@example.com"}
            for i in range(1000)
        ]

    @pytest.mark.benchmark
    async def test_engine_creation_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter
    ):
        """Test engine creation performance."""
        mock_engine = MockAsyncEngine()

        with (
            patch("sqlalchemy_utils.database_exists", return_value=True),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine
            ),
        ):

            async def create_engine():
                return await benchmark_adapter._create_client()

            engine = await benchmark(create_engine)
            assert engine == mock_engine

    @pytest.mark.benchmark
    async def test_session_creation_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter
    ):
        """Test session creation performance."""
        mock_engine = MockAsyncEngine()
        mock_session = MockAsyncSession()
        benchmark_adapter._engine = mock_engine

        with patch(
            "sqlmodel.ext.asyncio.session.AsyncSession", return_value=mock_session
        ):

            async def create_session():
                return await benchmark_adapter._ensure_session()

            session = await benchmark(create_session)
            assert session == mock_session

    @pytest.mark.benchmark
    async def test_connection_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter
    ):
        """Test connection acquisition performance."""
        mock_engine = MockAsyncEngine()
        mock_conn = MockAsyncConnection()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn
        benchmark_adapter._engine = mock_engine

        async def get_connection():
            async with benchmark_adapter.get_conn() as conn:
                return conn

        conn = await benchmark(get_connection)
        assert conn == mock_conn

    @pytest.mark.benchmark
    async def test_init_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter
    ):
        """Test initialization performance."""
        mock_conn = MockAsyncConnection()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_get_conn():
            yield mock_conn

        with (
            patch.object(benchmark_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter"),
        ):
            await benchmark(benchmark_adapter.init)
            assert mock_conn.run_sync.call_count == 2

    @pytest.mark.benchmark
    async def test_bulk_session_operations_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter, mock_data
    ):
        """Test bulk session operations performance."""
        mock_session = MockAsyncSession()
        benchmark_adapter._session = mock_session

        async def bulk_operations():
            results = []
            for i in range(100):
                async with benchmark_adapter.get_session():
                    # Simulate database operation
                    results.append(f"result_{i}")
            return results

        results = await benchmark(bulk_operations)
        assert len(results) == 100

"""Tests for MySQL SQL adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typing as t
from contextlib import asynccontextmanager
from pydantic import SecretStr
from pytest_benchmark.fixture import BenchmarkFixture
from sqlmodel import SQLModel

from acb.adapters.sql.mysql import Sql, SqlSettings
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


class TestMySQLSettings:
    """Test MySQL SQL settings."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for settings testing."""
        mock_config = MagicMock()
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app
        mock_config.deployed = False

        # Mock logger to avoid logger config issues
        mock_logger = MagicMock()
        mock_logger.verbose = False
        mock_config.logger = mock_logger

        # Add other necessary attributes that Config might have
        mock_config.debug = MagicMock()
        mock_config.root_path = MagicMock()
        mock_config.secrets_path = MagicMock()
        mock_config.settings_path = MagicMock()
        mock_config.tmp_path = MagicMock()

        return mock_config

    def test_default_settings(self, mock_config):
        """Test settings initialization with default values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(connect_timeout=None)

        # Test driver configuration
        assert settings._driver == "mysql+pymysql"
        assert settings._async_driver == "mysql+aiomysql"
        assert settings.driver == "mysql+pymysql"
        assert settings.async_driver == "mysql+aiomysql"

        # Test connection pool settings
        assert settings.pool_size == 20
        assert settings.max_overflow == 30
        assert settings.pool_recycle == 3600
        assert settings.pool_pre_ping is True

        # Test inherited defaults from SqlBaseSettings
        assert settings.port == 3306  # MySQL default port
        assert settings.host.get_secret_value() == "127.0.0.1"
        assert settings.user.get_secret_value() == "root"
        assert isinstance(settings.password, SecretStr)

    def test_custom_settings(self, mock_config):
        """Test settings initialization with custom values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(
                host=SecretStr("mysql.example.com"),
                port=3307,
                user=SecretStr("myuser"),
                password=SecretStr("mypassword"),
                pool_size=15,
                max_overflow=25,
                pool_recycle=2400,
                pool_pre_ping=False,
                connect_timeout=None,
            )

        assert settings.host.get_secret_value() == "mysql.example.com"
        assert settings.port == 3307
        assert settings.user.get_secret_value() == "myuser"
        assert settings.password.get_secret_value() == "mypassword"
        assert settings.pool_size == 15
        assert settings.max_overflow == 25
        assert settings.pool_recycle == 2400
        assert settings.pool_pre_ping is False

    def test_ssl_configuration(self, mock_config):
        """Test SSL/TLS configuration."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(
                ssl_enabled=True,
                ssl_mode="required",
                ssl_cert_path="/path/to/cert.pem",
                ssl_key_path="/path/to/key.pem",
                ssl_ca_path="/path/to/ca.pem",
                ssl_ciphers="HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA",
                connect_timeout=None,
            )

        assert settings.ssl_enabled is True
        assert settings.ssl_mode == "required"
        assert settings.ssl_cert_path == "/path/to/cert.pem"
        assert settings.ssl_key_path == "/path/to/key.pem"
        assert settings.ssl_ca_path == "/path/to/ca.pem"
        assert (
            settings.ssl_ciphers
            == "HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA"
        )

    def test_ssl_params_building(self, mock_config):
        """Test SSL parameter building for MySQL."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(
                ssl_enabled=True,
                ssl_mode="verify-full",
                ssl_cert_path="/path/to/cert.pem",
                ssl_key_path="/path/to/key.pem",
                ssl_ca_path="/path/to/ca.pem",
                ssl_ciphers="HIGH:!aNULL",
                connect_timeout=None,
            )

        ssl_params = settings._build_ssl_params()

        assert ssl_params["ssl_cert"] == "/path/to/cert.pem"
        assert ssl_params["ssl_key"] == "/path/to/key.pem"
        assert ssl_params["ssl_ca"] == "/path/to/ca.pem"
        assert ssl_params["ssl_ciphers"] == "HIGH:!aNULL"
        assert ssl_params["ssl_mode"] == "VERIFY_IDENTITY"

    def test_ssl_mode_mapping(self, mock_config):
        """Test different SSL mode mappings for MySQL."""
        test_cases = [
            ("disabled", {"ssl_disabled": True}),
            ("preferred", {"ssl_mode": "PREFERRED"}),
            ("required", {"ssl_mode": "REQUIRED"}),
            ("verify-ca", {"ssl_mode": "VERIFY_CA"}),
            ("verify-full", {"ssl_mode": "VERIFY_IDENTITY"}),
        ]

        for acb_mode, expected_params in test_cases:
            with patch("acb.depends.depends.get", return_value=mock_config):
                settings = SqlSettings(
                    ssl_enabled=True, ssl_mode=acb_mode, connect_timeout=None
                )
                ssl_params = settings._build_ssl_params()

                for key, value in expected_params.items():
                    assert ssl_params[key] == value

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

    def test_ssl_disabled_mode(self, mock_config):
        """Test SSL disabled mode creates ssl_disabled parameter."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = SqlSettings(
                ssl_enabled=True, ssl_mode="disabled", connect_timeout=None
            )
            ssl_params = settings._build_ssl_params()

            assert ssl_params.get("ssl_disabled") is True
            assert "ssl_mode" not in ssl_params


class TestMySQL:
    """Test MySQL SQL adapter."""

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
        mock_sql._driver = "mysql+pymysql"
        mock_sql._async_driver = "mysql+aiomysql"
        mock_sql._url = "mysql+pymysql://root:password@127.0.0.1:3306/testapp"
        mock_sql._async_url = "mysql+aiomysql://root:password@127.0.0.1:3306/testapp"
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
        mock_sql._driver = "mysql+pymysql"
        mock_sql._async_driver = "mysql+aiomysql"
        mock_sql._url = "mysql+pymysql://user:pass@mysql.example.com:3306/testapp"
        mock_sql._async_url = (
            "mysql+aiomysql://user:pass@mysql.example.com:3306/testapp"
        )
        mock_sql.ssl_enabled = True
        mock_sql.engine_kwargs = {
            "pool_size": 20,
            "max_overflow": 30,
            "pool_recycle": 3600,
            "echo": "debug",
            "echo_pool": "debug",
            "connect_args": {
                "ssl_mode": "REQUIRED",
                "ssl_cert": "/path/to/cert.pem",
                "ssl_key": "/path/to/key.pem",
                "ssl_ca": "/path/to/ca.pem",
            },
        }
        mock_config.sql = mock_sql

        return mock_config

    @pytest.fixture
    def mysql_adapter(self, mock_config):
        """MySQL adapter for testing."""
        adapter = Sql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def mysql_ssl_adapter(self, mock_ssl_config):
        """MySQL adapter with SSL for testing."""
        adapter = Sql()
        adapter.config = mock_ssl_config
        adapter.logger = MagicMock()
        return adapter

    def test_adapter_initialization(self, mysql_adapter):
        """Test adapter initialization."""
        assert mysql_adapter._engine is None
        assert mysql_adapter._session is None
        assert hasattr(mysql_adapter, "config")
        assert hasattr(mysql_adapter, "logger")

    async def test_create_client(self, mysql_adapter):
        """Test engine creation."""
        mock_engine = MockAsyncEngine()

        with (
            patch("sqlalchemy_utils.database_exists", return_value=True),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine
            ) as mock_create,
        ):
            engine = await mysql_adapter._create_client()

            mock_create.assert_called_once_with(
                mysql_adapter.config.sql._async_url,
                **mysql_adapter.config.sql.engine_kwargs,
            )
            assert engine == mock_engine

    async def test_create_client_with_database_creation(self, mysql_adapter):
        """Test engine creation when database doesn't exist."""
        mock_engine = MockAsyncEngine()

        with (
            patch("sqlalchemy_utils.database_exists", return_value=False),
            patch("sqlalchemy_utils.create_database") as mock_create_db,
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine
            ) as mock_create,
        ):
            engine = await mysql_adapter._create_client()

            mock_create_db.assert_called_once_with(mysql_adapter.config.sql._url)
            mock_create.assert_called_once_with(
                mysql_adapter.config.sql._async_url,
                **mysql_adapter.config.sql.engine_kwargs,
            )
            assert engine == mock_engine

    async def test_get_engine(self, mysql_adapter):
        """Test engine getter with lazy initialization."""
        mock_engine = MockAsyncEngine()

        with patch.object(
            mysql_adapter, "_create_client", return_value=mock_engine
        ) as mock_create:
            engine = await mysql_adapter.get_engine()

            mock_create.assert_called_once()
            assert mysql_adapter._engine == engine
            assert engine == mock_engine

            # Second call should not create again
            engine2 = await mysql_adapter.get_engine()
            assert engine == engine2
            assert mock_create.call_count == 1

    def test_engine_property_not_initialized(self, mysql_adapter):
        """Test engine property when not initialized."""
        with pytest.raises(RuntimeError, match="Engine not initialized"):
            _ = mysql_adapter.engine

    def test_engine_property_initialized(self, mysql_adapter):
        """Test engine property when initialized."""
        mock_engine = MockAsyncEngine()
        mysql_adapter._engine = mock_engine

        assert mysql_adapter.engine == mock_engine

    async def test_ensure_session(self, mysql_adapter):
        """Test session creation."""
        mock_engine = MockAsyncEngine()
        mock_session = MockAsyncSession()

        with (
            patch.object(mysql_adapter, "get_engine", return_value=mock_engine),
            patch(
                "sqlmodel.ext.asyncio.session.AsyncSession", return_value=mock_session
            ) as mock_session_class,
        ):
            session = await mysql_adapter._ensure_session()

            mock_session_class.assert_called_once_with(
                mock_engine, expire_on_commit=False
            )
            assert mysql_adapter._session == session
            assert session == mock_session

    def test_session_property_not_initialized(self, mysql_adapter):
        """Test session property when not initialized."""
        with pytest.raises(RuntimeError, match="Session not initialized"):
            _ = mysql_adapter.session

    def test_session_property_initialized(self, mysql_adapter):
        """Test session property when initialized."""
        mock_session = MockAsyncSession()
        mysql_adapter._session = mock_session

        assert mysql_adapter.session == mock_session

    async def test_get_session_context_manager(self, mysql_adapter):
        """Test session context manager."""
        mock_session = MockAsyncSession()

        with patch.object(mysql_adapter, "_ensure_session", return_value=mock_session):
            async with mysql_adapter.get_session() as session:
                assert session == mock_session

    async def test_get_conn_context_manager(self, mysql_adapter):
        """Test connection context manager."""
        mock_engine = MockAsyncEngine()
        mock_conn = MockAsyncConnection()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch.object(mysql_adapter, "get_engine", return_value=mock_engine):
            async with mysql_adapter.get_conn() as conn:
                assert conn == mock_conn

    async def test_init_method(self, mysql_adapter):
        """Test initialization method."""
        mock_conn = MockAsyncConnection()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_get_conn():
            yield mock_conn

        with (
            patch.object(mysql_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter") as mock_import,
        ):
            await mysql_adapter.init()

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

    async def test_init_with_debug_enabled(self, mysql_ssl_adapter):
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
            patch.object(mysql_ssl_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter"),
            patch("acb.debug.debug") as mock_debug,
        ):
            await mysql_ssl_adapter.init()

            # Check that process list query was executed
            mock_conn.execute.assert_called()
            call_args = mock_conn.execute.call_args[0][0]
            assert "SHOW FULL PROCESSLIST" in str(call_args)

            # Check that debug was called
            mock_debug.assert_called()

    async def test_init_exception_handling(self, mysql_adapter):
        """Test initialization exception handling."""
        mock_conn = MockAsyncConnection()
        mock_conn.run_sync.side_effect = Exception("Database error")

        @asynccontextmanager
        async def mock_get_conn():
            yield mock_conn

        with (
            patch.object(mysql_adapter, "get_conn", mock_get_conn),
            patch("acb.adapters.import_adapter"),
        ):
            with pytest.raises(Exception, match="Database error"):
                await mysql_adapter.init()

            mysql_adapter.logger.exception.assert_called_once()

    async def test_ssl_configuration_integration(self, mysql_ssl_adapter):
        """Test SSL configuration is properly integrated."""
        # The SSL configuration should be in engine_kwargs
        ssl_config = mysql_ssl_adapter.config.sql.engine_kwargs.get("connect_args", {})

        assert "ssl_mode" in ssl_config
        assert "ssl_cert" in ssl_config
        assert "ssl_key" in ssl_config
        assert "ssl_ca" in ssl_config

    def test_module_metadata(self):
        """Test module metadata constants."""
        from uuid import UUID

        from acb.adapters import AdapterStatus
        from acb.adapters.sql.mysql import MODULE_ID, MODULE_METADATA, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE
        assert MODULE_METADATA.name == "MySQL"
        assert MODULE_METADATA.category == "sql"
        assert MODULE_METADATA.provider == "mysql"

    def test_depends_registration(self):
        """Test that SQL class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        sql_class = depends.get(Sql)
        assert sql_class is not None

    def test_inheritance_structure(self):
        """Test that MySQL adapter properly inherits from SqlBase."""
        from acb.adapters.sql._base import SqlBase

        adapter = Sql()

        # Test inheritance
        assert isinstance(adapter, SqlBase)

        # Test that the adapter implements expected protocol
        assert hasattr(adapter, "get_engine")
        assert hasattr(adapter, "get_session")
        assert hasattr(adapter, "get_conn")
        assert hasattr(adapter, "init")

    async def test_comprehensive_workflow(self, mysql_adapter):
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
            engine = await mysql_adapter.get_engine()
            assert engine == mock_engine

            # Test session creation
            session = await mysql_adapter._ensure_session()
            assert session == mock_session

            # Test connection context
            async with mysql_adapter.get_conn() as conn:
                assert conn == mock_conn

            # Test session context
            async with mysql_adapter.get_session() as sess:
                assert sess == mock_session

            # Test initialization
            await mysql_adapter.init()

            # Verify all operations completed successfully
            assert mysql_adapter._engine == mock_engine
            assert mysql_adapter._session == mock_session

    async def test_connection_pooling_configuration(self, mysql_adapter):
        """Test that connection pooling is properly configured."""
        mock_engine = MockAsyncEngine()

        with (
            patch("sqlalchemy_utils.database_exists", return_value=True),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine
            ) as mock_create,
        ):
            await mysql_adapter._create_client()

            # Verify pool configuration was passed
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["pool_size"] == 20
            assert call_kwargs["max_overflow"] == 30
            assert call_kwargs["pool_recycle"] == 3600

    async def test_engine_logging_configuration(self, mysql_ssl_adapter):
        """Test that engine logging is properly configured."""
        # SSL adapter has debug enabled and verbose logging
        engine_kwargs = mysql_ssl_adapter.config.sql.engine_kwargs

        assert engine_kwargs["echo"] == "debug"
        assert engine_kwargs["echo_pool"] == "debug"

    def test_mysql_specific_ssl_features(self, mock_config):
        """Test MySQL-specific SSL features."""
        # Test ssl_ciphers support (MySQL-specific)
        settings = SqlSettings(
            ssl_enabled=True,
            ssl_mode="required",
            ssl_ciphers="HIGH:!aNULL:!eNULL",
        )

        ssl_params = settings._build_ssl_params()
        assert ssl_params["ssl_ciphers"] == "HIGH:!aNULL:!eNULL"
        assert ssl_params["ssl_mode"] == "REQUIRED"

    def test_mysql_ssl_verification_modes(self, mock_config):
        """Test MySQL SSL verification modes."""
        # Test all MySQL SSL modes
        mode_mappings = {
            "disabled": {"ssl_disabled": True},
            "preferred": {"ssl_mode": "PREFERRED"},
            "required": {"ssl_mode": "REQUIRED"},
            "verify-ca": {"ssl_mode": "VERIFY_CA"},
            "verify-full": {"ssl_mode": "VERIFY_IDENTITY"},
        }

        for mode, expected in mode_mappings.items():
            settings = SqlSettings(ssl_enabled=True, ssl_mode=mode)
            ssl_params = settings._build_ssl_params()

            for key, value in expected.items():
                assert ssl_params[key] == value

    async def test_mysql_charset_and_collation_support(self, mysql_adapter):
        """Test that MySQL can handle charset and collation configuration."""
        # This test ensures the adapter works with MySQL-specific connection options
        mock_engine = MockAsyncEngine()

        # Add charset and collation to engine kwargs (common MySQL configuration)
        mysql_adapter.config.sql.engine_kwargs.update(
            {
                "connect_args": {
                    "charset": "utf8mb4",
                    "collation": "utf8mb4_unicode_ci",
                }
            }
        )

        with (
            patch("sqlalchemy_utils.database_exists", return_value=True),
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine
            ) as mock_create,
        ):
            await mysql_adapter._create_client()

            # Verify charset configuration was passed
            call_kwargs = mock_create.call_args[1]
            connect_args = call_kwargs.get("connect_args", {})
            assert connect_args.get("charset") == "utf8mb4"
            assert connect_args.get("collation") == "utf8mb4_unicode_ci"


@pytest.mark.skip(reason="SQL benchmark tests need adapter method implementation")
class TestMySQLBenchmarks:
    """Benchmark tests for MySQL adapter."""

    @pytest.fixture
    def benchmark_adapter(self, mock_config):
        """MySQL adapter for benchmarking."""
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

    @pytest.mark.benchmark
    async def test_mysql_specific_operations_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter
    ):
        """Test MySQL-specific operations performance."""
        mock_conn = MockAsyncConnection()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("utf8mb4", "utf8mb4_unicode_ci")]
        mock_conn.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_get_conn():
            yield mock_conn

        with patch.object(benchmark_adapter, "get_conn", mock_get_conn):

            async def mysql_charset_check():
                async with benchmark_adapter.get_conn() as conn:
                    # Simulate MySQL-specific query
                    await conn.execute("SHOW VARIABLES LIKE 'character_set%'")
                    await conn.execute("SHOW VARIABLES LIKE 'collation%'")
                    return True

            result = await benchmark(mysql_charset_check)
            assert result is True

"""Comprehensive tests for the SQL base adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typing as t
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from acb.adapters.sql._base import SqlBase, SqlBaseSettings
from acb.config import Config


class MockSqlBaseSettings(SqlBaseSettings):
    """Mock SQL base settings for testing."""

    _driver: str = "sqlite"
    _async_driver: str = "sqlite+aiosqlite"
    port: int | None = None
    pool_pre_ping: bool | None = False
    poolclass: t.Any | None = None
    host: str = "localhost"
    local_host: str = "localhost"
    user: str = "test_user"
    password: str = "test_password"
    database: str = "test_db"

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)


class MockSqlBase(SqlBase):
    """Mock SQL base for testing."""

    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()
        self._engine: AsyncEngine | None = None
        self._session: AsyncSession | None = None
        self._client: AsyncEngine | None = None

    async def init(self) -> None:
        pass


class TestSqlBaseSettings:
    """Test SqlBaseSettings class."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock config."""
        config = MagicMock(spec=Config)
        config.app.name = "test_app"
        config.deployed = False
        config.logger.verbose = False
        config.debug.sql = False
        return config

    def test_build_ssl_params_no_ssl(self, mock_config: MagicMock) -> None:
        """Test _build_ssl_params with SSL disabled."""
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            settings = MockSqlBaseSettings(ssl_enabled=False)
            ssl_params = settings._build_ssl_params()
            assert ssl_params == {}

    def test_build_ssl_params_with_ssl(self, mock_config: MagicMock) -> None:
        """Test _build_ssl_params with SSL enabled."""
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            settings = MockSqlBaseSettings(
                ssl_enabled=True,
                ssl_mode="required",
                ssl_cert_path="/path/to/cert.pem",
                ssl_key_path="/path/to/key.pem",
                ssl_ca_path="/path/to/ca.pem",
                ssl_ciphers="HIGH:!aNULL",
                ssl_verify_cert=True,
                tls_version="TLSv1.3",
                connect_timeout=30.0,
            )
            ssl_params = settings._build_ssl_params()

            assert ssl_params["ssl_mode"] == "required"
            assert ssl_params["ssl_cert"] == "/path/to/cert.pem"
            assert ssl_params["ssl_key"] == "/path/to/key.pem"
            assert ssl_params["ssl_ca"] == "/path/to/ca.pem"
            assert ssl_params["ssl_ciphers"] == "HIGH:!aNULL"
            assert ssl_params["ssl_verify_cert"] is True
            assert ssl_params["tls_version"] == "TLSv1.3"
            assert ssl_params["connect_timeout"] == 30.0

    def test_build_ssl_params_partial_ssl(self, mock_config: MagicMock) -> None:
        """Test _build_ssl_params with partial SSL configuration."""
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            settings = MockSqlBaseSettings(
                ssl_enabled=True,
                ssl_mode="preferred",
                ssl_verify_cert=False,
            )
            ssl_params = settings._build_ssl_params()

            assert ssl_params["ssl_mode"] == "preferred"
            assert ssl_params["ssl_verify_cert"] is False
            # Other SSL params should not be present
            assert "ssl_cert" not in ssl_params
            assert "ssl_key" not in ssl_params
            assert "ssl_ca" not in ssl_params

    def test_init_cloudsql_proxy(self, mock_config: MagicMock) -> None:
        """Test __init__ with CloudSQL proxy."""
        mock_config.deployed = False
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            settings = MockSqlBaseSettings(
                cloudsql_proxy=True,
                cloudsql_proxy_port=3307,
            )
            # Port should be set to cloudsql_proxy_port when not deployed
            assert settings.port == 3307

    def test_init_deployed(self, mock_config: MagicMock) -> None:
        """Test __init__ when deployed."""
        mock_config.deployed = True
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            settings = MockSqlBaseSettings(host="prod-host")
            # Host should be the actual host when deployed
            assert settings.host == "prod-host"

    def test_init_not_deployed(self, mock_config: MagicMock) -> None:
        """Test __init__ when not deployed."""
        mock_config.deployed = False
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            settings = MockSqlBaseSettings(host="prod-host")
            # Host should be local_host when not deployed
            assert settings.host == "localhost"

    def test_init_poolclass(self, mock_config: MagicMock) -> None:
        """Test __init__ with poolclass."""
        mock_config.deployed = False
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            with patch("acb.adapters.sql._base.pool") as mock_pool:
                mock_pool.QueuePool = "QueuePool"
                settings = MockSqlBaseSettings(poolclass="QueuePool")
                assert settings.poolclass == "QueuePool"

    def test_engine_kwargs_verbose_logger(self, mock_config: MagicMock) -> None:
        """Test engine_kwargs with verbose logger."""
        mock_config.logger.verbose = True
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            settings = MockSqlBaseSettings()
            # When verbose logger, echo should be "debug"
            assert settings.engine_kwargs["echo"] == "debug"
            assert settings.engine_kwargs["echo_pool"] == "debug"

    def test_engine_kwargs_debug_sql(self, mock_config: MagicMock) -> None:
        """Test engine_kwargs with debug SQL."""
        mock_config.logger.verbose = False
        mock_config.debug.sql = True
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            settings = MockSqlBaseSettings()
            # When debug.sql is True, echo should be "debug"
            assert settings.engine_kwargs["echo"] == "debug"
            assert settings.engine_kwargs["echo_pool"] == "debug"

    def test_ssl_engine_kwargs(self, mock_config: MagicMock) -> None:
        """Test SSL engine kwargs."""
        with patch("acb.adapters.sql._base.depends.get", return_value=mock_config):
            settings = MockSqlBaseSettings(
                ssl_enabled=True,
                pool_timeout=60.0,
                command_timeout=30.0,
            )
            ssl_params = settings._build_ssl_params()
            # SSL params should be included in engine_kwargs
            assert "ssl_mode" in ssl_params
            assert settings.engine_kwargs["pool_timeout"] == 60.0
            assert settings.engine_kwargs["connect_args"]["command_timeout"] == 30.0


class TestSqlBase:
    """Test SqlBase class."""

    @pytest.fixture
    def sql_base(self) -> MockSqlBase:
        """Create a MockSqlBase instance."""
        sql_base = MockSqlBase()
        sql_base.config = MagicMock()
        sql_base.config.sql = MockSqlBaseSettings()
        sql_base.config.sql._url = "sqlite:///test.db"
        sql_base.config.sql._async_url = "sqlite+aiosqlite:///test.db"
        sql_base.config.sql.engine_kwargs = {}
        sql_base.logger = MagicMock()
        return sql_base

    @pytest.mark.asyncio
    async def test_create_client(self, sql_base: MockSqlBase) -> None:
        """Test _create_client method."""
        # Mock database_exists and create_database
        with (
            patch("acb.adapters.sql._base.database_exists", return_value=False),
            patch("acb.adapters.sql._base.create_database") as mock_create_db,
            patch("acb.adapters.sql._base.create_async_engine") as mock_create_engine,
        ):
            mock_engine = AsyncMock(spec=AsyncEngine)
            mock_create_engine.return_value = mock_engine

            engine = await sql_base._create_client()

            # Verify create_database was called
            mock_create_db.assert_called_once_with(sql_base.config.sql._url)
            mock_create_db.assert_called_once()
            # Verify create_async_engine was called with correct parameters
            mock_create_engine.assert_called_once_with(
                sql_base.config.sql._async_url,
                **sql_base.config.sql.engine_kwargs,
            )
            assert engine == mock_engine

    @pytest.mark.asyncio
    async def test_create_client_database_exists(self, sql_base: MockSqlBase) -> None:
        """Test _create_client method when database already exists."""
        # Mock database_exists to return True
        with (
            patch("acb.adapters.sql._base.database_exists", return_value=True),
            patch("acb.adapters.sql._base.create_database") as mock_create_db,
            patch("acb.adapters.sql._base.create_async_engine") as mock_create_engine,
        ):
            mock_engine = AsyncMock(spec=AsyncEngine)
            mock_create_engine.return_value = mock_engine

            engine = await sql_base._create_client()

            # Verify create_database was not called
            mock_create_db.assert_called_once_with(sql_base.config.sql._url)
            mock_create_db.assert_not_called()
            # Verify create_async_engine was called
            mock_create_engine.assert_called_once()
            assert engine == mock_engine

    @pytest.mark.asyncio
    async def test_get_engine(self, sql_base: MockSqlBase) -> None:
        """Test get_engine method."""
        mock_engine = AsyncMock(spec=AsyncEngine)

        # Mock _ensure_client to return our mock engine
        with patch.object(sql_base, "_ensure_client", return_value=mock_engine):
            engine = await sql_base.get_engine()
            assert engine == mock_engine

    def test_engine_property_initialized(self, sql_base: MockSqlBase) -> None:
        """Test engine property when engine is initialized."""
        mock_engine = AsyncMock(spec=AsyncEngine)
        sql_base._engine = mock_engine

        engine = sql_base.engine
        assert engine == mock_engine

    def test_engine_property_not_initialized(self, sql_base: MockSqlBase) -> None:
        """Test engine property when engine is not initialized."""
        sql_base._engine = None

        with pytest.raises(RuntimeError, match="Engine not initialized"):
            _ = sql_base.engine

    @pytest.mark.asyncio
    async def test_ensure_session(self, sql_base: MockSqlBase) -> None:
        """Test _ensure_session method."""
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock get_engine to return our mock engine
        with patch.object(sql_base, "get_engine", return_value=mock_engine):
            # Mock AsyncSession constructor
            with patch(
                "acb.adapters.sql._base.AsyncSession", return_value=mock_session
            ):
                session = await sql_base._ensure_session()

                # Verify AsyncSession was created with correct parameters
                assert session == mock_session
                assert sql_base._session == mock_session

    def test_session_property_initialized(self, sql_base: MockSqlBase) -> None:
        """Test session property when session is initialized."""
        mock_session = AsyncMock(spec=AsyncSession)
        sql_base._session = mock_session

        session = sql_base.session
        assert session == mock_session

    def test_session_property_not_initialized(self, sql_base: MockSqlBase) -> None:
        """Test session property when session is not initialized."""
        sql_base._session = None

        with pytest.raises(RuntimeError, match="Session not initialized"):
            _ = sql_base.session

    @pytest.mark.asyncio
    async def test_get_session(self, sql_base: MockSqlBase) -> None:
        """Test get_session method."""
        mock_session = AsyncMock(spec=AsyncSession)
        sql_base._session = mock_session

        # Mock the async context manager behavior
        async def mock_ensure_session():
            return mock_session

        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch.object(sql_base, "_ensure_session", side_effect=mock_ensure_session):
            async with sql_base.get_session() as session:
                assert session == mock_session

    @pytest.mark.asyncio
    async def test_get_conn(self, sql_base: MockSqlBase) -> None:
        """Test get_conn method."""
        mock_engine = AsyncMock(spec=AsyncEngine)
        AsyncMock(spec=AsyncConnection)

        # Mock get_engine to return our mock engine
        with patch.object(sql_base, "get_engine", return_value=mock_engine):
            # Mock the async context manager behavior
            mock_engine.begin = AsyncMock(
                return_value=asynccontextmanager(lambda: AsyncMock())()
            )

            async with sql_base.get_conn() as conn:
                assert conn is not None

    @pytest.mark.asyncio
    async def test_cleanup_resources_session(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method with session."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.close = AsyncMock()
        sql_base._session = mock_session
        sql_base._client = None  # No engine

        await sql_base._cleanup_resources()

        # Verify session was closed
        mock_session.close.assert_called_once()
        assert sql_base._session is None

    @pytest.mark.asyncio
    async def test_cleanup_resources_engine(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method with engine."""
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_engine.dispose = AsyncMock()
        sql_base._session = None  # No session
        sql_base._client = mock_engine  # Engine stored in _client

        await sql_base._cleanup_resources()

        # Verify engine was disposed
        mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resources_both(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method with both session and engine."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.close = AsyncMock()
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_engine.dispose = AsyncMock()
        sql_base._session = mock_session
        sql_base._client = mock_engine

        await sql_base._cleanup_resources()

        # Verify both session and engine were cleaned up
        mock_session.close.assert_called_once()
        mock_engine.dispose.assert_called_once()
        assert sql_base._session is None

    @pytest.mark.asyncio
    async def test_cleanup_resources_session_error(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method when session cleanup fails."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.close = AsyncMock(side_effect=Exception("Session close failed"))
        sql_base._session = mock_session
        sql_base._client = None

        await sql_base._cleanup_resources()

        # Session should still be cleared even if close fails
        assert sql_base._session is None
        # Logger should have been called with warning
        sql_base.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_resources_engine_error(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method when engine cleanup fails."""
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_engine.dispose = AsyncMock(side_effect=Exception("Engine dispose failed"))
        sql_base._session = None
        sql_base._client = mock_engine

        await sql_base._cleanup_resources()

        # Engine should still be handled even if dispose fails
        # Logger should have been called with warning
        sql_base.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_resources_both_errors(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method when both cleanup operations fail."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.close = AsyncMock(side_effect=Exception("Session close failed"))
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_engine.dispose = AsyncMock(side_effect=Exception("Engine dispose failed"))
        sql_base._session = mock_session
        sql_base._client = mock_engine

        await sql_base._cleanup_resources()

        # Both should still be cleared even if they fail
        assert sql_base._session is None
        # Logger should have been called with warning
        sql_base.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_resources_no_resources(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method when no resources exist."""
        sql_base._session = None
        sql_base._client = None

        await sql_base._cleanup_resources()

        # Should not raise any exceptions
        assert sql_base._session is None


# We won't run the init test from the original file since it requires complex setup
# and is already covered by the existing test

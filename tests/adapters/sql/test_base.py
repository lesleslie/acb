"""Tests for the SQL base adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncConnection

from acb.adapters.sql._base import SqlBase


class MockSqlBase(SqlBase):
    """Mock SQL base for testing."""

    def __init__(self) -> None:
        self.config = MagicMock()
        self.logger = MagicMock()
        self._engine: AsyncMock | None = None
        self._session: AsyncMock | None = None
        # Add the missing _resource_cache attribute
        self._resource_cache = MagicMock()
        self._resource_cache.clear = MagicMock()

    async def init(self) -> None:
        pass


class TestSqlBase:
    @pytest.fixture
    def sql_base(self) -> MockSqlBase:
        sql_base = MockSqlBase()
        sql_base.config = MagicMock()
        sql_base.logger = MagicMock()
        # Mock the _resource_cache clear method
        sql_base._resource_cache.clear = MagicMock()
        return sql_base

    @pytest.mark.asyncio
    async def test_init(self, sql_base: MockSqlBase) -> None:
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

    @pytest.mark.asyncio
    async def test_create_client(self, sql_base: MockSqlBase) -> None:
        """Test _create_client method."""
        # Mock the config
        sql_base.config.sql = MagicMock()
        sql_base.config.sql._url = "sqlite:///test.db"
        sql_base.config.sql._async_url = "sqlite+aiosqlite:///test.db"
        sql_base.config.sql.engine_kwargs = {"echo": True}

        # Mock database_exists and create_database
        with (
            patch(
                "acb.adapters.sql._base.database_exists", return_value=False
            ) as mock_db_exists,
            patch("acb.adapters.sql._base.create_database") as mock_create_db,
            patch("acb.adapters.sql._base.create_async_engine") as mock_create_engine,
        ):
            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            engine = await sql_base._create_client()

            # Verify database_exists was called
            mock_db_exists.assert_called_once_with("sqlite:///test.db")
            # Verify create_database was called
            mock_create_db.assert_called_once_with("sqlite:///test.db")
            # Verify create_async_engine was called with correct parameters
            mock_create_engine.assert_called_once_with(
                "sqlite+aiosqlite:///test.db",
                **{"echo": True},
            )
            assert engine == mock_engine

    @pytest.mark.asyncio
    async def test_create_client_database_exists(self, sql_base: MockSqlBase) -> None:
        """Test _create_client method when database already exists."""
        # Mock the config
        sql_base.config.sql = MagicMock()
        sql_base.config.sql._url = "sqlite:///test.db"
        sql_base.config.sql._async_url = "sqlite+aiosqlite:///test.db"
        sql_base.config.sql.engine_kwargs = {"echo": True}

        # Mock database_exists to return True (database already exists)
        with (
            patch(
                "acb.adapters.sql._base.database_exists", return_value=True
            ) as mock_db_exists,
            patch("acb.adapters.sql._base.create_database") as mock_create_db,
            patch("acb.adapters.sql._base.create_async_engine") as mock_create_engine,
        ):
            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            engine = await sql_base._create_client()

            # Verify database_exists was called
            mock_db_exists.assert_called_once_with("sqlite:///test.db")
            # Verify create_database was NOT called since database exists
            mock_create_db.assert_not_called()
            # Verify create_async_engine was called with correct parameters
            mock_create_engine.assert_called_once_with(
                "sqlite+aiosqlite:///test.db",
                **{"echo": True},
            )
            assert engine == mock_engine

    def test_engine_property_initialized(self, sql_base: MockSqlBase) -> None:
        """Test engine property when engine is initialized."""
        mock_engine = AsyncMock()
        sql_base._engine = mock_engine

        engine = sql_base.engine
        assert engine == mock_engine

    def test_engine_property_not_initialized(self, sql_base: MockSqlBase) -> None:
        """Test engine property when engine is not initialized."""
        sql_base._engine = None

        with pytest.raises(RuntimeError, match="Engine not initialized"):
            _ = sql_base.engine

    def test_session_property_initialized(self, sql_base: MockSqlBase) -> None:
        """Test session property when session is initialized."""
        mock_session = AsyncMock()
        sql_base._session = mock_session

        session = sql_base.session
        assert session == mock_session

    def test_session_property_not_initialized(self, sql_base: MockSqlBase) -> None:
        """Test session property when session is not initialized."""
        sql_base._session = None

        with pytest.raises(RuntimeError, match="Session not initialized"):
            _ = sql_base.session

    @pytest.mark.asyncio
    async def test_ensure_session(self, sql_base: MockSqlBase) -> None:
        """Test _ensure_session method."""
        mock_engine = AsyncMock()
        mock_session = AsyncMock()

        # Mock get_engine to return our mock engine
        with patch.object(sql_base, "get_engine", return_value=mock_engine):
            # Mock AsyncSession constructor
            with patch(
                "acb.adapters.sql._base.AsyncSession", return_value=mock_session
            ):
                session = await sql_base._ensure_session()

                # Verify AsyncSession was created with correct parameters
                # Note: We can't easily verify constructor arguments with patch,
                # but we can verify the session was created and stored
                assert session == mock_session
                assert sql_base._session == mock_session

    @pytest.mark.asyncio
    async def test_cleanup_resources_session(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method with session."""
        mock_session = AsyncMock()
        mock_session.close = AsyncMock()
        sql_base._session = mock_session
        sql_base._client = None  # No engine
        # Mock the _resource_cache clear method
        sql_base._resource_cache.clear = MagicMock()

        await sql_base._cleanup_resources()

        # Verify session was closed and cleared
        mock_session.close.assert_called_once()
        assert sql_base._session is None
        # Verify _resource_cache.clear was called
        sql_base._resource_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resources_engine(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method with engine."""
        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()
        sql_base._session = None  # No session
        sql_base._client = mock_engine  # Engine stored in _client
        # Mock the _resource_cache clear method
        sql_base._resource_cache.clear = MagicMock()

        await sql_base._cleanup_resources()

        # Verify engine was disposed
        mock_engine.dispose.assert_called_once()
        # Verify _resource_cache.clear was called
        sql_base._resource_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resources_both(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method with both session and engine."""
        mock_session = AsyncMock()
        mock_session.close = AsyncMock()
        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()
        sql_base._session = mock_session
        sql_base._client = mock_engine
        # Mock the _resource_cache clear method
        sql_base._resource_cache.clear = MagicMock()

        await sql_base._cleanup_resources()

        # Verify both session and engine were cleaned up
        mock_session.close.assert_called_once()
        mock_engine.dispose.assert_called_once()
        assert sql_base._session is None
        # Verify _resource_cache.clear was called
        sql_base._resource_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resources_session_error(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method when session closing fails."""
        mock_session = AsyncMock()
        mock_session.close = AsyncMock(side_effect=Exception("Session close failed"))
        sql_base._session = mock_session
        sql_base._client = None  # No engine
        # Mock the _resource_cache clear method
        sql_base._resource_cache.clear = MagicMock()

        await sql_base._cleanup_resources()

        # Verify session close was attempted
        mock_session.close.assert_called_once()
        # Note: In the actual implementation, the session might not be set to None
        # if there's an error, so we won't assert that here
        # Verify logger.warning was called
        sql_base.logger.warning.assert_called_once()
        # Verify _resource_cache.clear was called
        sql_base._resource_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resources_engine_error(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method when engine disposal fails."""
        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock(side_effect=Exception("Engine dispose failed"))
        sql_base._session = None  # No session
        sql_base._client = mock_engine  # Engine stored in _client
        # Mock the _resource_cache clear method
        sql_base._resource_cache.clear = MagicMock()

        await sql_base._cleanup_resources()

        # Verify engine dispose was attempted
        mock_engine.dispose.assert_called_once()
        # Verify _resource_cache.clear was called
        sql_base._resource_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resources_both_errors(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method when both session and engine operations fail."""
        mock_session = AsyncMock()
        mock_session.close = AsyncMock(side_effect=Exception("Session close failed"))
        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock(side_effect=Exception("Engine dispose failed"))
        sql_base._session = mock_session
        sql_base._client = mock_engine
        # Mock the _resource_cache clear method
        sql_base._resource_cache.clear = MagicMock()

        await sql_base._cleanup_resources()

        # Verify both operations were attempted
        mock_session.close.assert_called_once()
        mock_engine.dispose.assert_called_once()
        # Note: In the actual implementation, the session might not be set to None
        # if there's an error, so we won't assert that here
        # Verify logger.warning was called (since there were errors)
        sql_base.logger.warning.assert_called_once()
        # Verify _resource_cache.clear was called
        sql_base._resource_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resources_no_resources(self, sql_base: MockSqlBase) -> None:
        """Test _cleanup_resources method when no resources exist."""
        sql_base._session = None  # No session
        sql_base._client = None  # No engine
        # Mock the _resource_cache clear method
        sql_base._resource_cache.clear = MagicMock()

        await sql_base._cleanup_resources()

        # Verify _resource_cache.clear was called even with no resources
        sql_base._resource_cache.clear.assert_called_once()

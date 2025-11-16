"""Tests for the DuckDB SQL adapter."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typing as t

from acb.adapters.sql.duckdb import Sql, SqlSettings


class _AsyncContextManager:
    """Async context manager for engine.begin()."""

    def __init__(self, connection: AsyncMock) -> None:
        self._connection = connection

    async def __aenter__(self) -> AsyncMock:
        return self._connection

    async def __aexit__(
        self,
        exc_type: t.Any,
        exc: t.Any,
        tb: t.Any,
    ) -> None:
        return None


class _MockAsyncEngine:
    """Minimal async engine stub."""

    def __init__(self, connection: AsyncMock) -> None:
        self._connection = connection

    def begin(self) -> _AsyncContextManager:
        return _AsyncContextManager(self._connection)


@pytest.fixture
def duckdb_sql_config(tmp_path):
    """Create a minimal config namespace for the adapter."""
    db_path = tmp_path / "duckdb_test.duckdb"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    settings = SqlSettings(
        database_url=f"duckdb:///{db_path}",
        threads=4,
        pragmas={"memory_limit": "512MB"},
        extensions=["httpfs"],
        temp_directory=str(temp_dir),
    )
    return SimpleNamespace(sql=settings)


@pytest.fixture
def duckdb_sql_adapter(duckdb_sql_config):
    adapter = Sql()
    adapter.config = duckdb_sql_config
    adapter.logger = MagicMock()
    return adapter


def _collect_text(call: t.Any) -> str:
    stmt = call.args[0]
    if isinstance(stmt, str):
        return stmt
    if hasattr(stmt, "text"):
        return stmt.text
    return str(stmt)


class TestDuckDBSettings:
    def test_connect_args_configuration(self, duckdb_sql_config) -> None:
        settings = duckdb_sql_config.sql
        connect_args = settings.engine_kwargs["connect_args"]
        assert connect_args["threads"] == 4
        assert connect_args["temp_directory"] == duckdb_sql_config.sql.temp_directory
        assert settings.engine_kwargs["poolclass"].__name__ == "NullPool"

    def test_read_only_settings(self, tmp_path) -> None:
        settings = SqlSettings(
            database_url=f"duckdb:///{tmp_path / 'readonly.duckdb'}",
            read_only=True,
        )
        connect_args = settings.engine_kwargs["connect_args"]
        assert connect_args["read_only"] is True


@pytest.mark.asyncio
async def test_create_client_applies_configuration(duckdb_sql_adapter: Sql) -> None:
    connection = AsyncMock()
    connection.execute = AsyncMock(return_value=AsyncMock())

    mock_engine = _MockAsyncEngine(connection)

    with patch(
        "sqlalchemy.ext.asyncio.create_async_engine",
        return_value=mock_engine,
    ) as mock_create_engine:
        engine = await duckdb_sql_adapter._create_client()

    assert engine is mock_engine
    mock_create_engine.assert_called_once_with(
        duckdb_sql_adapter.config.sql._async_url,
        **duckdb_sql_adapter.config.sql.engine_kwargs,
    )

    executed = [_collect_text(call) for call in connection.execute.call_args_list]
    assert "PRAGMA threads=4" in executed
    assert "PRAGMA memory_limit='512MB'" in executed
    assert "INSTALL httpfs" in executed
    assert "LOAD httpfs" in executed
    assert "SET temp_directory=:temp_directory" in executed

    temp_call = next(
        call
        for call in connection.execute.call_args_list
        if "temp_directory" in _collect_text(call)
    )
    temp_stmt = temp_call.args[0]
    assert temp_stmt.text == "SET temp_directory=:temp_directory"
    assert (
        temp_stmt._bindparams["temp_directory"].value
        == duckdb_sql_adapter.config.sql.temp_directory
    )


@pytest.mark.asyncio
async def test_init_skips_schema_when_read_only(
    duckdb_sql_adapter: Sql,
) -> None:
    duckdb_sql_adapter.config.sql.read_only = True
    duckdb_sql_adapter.logger = MagicMock()

    await duckdb_sql_adapter.init()

    duckdb_sql_adapter.logger.info.assert_any_call(
        "DuckDB adapter running in read-only mode; skipping schema sync"
    )

"""Database Test Provider for ACB Testing.

Provides database testing utilities, fixtures, and helpers
for comprehensive database testing scenarios.

Features:
- In-memory database setup and teardown
- Database schema migration testing
- Transaction rollback testing
- Data seeding and fixtures
- Connection pooling testing
"""

from unittest.mock import AsyncMock, MagicMock

import typing as t
from contextlib import asynccontextmanager
from typing import Any

from acb.testing.discovery import (
    TestProviderCapability,
    create_test_provider_metadata_template,
)

# Provider metadata
PROVIDER_METADATA = create_test_provider_metadata_template(
    name="Database Test Provider",
    category="integration",
    provider_type="database_test",
    author="ACB Testing Team",
    description="Database testing utilities and fixtures for ACB applications",
    version="1.0.0",
    capabilities=[
        TestProviderCapability.DATABASE_FIXTURES,
        TestProviderCapability.TRANSACTION_ROLLBACK,
        TestProviderCapability.SCHEMA_MIGRATION,
        TestProviderCapability.DATA_SEEDING,
    ],
    settings_class="DatabaseTestProviderSettings",
)


class DatabaseTestProvider:
    """Provider for database testing utilities."""

    PROVIDER_METADATA = PROVIDER_METADATA

    def __init__(self) -> None:
        self._test_databases: dict[str, t.Any] = {}
        self._fixtures: dict[str, t.Any] = {}
        self._migrations: list[t.Any] = []

    async def create_test_database(
        self,
        db_type: str = "sqlite",
        config: dict[str, Any] | None = None,
    ) -> AsyncMock:
        """Create an in-memory test database."""
        db_mock = AsyncMock()
        db_mock._tables = {}
        db_mock._data = {}
        db_mock._next_id = 1
        db_mock._transactions = []

        # Default configuration
        default_config = {
            "url": ":memory:" if db_type == "sqlite" else f"test_{db_type}_db",
            "pool_size": 5,
            "echo": False,
            "isolation_level": "READ_COMMITTED",
        }

        if config:
            default_config.update(config)

        db_mock._config = default_config

        async def mock_execute(
            query: str,
            params: tuple[Any, ...] | None = None,
        ) -> MagicMock:
            # Simulate query execution
            result_mock = MagicMock()

            query_upper = query.strip().upper()

            if query_upper.startswith("CREATE TABLE"):
                # Extract table name (simplified)
                table_name = "test_table"
                db_mock._tables[table_name] = []
                result_mock.rowcount = 0

            elif query_upper.startswith("INSERT"):
                result_mock.rowcount = 1
                result_mock.lastrowid = db_mock._next_id
                db_mock._next_id += 1

            elif query_upper.startswith(("UPDATE", "DELETE")):
                result_mock.rowcount = 1

            else:
                result_mock.rowcount = 0

            return result_mock

        async def mock_fetch_one(
            query: str,
            params: tuple[Any, ...] | None = None,
        ) -> dict[str, Any]:
            return {
                "id": 1,
                "name": "test_record",
                "created_at": "2024-01-01T12:00:00Z",
            }

        async def mock_fetch_all(
            query: str,
            params: tuple[Any, ...] | None = None,
        ) -> list[dict[str, Any]]:
            return [
                {
                    "id": 1,
                    "name": "test_record_1",
                    "created_at": "2024-01-01T12:00:00Z",
                },
                {
                    "id": 2,
                    "name": "test_record_2",
                    "created_at": "2024-01-01T12:01:00Z",
                },
            ]

        async def mock_begin_transaction() -> AsyncMock:
            transaction_mock = AsyncMock()
            transaction_mock._id = len(db_mock._transactions)
            transaction_mock._committed = False
            transaction_mock._rolled_back = False

            async def commit() -> None:
                transaction_mock._committed = True

            async def rollback() -> None:
                transaction_mock._rolled_back = True

            transaction_mock.commit.side_effect = commit
            transaction_mock.rollback.side_effect = rollback

            db_mock._transactions.append(transaction_mock)
            return transaction_mock

        # Assign behaviors
        db_mock.execute.side_effect = mock_execute
        db_mock.fetch_one.side_effect = mock_fetch_one
        db_mock.fetch_all.side_effect = mock_fetch_all
        db_mock.begin_transaction.side_effect = mock_begin_transaction

        self._test_databases[db_type] = db_mock
        return db_mock

    def create_fixtures(
        self,
        table_name: str,
        data: list[dict[str, Any]],
    ) -> dict[str, t.Any]:
        """Create test data fixtures."""
        fixture = {
            "table": table_name,
            "data": data,
            "created_at": "2024-01-01T12:00:00Z",
        }

        self._fixtures[table_name] = fixture
        return fixture

    async def seed_data(self, db: AsyncMock, fixtures: dict[str, t.Any]) -> bool:
        """Seed database with test data."""
        try:
            for fixture in fixtures.values():
                table_name = fixture["table"]
                data = fixture["data"]

                # Validate table name (alphanumeric and underscore only for safety)
                if not table_name.replace("_", "").isalnum():
                    continue

                for record in data:
                    # Simulate insert with parameterized query
                    query = f"INSERT INTO {table_name} (name, value) VALUES (?, ?)"  # nosec B608
                    await db.execute(
                        query,
                        (record.get("name", "test"), record.get("value", "data")),
                    )

            return True
        except Exception:
            return False

    async def run_migration(self, db: AsyncMock, migration_sql: str) -> bool:
        """Run a database migration."""
        try:
            # Split migration into statements
            statements = [
                stmt.strip() for stmt in migration_sql.split(";") if stmt.strip()
            ]

            for statement in statements:
                await db.execute(statement)

            self._migrations.append(
                {
                    "sql": migration_sql,
                    "executed_at": "2024-01-01T12:00:00Z",
                    "success": True,
                },
            )

            return True
        except Exception as e:
            self._migrations.append(
                {
                    "sql": migration_sql,
                    "executed_at": "2024-01-01T12:00:00Z",
                    "success": False,
                    "error": str(e),
                },
            )
            return False

    def get_migration_history(self) -> list[dict[str, Any]]:
        """Get migration execution history."""
        return self._migrations.copy()

    async def cleanup_database(self, db: AsyncMock) -> None:
        """Clean up test database."""
        # Reset database state
        db._tables.clear()
        db._data.clear()
        db._next_id = 1
        db._transactions.clear()

    @asynccontextmanager
    async def database_transaction_test(
        self,
        db: AsyncMock,
    ) -> t.AsyncGenerator[AsyncMock]:
        """Context manager for testing database transactions."""
        transaction = await db.begin_transaction()

        try:
            yield transaction
        finally:
            # Always rollback in tests
            if not transaction._committed and not transaction._rolled_back:
                await transaction.rollback()

    def create_connection_pool_mock(self, pool_size: int = 5) -> AsyncMock:
        """Create a mock connection pool."""
        pool_mock = AsyncMock()
        pool_mock._size = pool_size
        pool_mock._active_connections = 0
        pool_mock._connections = []

        async def acquire_connection() -> AsyncMock:
            if pool_mock._active_connections < pool_mock._size:
                conn_mock = AsyncMock()
                conn_mock._pool = pool_mock
                pool_mock._active_connections += 1
                pool_mock._connections.append(conn_mock)
                return conn_mock
            msg = "Connection pool exhausted"
            raise RuntimeError(msg)

        async def release_connection(conn: AsyncMock) -> None:
            if conn in pool_mock._connections:
                pool_mock._active_connections -= 1
                pool_mock._connections.remove(conn)

        pool_mock.acquire.side_effect = acquire_connection
        pool_mock.release.side_effect = release_connection

        return pool_mock

    def assert_transaction_rolled_back(self, transaction: AsyncMock) -> None:
        """Assert that a transaction was rolled back."""
        assert transaction._rolled_back, "Transaction was not rolled back"
        assert not transaction._committed, (
            "Transaction was committed when it should have been rolled back"
        )

    def assert_transaction_committed(self, transaction: AsyncMock) -> None:
        """Assert that a transaction was committed."""
        assert transaction._committed, "Transaction was not committed"
        assert not transaction._rolled_back, (
            "Transaction was rolled back when it should have been committed"
        )

    def get_test_database(self, db_type: str) -> AsyncMock | None:
        """Get a previously created test database."""
        return self._test_databases.get(db_type)

    def get_fixtures(self, table_name: str) -> dict[str, t.Any] | None:
        """Get fixtures for a specific table."""
        return self._fixtures.get(table_name)

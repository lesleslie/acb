"""Tests for SQL Query Adapter."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acb.adapters.models._query import (
    QueryOperator,
    QuerySpec,
)
from acb.adapters.sql._query import SqlDatabaseAdapter


class TestSqlDatabaseAdapter:
    """Test suite for SqlDatabaseAdapter."""

    @pytest.fixture
    def mock_sql_adapter(self) -> MagicMock:
        """Create a mock SQL adapter."""
        adapter = MagicMock()

        # Mock session context manager
        @asynccontextmanager
        async def mock_session():
            session = AsyncMock()
            yield session

        adapter.get_session = mock_session
        return adapter

    @pytest.fixture
    def sql_db_adapter(self, mock_sql_adapter: MagicMock) -> SqlDatabaseAdapter:
        """Create SqlDatabaseAdapter instance."""
        return SqlDatabaseAdapter(mock_sql_adapter)

    @pytest.mark.asyncio
    async def test_execute_query_simple(
        self, sql_db_adapter: SqlDatabaseAdapter
    ) -> None:
        """Test simple query execution."""
        # Create query spec
        query_spec = QuerySpec()

        # Mock session and results
        mock_result = MagicMock()
        mock_rows = [
            MagicMock(_mapping={"id": 1, "name": "John"}),
            MagicMock(_mapping={"id": 2, "name": "Jane"}),
        ]
        mock_result.fetchall.return_value = mock_rows

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Execute query
            result = await sql_db_adapter.execute_query("users", query_spec)

        # Verify results
        assert len(result) == 2
        assert result[0] == {"id": 1, "name": "John"}
        assert result[1] == {"id": 2, "name": "Jane"}

    @pytest.mark.asyncio
    async def test_execute_query_with_filter(
        self, sql_db_adapter: SqlDatabaseAdapter
    ) -> None:
        """Test query execution with WHERE clause."""
        # Create query spec with filter
        query_spec = QuerySpec()
        query_spec.filter.where("active", True)
        query_spec.filter.where_gt("age", 18)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Execute query
            await sql_db_adapter.execute_query("users", query_spec)

            # Verify SQL was called with WHERE clause
            call_args = mock_session.execute.call_args
            sql_text = call_args[0][0]
            params = call_args[0][1]

            assert "WHERE" in str(sql_text)
            assert params == {"active": True, "age": 18}

    @pytest.mark.asyncio
    async def test_execute_query_with_sorting(
        self, sql_db_adapter: SqlDatabaseAdapter
    ) -> None:
        """Test query execution with ORDER BY clause."""
        # Create query spec with sorting
        query_spec = QuerySpec()
        query_spec.order_by("name")
        query_spec.order_by_desc("created_at")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Execute query
            await sql_db_adapter.execute_query("users", query_spec)

            # Verify ORDER BY was included
            call_args = mock_session.execute.call_args
            sql_text = str(call_args[0][0])

            assert "ORDER BY" in sql_text
            assert "name ASC" in sql_text
            assert "created_at DESC" in sql_text

    @pytest.mark.asyncio
    async def test_execute_query_with_limit_offset(
        self, sql_db_adapter: SqlDatabaseAdapter
    ) -> None:
        """Test query execution with LIMIT and OFFSET."""
        # Create query spec with pagination
        query_spec = QuerySpec()
        query_spec.take(10)
        query_spec.skip(20)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Execute query
            await sql_db_adapter.execute_query("users", query_spec)

            # Verify LIMIT and OFFSET
            call_args = mock_session.execute.call_args
            sql_text = str(call_args[0][0])

            assert "LIMIT 10" in sql_text
            assert "OFFSET 20" in sql_text

    @pytest.mark.asyncio
    async def test_execute_count(self, sql_db_adapter: SqlDatabaseAdapter) -> None:
        """Test count query execution."""
        # Create query spec
        query_spec = QuerySpec()
        query_spec.filter.where("active", True)

        mock_result = MagicMock()
        mock_result.scalar.return_value = 42

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Execute count
            result = await sql_db_adapter.execute_count("users", query_spec)

            # Verify
            assert result == 42
            call_args = mock_session.execute.call_args
            sql_text = str(call_args[0][0])

            assert "SELECT COUNT(*)" in sql_text
            assert "FROM users" in sql_text

    @pytest.mark.asyncio
    async def test_execute_create_single(
        self, sql_db_adapter: SqlDatabaseAdapter
    ) -> None:
        """Test single record creation."""
        data = {"name": "John Doe", "email": "john@example.com"}

        mock_result = MagicMock()
        mock_row = MagicMock(_mapping={"id": 1} | data)
        mock_result.fetchone.return_value = mock_row

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Execute create
            result = await sql_db_adapter.execute_create("users", data)

            # Verify
            assert result == {"id": 1, "name": "John Doe", "email": "john@example.com"}
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_create_many(
        self, sql_db_adapter: SqlDatabaseAdapter
    ) -> None:
        """Test multiple record creation."""
        data = [
            {"name": "John", "email": "john@example.com"},
            {"name": "Jane", "email": "jane@example.com"},
        ]

        mock_results = [
            MagicMock(_mapping={"id": 1} | data[0]),
            MagicMock(_mapping={"id": 2} | data[1]),
        ]

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchone.side_effect = mock_results
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Execute create
            result = await sql_db_adapter.execute_create("users", data)

            # Verify
            assert len(result) == 2
            assert result[0]["id"] == 1
            assert result[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_execute_update(self, sql_db_adapter: SqlDatabaseAdapter) -> None:
        """Test update operation."""
        query_spec = QuerySpec()
        query_spec.filter.where("id", 1)
        data = {"name": "Updated Name"}

        mock_result = MagicMock()
        mock_result.rowcount = 1

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Execute update
            result = await sql_db_adapter.execute_update("users", query_spec, data)

            # Verify
            assert result == 1
            call_args = mock_session.execute.call_args
            sql_text = str(call_args[0][0])
            params = call_args[0][1]

            assert "UPDATE users" in sql_text
            assert "SET" in sql_text
            assert params["set_name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_execute_delete(self, sql_db_adapter: SqlDatabaseAdapter) -> None:
        """Test delete operation."""
        query_spec = QuerySpec()
        query_spec.filter.where("id", 1)

        mock_result = MagicMock()
        mock_result.rowcount = 1

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Execute delete
            result = await sql_db_adapter.execute_delete("users", query_spec)

            # Verify
            assert result == 1
            call_args = mock_session.execute.call_args
            sql_text = str(call_args[0][0])

            assert "DELETE FROM users" in sql_text

    @pytest.mark.asyncio
    async def test_transaction(self, sql_db_adapter: SqlDatabaseAdapter) -> None:
        """Test transaction context manager."""
        mock_session = MagicMock()
        mock_transaction = AsyncMock()

        # Make begin() return an async context manager (not a coroutine)
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_transaction
        async_cm.__aexit__.return_value = None
        mock_session.begin.return_value = async_cm

        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            async with sql_db_adapter.transaction() as txn:
                assert txn is not None

    def test_build_where_clause_with_operators(
        self, sql_db_adapter: SqlDatabaseAdapter
    ) -> None:
        """Test WHERE clause building with various operators."""
        # Test different operators
        test_cases = [
            (QueryOperator.EQ, "field = :field"),
            (QueryOperator.NE, "field != :field"),
            (QueryOperator.GT, "field > :field"),
            (QueryOperator.GTE, "field >= :field"),
            (QueryOperator.LT, "field < :field"),
            (QueryOperator.LTE, "field <= :field"),
            (QueryOperator.IN, "field = ANY(:field)"),
            (QueryOperator.NOT_IN, "field != ALL(:field)"),
            (QueryOperator.LIKE, "field LIKE :field"),
            (QueryOperator.ILIKE, "field ILIKE :field"),
            (QueryOperator.IS_NULL, "field IS NULL"),
            (QueryOperator.IS_NOT_NULL, "field IS NOT NULL"),
            (QueryOperator.BETWEEN, "field BETWEEN :field_start AND :field_end"),
            (QueryOperator.REGEX, "field ~ :field"),
        ]

        for operator, expected in test_cases:
            query_spec = QuerySpec()
            query_spec.filter.add_condition("field", operator, "value")

            where_clause = sql_db_adapter._build_where_clause(query_spec)
            assert expected in where_clause

    def test_build_params(self, sql_db_adapter: SqlDatabaseAdapter) -> None:
        """Test parameter building for queries."""
        query_spec = QuerySpec()
        query_spec.filter.where("name", "John")
        query_spec.filter.where_in("status", ["active", "pending"])
        query_spec.filter.add_condition("age", QueryOperator.BETWEEN, [18, 65])

        params = sql_db_adapter._build_params(query_spec)

        assert params["name"] == "John"
        assert params["status"] == ["active", "pending"]
        assert params["age_start"] == 18
        assert params["age_end"] == 65

    @pytest.mark.asyncio
    async def test_execute_aggregate(self, sql_db_adapter: SqlDatabaseAdapter) -> None:
        """Test aggregation pipeline execution."""
        pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {"_id": "department", "total": {"$sum": "salary"}}},
            {"$sort": {"total": -1}},
            {"$limit": 10},
        ]

        mock_result = MagicMock()
        mock_rows = [
            MagicMock(_mapping={"department": "Sales", "total": 500000}),
            MagicMock(_mapping={"department": "Engineering", "total": 750000}),
        ]
        mock_result.fetchall.return_value = mock_rows

        # Mock the sql adapter to return our mock result
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Execute aggregate
            result = await sql_db_adapter.execute_aggregate("employees", pipeline)

            # Verify
            assert len(result) == 2
            assert result[0]["department"] == "Sales"
            assert result[1]["department"] == "Engineering"

    @pytest.mark.asyncio
    async def test_error_handling_in_create(
        self, sql_db_adapter: SqlDatabaseAdapter
    ) -> None:
        """Test error handling during create operation."""
        data = {"name": "Test"}

        # Mock the sql adapter to simulate an error
        with patch.object(
            sql_db_adapter.sql_adapter, "get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("Database error")
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Should raise and rollback
            with pytest.raises(Exception, match="Database error"):
                await sql_db_adapter.execute_create("users", data)

            mock_session.rollback.assert_called_once()

    def test_build_select_query_with_fields(
        self, sql_db_adapter: SqlDatabaseAdapter
    ) -> None:
        """Test SELECT query building with specific fields."""
        query_spec = QuerySpec()
        query_spec.select("id", "name", "email")

        query = sql_db_adapter._build_select_query("users", query_spec)

        assert query.startswith("SELECT id, name, email")
        assert "FROM users" in query

"""Tests for NoSQL Query Adapter."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.models._query import (
    QueryOperator,
    QuerySpec,
)
from acb.adapters.nosql._query import NoSqlDatabaseAdapter


class TestNoSqlDatabaseAdapter:
    """Test suite for NoSqlDatabaseAdapter."""

    @pytest.fixture
    def mock_nosql_adapter(self) -> MagicMock:
        """Create a mock NoSQL adapter."""
        adapter = MagicMock()

        # Mock async methods
        adapter.find = AsyncMock()
        adapter.count = AsyncMock()
        adapter.insert_one = AsyncMock()
        adapter.insert_many = AsyncMock()
        adapter.update_many = AsyncMock()
        adapter.delete_many = AsyncMock()
        adapter.aggregate = AsyncMock()

        # Mock transaction if available
        @asynccontextmanager
        async def mock_transaction():
            yield MagicMock()

        adapter.transaction = mock_transaction

        return adapter

    @pytest.fixture
    def nosql_db_adapter(self, mock_nosql_adapter: MagicMock) -> NoSqlDatabaseAdapter:
        """Create NoSqlDatabaseAdapter instance."""
        return NoSqlDatabaseAdapter(mock_nosql_adapter)

    @pytest.mark.asyncio
    async def test_execute_query_simple(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test simple query execution."""
        # Create query spec
        query_spec = QuerySpec()

        # Mock results
        mock_results = [
            {"_id": "1", "name": "John", "age": 30},
            {"_id": "2", "name": "Jane", "age": 25},
        ]
        nosql_db_adapter.nosql_adapter.find.return_value = mock_results

        # Execute query
        result = await nosql_db_adapter.execute_query("users", query_spec)

        # Verify
        assert len(result) == 2
        assert result[0]["_id"] == "1"
        assert result[1]["name"] == "Jane"

        # Check find was called correctly
        nosql_db_adapter.nosql_adapter.find.assert_called_once_with("users", {})

    @pytest.mark.asyncio
    async def test_execute_query_with_filter(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test query with filter conditions."""
        # Create query spec with filters
        query_spec = QuerySpec()
        query_spec.filter.where("active", True)
        query_spec.filter.where_gt("age", 18)
        query_spec.filter.where_in("status", ["active", "pending"])

        nosql_db_adapter.nosql_adapter.find.return_value = []

        # Execute query
        await nosql_db_adapter.execute_query("users", query_spec)

        # Verify filter was built correctly
        expected_filter = {
            "active": True,
            "age": {"$gt": 18},
            "status": {"$in": ["active", "pending"]},
        }
        nosql_db_adapter.nosql_adapter.find.assert_called_once_with(
            "users", expected_filter
        )

    @pytest.mark.asyncio
    async def test_execute_query_with_or_filter(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test query with OR logical operator."""
        # Create query spec with OR filter
        query_spec = QuerySpec()
        query_spec.filter.logical_operator = "OR"
        query_spec.filter.where("status", "active")
        query_spec.filter.where("priority", "high")

        nosql_db_adapter.nosql_adapter.find.return_value = []

        # Execute query
        await nosql_db_adapter.execute_query("users", query_spec)

        # Verify OR filter
        expected_filter = {"$or": [{"status": "active"}, {"priority": "high"}]}
        nosql_db_adapter.nosql_adapter.find.assert_called_once_with(
            "users", expected_filter
        )

    @pytest.mark.asyncio
    async def test_execute_query_with_sorting(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test query with sorting options."""
        # Create query spec with sorting
        query_spec = QuerySpec()
        query_spec.order_by("name")
        query_spec.order_by_desc("created_at")

        nosql_db_adapter.nosql_adapter.find.return_value = []

        # Execute query
        await nosql_db_adapter.execute_query("users", query_spec)

        # Verify sort option
        call_args = nosql_db_adapter.nosql_adapter.find.call_args
        assert call_args[1]["sort"] == [("name", 1), ("created_at", -1)]

    @pytest.mark.asyncio
    async def test_execute_query_with_pagination(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test query with limit and offset."""
        # Create query spec with pagination
        query_spec = QuerySpec()
        query_spec.take(10)
        query_spec.skip(20)

        nosql_db_adapter.nosql_adapter.find.return_value = []

        # Execute query
        await nosql_db_adapter.execute_query("users", query_spec)

        # Verify pagination options
        call_args = nosql_db_adapter.nosql_adapter.find.call_args
        assert call_args[1]["limit"] == 10
        assert call_args[1]["skip"] == 20

    @pytest.mark.asyncio
    async def test_execute_query_with_projection(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test query with field selection."""
        # Create query spec with field selection
        query_spec = QuerySpec()
        query_spec.select("name", "email", "active")

        nosql_db_adapter.nosql_adapter.find.return_value = []

        # Execute query
        await nosql_db_adapter.execute_query("users", query_spec)

        # Verify projection
        call_args = nosql_db_adapter.nosql_adapter.find.call_args
        assert call_args[1]["projection"] == {"name": 1, "email": 1, "active": 1}

    @pytest.mark.asyncio
    async def test_execute_count(self, nosql_db_adapter: NoSqlDatabaseAdapter) -> None:
        """Test count operation."""
        # Create query spec
        query_spec = QuerySpec()
        query_spec.filter.where("active", True)

        nosql_db_adapter.nosql_adapter.count.return_value = 42

        # Execute count
        result = await nosql_db_adapter.execute_count("users", query_spec)

        # Verify
        assert result == 42
        nosql_db_adapter.nosql_adapter.count.assert_called_once_with(
            "users", {"active": True}
        )

    @pytest.mark.asyncio
    async def test_execute_create_single(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test single document creation."""
        data = {"name": "John Doe", "email": "john@example.com"}

        nosql_db_adapter.nosql_adapter.insert_one.return_value = (
            "507f1f77bcf86cd799439011"
        )

        # Execute create
        result = await nosql_db_adapter.execute_create("users", data)

        # Verify
        assert result == "507f1f77bcf86cd799439011"
        nosql_db_adapter.nosql_adapter.insert_one.assert_called_once_with("users", data)

    @pytest.mark.asyncio
    async def test_execute_create_many(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test multiple document creation."""
        data = [
            {"name": "John", "email": "john@example.com"},
            {"name": "Jane", "email": "jane@example.com"},
        ]

        nosql_db_adapter.nosql_adapter.insert_many.return_value = [
            "507f1f77bcf86cd799439011",
            "507f1f77bcf86cd799439012",
        ]

        # Execute create
        result = await nosql_db_adapter.execute_create("users", data)

        # Verify
        assert len(result) == 2
        nosql_db_adapter.nosql_adapter.insert_many.assert_called_once_with(
            "users", data
        )

    @pytest.mark.asyncio
    async def test_execute_update(self, nosql_db_adapter: NoSqlDatabaseAdapter) -> None:
        """Test update operation."""
        query_spec = QuerySpec()
        query_spec.filter.where("status", "pending")
        data = {"status": "approved", "updated_at": "2024-01-01"}

        nosql_db_adapter.nosql_adapter.update_many.return_value = 5

        # Execute update
        result = await nosql_db_adapter.execute_update("users", query_spec, data)

        # Verify
        assert result == 5
        nosql_db_adapter.nosql_adapter.update_many.assert_called_once_with(
            "users", {"status": "pending"}, {"$set": data}
        )

    @pytest.mark.asyncio
    async def test_execute_delete(self, nosql_db_adapter: NoSqlDatabaseAdapter) -> None:
        """Test delete operation."""
        query_spec = QuerySpec()
        query_spec.filter.where("active", False)

        nosql_db_adapter.nosql_adapter.delete_many.return_value = 3

        # Execute delete
        result = await nosql_db_adapter.execute_delete("users", query_spec)

        # Verify
        assert result == 3
        nosql_db_adapter.nosql_adapter.delete_many.assert_called_once_with(
            "users", {"active": False}
        )

    @pytest.mark.asyncio
    async def test_execute_aggregate(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test aggregation pipeline."""
        pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {"_id": "$department", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

        mock_results = [
            {"_id": "sales", "count": 25},
            {"_id": "engineering", "count": 40},
        ]
        nosql_db_adapter.nosql_adapter.aggregate.return_value = mock_results

        # Execute aggregate
        result = await nosql_db_adapter.execute_aggregate("users", pipeline)

        # Verify
        assert len(result) == 2
        assert result[0]["_id"] == "sales"
        nosql_db_adapter.nosql_adapter.aggregate.assert_called_once_with(
            "users", pipeline
        )

    @pytest.mark.asyncio
    async def test_transaction_with_support(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test transaction when adapter supports it."""
        async with nosql_db_adapter.transaction() as txn:
            assert txn is not None

    @pytest.mark.asyncio
    async def test_transaction_without_support(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test transaction when adapter doesn't support it."""
        # Remove transaction support
        delattr(nosql_db_adapter.nosql_adapter, "transaction")

        async with nosql_db_adapter.transaction() as txn:
            assert txn is None

    def test_build_filter_with_operators(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test filter building with various operators."""
        test_cases = [
            (QueryOperator.EQ, "value", {"field": "value"}),
            (QueryOperator.NE, "value", {"field": {"$ne": "value"}}),
            (QueryOperator.GT, 10, {"field": {"$gt": 10}}),
            (QueryOperator.GTE, 10, {"field": {"$gte": 10}}),
            (QueryOperator.LT, 10, {"field": {"$lt": 10}}),
            (QueryOperator.LTE, 10, {"field": {"$lte": 10}}),
            (QueryOperator.IN, [1, 2, 3], {"field": {"$in": [1, 2, 3]}}),
            (QueryOperator.NOT_IN, [1, 2, 3], {"field": {"$nin": [1, 2, 3]}}),
            (
                QueryOperator.LIKE,
                "test%",
                {"field": {"$regex": "test.*", "$options": "i"}},
            ),
            (QueryOperator.IS_NULL, None, {"field": {"$exists": False}}),
            (QueryOperator.IS_NOT_NULL, None, {"field": {"$exists": True}}),
            (QueryOperator.BETWEEN, [10, 20], {"field": {"$gte": 10, "$lte": 20}}),
            (QueryOperator.REGEX, "^test", {"field": {"$regex": "^test"}}),
        ]

        for operator, value, expected in test_cases:
            query_spec = QuerySpec()
            query_spec.filter.add_condition("field", operator, value)

            filter_dict = nosql_db_adapter._build_filter(query_spec)
            assert filter_dict == expected

    @pytest.mark.asyncio
    async def test_normalize_document(
        self, nosql_db_adapter: NoSqlDatabaseAdapter
    ) -> None:
        """Test document normalization."""

        # Document with ObjectId-like object
        class ObjectId:
            def __init__(self, value: str) -> None:
                self.value = value

            def __str__(self) -> str:
                return self.value

        doc = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "John",
            "created_at": ObjectId("timestamp"),
            "tags": ["python", "async"],
        }

        normalized = nosql_db_adapter._normalize_document(doc)

        assert normalized["_id"] == "507f1f77bcf86cd799439011"
        assert normalized["created_at"] == "timestamp"
        assert normalized["tags"] == ["python", "async"]

    def test_build_options(self, nosql_db_adapter: NoSqlDatabaseAdapter) -> None:
        """Test options building for queries."""
        query_spec = QuerySpec()
        query_spec.select("name", "email")
        query_spec.order_by("name")
        query_spec.order_by_desc("created_at")
        query_spec.take(10)
        query_spec.skip(5)

        options = nosql_db_adapter._build_options(query_spec)

        assert options["projection"] == {"name": 1, "email": 1}
        assert options["sort"] == [("name", 1), ("created_at", -1)]
        assert options["limit"] == 10
        assert options["skip"] == 5

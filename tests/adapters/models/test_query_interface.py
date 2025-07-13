"""Tests for the Universal Query Interface."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.models._query import (
    DatabaseAdapter,
    ModelAdapter,
    Query,
    QueryBuilder,
    QueryCondition,
    QueryFilter,
    QueryOperator,
    QuerySpec,
    Registry,
    SortDirection,
    registry,
)


class TestQueryCondition:
    """Test QueryCondition dataclass."""

    def test_query_condition_creation(self) -> None:
        """Test creating a QueryCondition."""
        condition = QueryCondition(
            field="name", operator=QueryOperator.EQ, value="John"
        )

        assert condition.field == "name"
        assert condition.operator == QueryOperator.EQ
        assert condition.value == "John"

    def test_query_condition_null_operators(self) -> None:
        """Test conditions with null operators have value set to None."""
        # These operators should have value forced to None
        null_operators = [
            QueryOperator.IS_NULL,
            QueryOperator.IS_NOT_NULL,
            QueryOperator.EXISTS,
        ]

        for op in null_operators:
            condition = QueryCondition(
                field="field", operator=op, value="should be None"
            )
            assert condition.value is None


class TestQueryFilter:
    """Test QueryFilter functionality."""

    def test_query_filter_initialization(self) -> None:
        """Test QueryFilter initialization."""
        filter_obj = QueryFilter()

        assert not filter_obj.conditions
        assert filter_obj.logical_operator == "AND"

    def test_add_condition(self) -> None:
        """Test adding conditions to filter."""
        filter_obj = QueryFilter()

        filter_obj.add_condition("name", QueryOperator.EQ, "John")
        filter_obj.add_condition("age", QueryOperator.GT, 18)

        assert len(filter_obj.conditions) == 2
        assert filter_obj.conditions[0].field == "name"
        assert filter_obj.conditions[1].operator == QueryOperator.GT

    def test_where_methods(self) -> None:
        """Test convenience where methods."""
        filter_obj = QueryFilter()

        # Test various where methods
        filter_obj.where("name", "John")
        filter_obj.where_not("status", "inactive")
        filter_obj.where_gt("age", 18)
        filter_obj.where_gte("score", 90)
        filter_obj.where_lt("price", 100)
        filter_obj.where_lte("quantity", 50)
        filter_obj.where_in("category", ["A", "B", "C"])
        filter_obj.where_not_in("type", ["X", "Y"])
        filter_obj.where_like("email", "%@example.com")
        filter_obj.where_null("deleted_at")
        filter_obj.where_not_null("created_at")

        assert len(filter_obj.conditions) == 11

        # Verify operators
        assert filter_obj.conditions[0].operator == QueryOperator.EQ
        assert filter_obj.conditions[1].operator == QueryOperator.NE
        assert filter_obj.conditions[2].operator == QueryOperator.GT
        assert filter_obj.conditions[3].operator == QueryOperator.GTE
        assert filter_obj.conditions[4].operator == QueryOperator.LT
        assert filter_obj.conditions[5].operator == QueryOperator.LTE
        assert filter_obj.conditions[6].operator == QueryOperator.IN
        assert filter_obj.conditions[7].operator == QueryOperator.NOT_IN
        assert filter_obj.conditions[8].operator == QueryOperator.LIKE
        assert filter_obj.conditions[9].operator == QueryOperator.IS_NULL
        assert filter_obj.conditions[10].operator == QueryOperator.IS_NOT_NULL

    def test_method_chaining(self) -> None:
        """Test that filter methods return self for chaining."""
        filter_obj = QueryFilter()

        result = filter_obj.where("a", 1).where_gt("b", 2).where_in("c", [3, 4])

        assert result is filter_obj
        assert len(filter_obj.conditions) == 3


class TestQuerySpec:
    """Test QuerySpec functionality."""

    def test_query_spec_initialization(self) -> None:
        """Test QuerySpec initialization."""
        spec = QuerySpec()

        assert isinstance(spec.filter, QueryFilter)
        assert not spec.sorts
        assert spec.limit is None
        assert spec.offset is None
        assert spec.fields is None

    def test_add_sort(self) -> None:
        """Test adding sort specifications."""
        spec = QuerySpec()

        spec.add_sort("name")
        spec.add_sort("created_at", SortDirection.DESC)

        assert len(spec.sorts) == 2
        assert spec.sorts[0].field == "name"
        assert spec.sorts[0].direction == SortDirection.ASC
        assert spec.sorts[1].field == "created_at"
        assert spec.sorts[1].direction == SortDirection.DESC

    def test_order_by_methods(self) -> None:
        """Test order by convenience methods."""
        spec = QuerySpec()

        spec.order_by("name")
        spec.order_by_desc("created_at")

        assert spec.sorts[0].direction == SortDirection.ASC
        assert spec.sorts[1].direction == SortDirection.DESC

    def test_pagination_methods(self) -> None:
        """Test pagination methods."""
        spec = QuerySpec()

        spec.take(10)
        spec.skip(20)

        assert spec.limit == 10
        assert spec.offset == 20

    def test_select_fields(self) -> None:
        """Test field selection."""
        spec = QuerySpec()

        spec.select("id", "name", "email")

        assert spec.fields == ["id", "name", "email"]

    def test_method_chaining(self) -> None:
        """Test that spec methods return self for chaining."""
        spec = QuerySpec()

        result = spec.order_by("name").take(10).skip(5).select("id", "name")

        assert result is spec
        assert spec.limit == 10
        assert spec.offset == 5


class TestQuery:
    """Test Query class functionality."""

    @pytest.fixture
    def mock_database_adapter(self) -> MagicMock:
        """Create mock database adapter."""
        adapter = MagicMock(spec=DatabaseAdapter)
        adapter.execute_query = AsyncMock(return_value=[])
        adapter.execute_count = AsyncMock(return_value=0)
        adapter.execute_create = AsyncMock(return_value=1)
        adapter.execute_update = AsyncMock(return_value=1)
        adapter.execute_delete = AsyncMock(return_value=1)
        adapter.execute_aggregate = AsyncMock(return_value=[])
        return adapter

    @pytest.fixture
    def mock_model_adapter(self) -> MagicMock:
        """Create mock model adapter."""
        adapter = MagicMock(spec=ModelAdapter)
        adapter.serialize = MagicMock(return_value={})
        adapter.deserialize = MagicMock(return_value=MagicMock())
        adapter.get_entity_name = MagicMock(return_value="test_entity")
        adapter.get_field_mapping = MagicMock(return_value={})
        adapter.validate_data = MagicMock(return_value={})
        return adapter

    @pytest.fixture
    def query_instance(
        self, mock_database_adapter: MagicMock, mock_model_adapter: MagicMock
    ) -> Query:
        """Create Query instance."""

        class TestModel:
            pass

        return Query(TestModel, mock_database_adapter, mock_model_adapter)

    def test_query_initialization(
        self, mock_database_adapter: MagicMock, mock_model_adapter: MagicMock
    ) -> None:
        """Test Query initialization."""

        class TestModel:
            pass

        query = Query(TestModel, mock_database_adapter, mock_model_adapter)

        assert query.model_class == TestModel
        assert query.database_adapter == mock_database_adapter
        assert query.model_adapter == mock_model_adapter
        assert isinstance(query.query_spec, QuerySpec)

    def test_where_methods_chaining(self, query_instance: Query) -> None:
        """Test where method chaining."""
        result = (
            query_instance.where("name", "John")
            .where_gt("age", 18)
            .where_in("status", ["active", "pending"])
            .order_by("created_at")
            .limit(10)
        )

        assert result is query_instance
        assert len(query_instance.query_spec.filter.conditions) == 3
        assert query_instance.query_spec.limit == 10

    @pytest.mark.asyncio
    async def test_all_method(self, query_instance: Query) -> None:
        """Test all() method execution."""
        # Setup mock return values
        raw_results = [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]
        query_instance.database_adapter.execute_query.return_value = raw_results
        query_instance.model_adapter.deserialize.side_effect = lambda x: x

        # Add some query conditions
        query_instance.where("active", True)

        # Execute query
        results = await query_instance.all()

        # Verify
        assert len(results) == 2
        assert results[0]["name"] == "John"
        query_instance.database_adapter.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_first_method(self, query_instance: Query) -> None:
        """Test first() method execution."""
        # Setup mock return
        query_instance.database_adapter.execute_query.return_value = [
            {"id": 1, "name": "John"}
        ]
        query_instance.model_adapter.deserialize.side_effect = lambda x: x

        # Execute query
        result = await query_instance.first()

        # Verify
        assert result is not None
        assert result["name"] == "John"
        # Verify limit was temporarily set to 1
        call_args = query_instance.database_adapter.execute_query.call_args
        assert call_args[0][1].limit == 1

    @pytest.mark.asyncio
    async def test_first_method_no_results(self, query_instance: Query) -> None:
        """Test first() when no results found."""
        query_instance.database_adapter.execute_query.return_value = []

        result = await query_instance.first()

        assert result is None

    @pytest.mark.asyncio
    async def test_count_method(self, query_instance: Query) -> None:
        """Test count() method."""
        query_instance.database_adapter.execute_count.return_value = 42

        query_instance.where("active", True)
        result = await query_instance.count()

        assert result == 42
        query_instance.database_adapter.execute_count.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists_method(self, query_instance: Query) -> None:
        """Test exists() method."""
        # Test when records exist
        query_instance.database_adapter.execute_count.return_value = 5
        assert await query_instance.exists()

        # Test when no records exist
        query_instance.database_adapter.execute_count.return_value = 0
        assert not await query_instance.exists()

    @pytest.mark.asyncio
    async def test_create_method(self, query_instance: Query) -> None:
        """Test create() method."""
        data = {"name": "John", "email": "john@example.com"}
        query_instance.model_adapter.validate_data.return_value = data
        query_instance.database_adapter.execute_create.return_value = 1

        result = await query_instance.create(data)

        assert result == 1
        query_instance.model_adapter.validate_data.assert_called_once_with(
            query_instance.model_class, data
        )

    @pytest.mark.asyncio
    async def test_update_method(self, query_instance: Query) -> None:
        """Test update() method."""
        data = {"name": "Updated Name"}
        query_instance.model_adapter.validate_data.return_value = data
        query_instance.database_adapter.execute_update.return_value = 3

        query_instance.where("status", "pending")
        result = await query_instance.update(data)

        assert result == 3

    @pytest.mark.asyncio
    async def test_delete_method(self, query_instance: Query) -> None:
        """Test delete() method."""
        query_instance.database_adapter.execute_delete.return_value = 2

        query_instance.where("active", False)
        result = await query_instance.delete()

        assert result == 2

    def test_field_mapping(self, query_instance: Query) -> None:
        """Test field mapping functionality."""
        # Setup field mapping
        query_instance.model_adapter.get_field_mapping.return_value = {
            "userId": "user_id",
            "fullName": "full_name",
        }
        query_instance._field_mapping = query_instance.model_adapter.get_field_mapping(
            query_instance.model_class
        )

        # Test field mapping
        assert query_instance._map_field("userId") == "user_id"
        assert query_instance._map_field("fullName") == "full_name"
        assert query_instance._map_field("unmapped") == "unmapped"


class TestQueryBuilder:
    """Test QueryBuilder functionality."""

    @pytest.fixture
    def query_builder(self) -> QueryBuilder:
        """Create QueryBuilder instance."""
        db_adapter = MagicMock(spec=DatabaseAdapter)
        model_adapter = MagicMock(spec=ModelAdapter)
        return QueryBuilder(db_adapter, model_adapter)

    def test_query_builder_initialization(self) -> None:
        """Test QueryBuilder initialization."""
        db_adapter = MagicMock()
        model_adapter = MagicMock()

        builder = QueryBuilder(db_adapter, model_adapter)

        assert builder.database_adapter == db_adapter
        assert builder.model_adapter == model_adapter

    def test_query_method(self, query_builder: QueryBuilder) -> None:
        """Test query() method creates Query instance."""

        class TestModel:
            pass

        query = query_builder.query(TestModel)

        assert isinstance(query, Query)
        assert query.model_class == TestModel
        assert query.database_adapter == query_builder.database_adapter

    @pytest.mark.asyncio
    async def test_create_method(self, query_builder: QueryBuilder) -> None:
        """Test create() convenience method."""

        class TestModel:
            pass

        data = {"name": "Test"}
        query_builder.model_adapter.validate_data.return_value = data
        query_builder.database_adapter.execute_create = AsyncMock(return_value=1)

        result = await query_builder.create(TestModel, data)

        assert result == 1

    @pytest.mark.asyncio
    async def test_find_by_id(self, query_builder: QueryBuilder) -> None:
        """Test find_by_id() convenience method."""

        class TestModel:
            def __getitem__(self, key: str) -> Any:
                # For testing: allow dictionary-style access
                return getattr(self, key, None)

        query_builder.model_adapter.get_entity_name.return_value = "test"
        query_builder.model_adapter.get_field_mapping.return_value = {"id": "id"}
        query_builder.database_adapter.execute_query = AsyncMock(
            return_value=[{"id": 123, "name": "Test"}]
        )
        query_builder.model_adapter.deserialize.side_effect = lambda x: x

        result = await query_builder.find_by_id(TestModel, 123)

        assert result is not None
        assert result["id"] == 123


class TestRegistry:
    """Test Registry functionality."""

    def test_registry_initialization(self) -> None:
        """Test Registry initialization."""
        reg = Registry()

        assert not reg._database_adapters
        assert not reg._model_adapters
        assert reg._default_database is None
        assert reg._default_model is None

    def test_register_database_adapter(self) -> None:
        """Test registering database adapters."""
        reg = Registry()
        adapter1 = MagicMock(spec=DatabaseAdapter)
        adapter2 = MagicMock(spec=DatabaseAdapter)

        # Register first adapter (becomes default)
        reg.register_database_adapter("sql", adapter1)
        assert reg._default_database == "sql"
        assert reg._database_adapters["sql"] == adapter1

        # Register second adapter (not default)
        reg.register_database_adapter("nosql", adapter2)
        assert reg._default_database == "sql"  # Still first one

        # Register third as explicit default
        adapter3 = MagicMock(spec=DatabaseAdapter)
        reg.register_database_adapter("graph", adapter3, is_default=True)
        assert reg._default_database == "graph"

    def test_register_model_adapter(self) -> None:
        """Test registering model adapters."""
        reg = Registry()
        adapter1 = MagicMock(spec=ModelAdapter)
        adapter2 = MagicMock(spec=ModelAdapter)

        reg.register_model_adapter("pydantic", adapter1)
        reg.register_model_adapter("sqlmodel", adapter2, is_default=True)

        assert reg._default_model == "sqlmodel"
        assert reg._model_adapters["pydantic"] == adapter1

    def test_get_database_adapter(self) -> None:
        """Test retrieving database adapters."""
        reg = Registry()
        adapter = MagicMock(spec=DatabaseAdapter)
        reg.register_database_adapter("sql", adapter)

        # Get by name
        assert reg.get_database_adapter("sql") == adapter

        # Get default
        assert reg.get_database_adapter() == adapter

        # Get non-existent
        with pytest.raises(ValueError, match="Database adapter 'nosql' not found"):
            reg.get_database_adapter("nosql")

    def test_get_model_adapter(self) -> None:
        """Test retrieving model adapters."""
        reg = Registry()
        adapter = MagicMock(spec=ModelAdapter)
        reg.register_model_adapter("pydantic", adapter)

        assert reg.get_model_adapter("pydantic") == adapter
        assert reg.get_model_adapter() == adapter

    def test_create_query_builder(self) -> None:
        """Test creating QueryBuilder from registry."""
        reg = Registry()
        db_adapter = MagicMock(spec=DatabaseAdapter)
        model_adapter = MagicMock(spec=ModelAdapter)

        reg.register_database_adapter("sql", db_adapter)
        reg.register_model_adapter("pydantic", model_adapter)

        builder = reg.create_query_builder()

        assert isinstance(builder, QueryBuilder)
        assert builder.database_adapter == db_adapter
        assert builder.model_adapter == model_adapter

    def test_global_registry(self) -> None:
        """Test that global registry instance exists."""
        assert isinstance(registry, Registry)

"""Database and Model Agnostic Query Interface Demo.

This example demonstrates the truly agnostic query interface that works with
any combination of database adapters and model frameworks.
"""

import asyncio
import contextlib
from datetime import datetime
from types import TracebackType
from typing import Any

from acb.adapters.models._pydantic import PydanticModelAdapter

# Import the agnostic query interface
from acb.adapters.models._query import QueryBuilder, registry
from acb.adapters.models._sqlmodel import SQLModelAdapter
from acb.adapters.nosql._query import NoSqlDatabaseAdapter
from acb.adapters.sql._query import SqlDatabaseAdapter

# Example models using different frameworks
try:
    from pydantic import BaseModel

    class User(BaseModel):
        id: int | None = None
        name: str
        email: str
        age: int
        created_at: datetime | None = None

        class Config:
            collection_name = "users"  # For NoSQL

    class Post(BaseModel):
        id: int | None = None
        title: str
        content: str
        user_id: int
        created_at: datetime | None = None

        class Config:
            collection_name = "posts"

    pydantic_available = True
except ImportError:
    pydantic_available = False
    User = None  # type: ignore
    Post = None  # type: ignore

try:
    from sqlmodel import Field, SQLModel

    class SQLUser(SQLModel, table=True):
        __tablename__ = "users"  # type: ignore

        id: int | None = Field(default=None, primary_key=True)
        name: str
        email: str
        age: int
        created_at: datetime | None = None

    class SQLPost(SQLModel, table=True):
        __tablename__ = "posts"  # type: ignore

        id: int | None = Field(default=None, primary_key=True)
        title: str
        content: str
        user_id: int
        created_at: datetime | None = None

    sqlmodel_available = True
except ImportError:
    sqlmodel_available = False
    SQLUser = None  # type: ignore
    SQLPost = None  # type: ignore


async def demo_agnostic_query_interface() -> None:
    """Demonstrate the database and model agnostic query interface."""
    # Setup adapters and registry
    adapters = await _setup_demo_adapters()
    await _register_adapters(adapters)

    # Run demo sections
    await _demo_same_model_different_databases()
    await _demo_same_database_different_models(adapters)
    await _demo_unified_query_interface()
    await _demo_type_safe_operations(adapters)
    await _demo_field_mapping_introspection(adapters)
    await _demo_adapter_swapping()
    await _demo_cross_adapter_compatibility()

    _print_demo_summary()


async def _setup_demo_adapters() -> dict[str, Any]:
    """Set up mock adapters for the demo."""
    # Create database adapters
    mock_sql = MockSqlAdapter()
    mock_nosql = MockNoSqlAdapter()

    sql_db_adapter = SqlDatabaseAdapter(mock_sql)  # type: ignore
    nosql_db_adapter = NoSqlDatabaseAdapter(mock_nosql)  # type: ignore

    # Create model adapters
    adapters: dict[str, Any] = {
        "sql_db": sql_db_adapter,
        "nosql_db": nosql_db_adapter,
    }

    if pydantic_available:
        adapters["pydantic"] = PydanticModelAdapter()

    if sqlmodel_available:
        adapters["sqlmodel"] = SQLModelAdapter()

    return adapters


class MockSqlAdapter:
    async def get_session(self) -> "MockSession":
        return MockSession()

    async def execute_query(self, entity: Any, query_spec: Any) -> list[dict[str, Any]]:
        return [{"id": 1, "name": "John", "email": "john@example.com", "age": 30}]

    async def execute_count(self, entity: Any, query_spec: Any) -> int:
        return 1


class MockNoSqlAdapter:
    async def find(
        self, collection: str, filter_dict: dict[str, Any], **options: Any
    ) -> list[dict[str, Any]]:
        return [
            {
                "_id": "507f1f77bcf86cd799439011",
                "name": "Jane",
                "email": "jane@example.com",
                "age": 25,
            },
        ]

    async def count(self, collection: str, filter_dict: dict[str, Any]) -> int:
        return 1


class MockSession:
    async def execute(self, query: Any, params: Any = None) -> "MockResult":
        return MockResult()

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def __aenter__(self) -> "MockSession":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass


class MockResult:
    def fetchall(self) -> list["MockRow"]:
        return [MockRow()]

    def fetchone(self) -> "MockRow":
        return MockRow()

    def scalar(self) -> int:
        return 1

    @property
    def rowcount(self) -> int:
        return 1


class MockRow:
    def __init__(self) -> None:
        self._mapping = {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "age": 30,
        }


def _create_mock_classes() -> dict[str, type[Any]]:
    """Create mock classes for database operations."""
    return {
        "MockSqlAdapter": MockSqlAdapter,
        "MockNoSqlAdapter": MockNoSqlAdapter,
        "MockSession": MockSession,
        "MockResult": MockResult,
        "MockRow": MockRow,
    }


async def _register_adapters(adapters: dict[str, Any]) -> None:
    """Register all adapters with the registry."""
    # Register database adapters
    registry.register_database_adapter("sql", adapters["sql_db"], is_default=True)
    registry.register_database_adapter("nosql", adapters["nosql_db"])

    # Register model adapters
    if pydantic_available:
        registry.register_model_adapter(
            "pydantic", adapters["pydantic"], is_default=True
        )

    if sqlmodel_available:
        registry.register_model_adapter("sqlmodel", adapters["sqlmodel"])


async def _demo_same_model_different_databases() -> None:
    """Demo 1: Same model, different databases."""
    if pydantic_available:
        # Pydantic model with SQL database
        sql_pydantic_builder = registry.create_query_builder("sql", "pydantic")
        with contextlib.suppress(Exception):
            sql_pydantic_builder.query(User)

        # Pydantic model with NoSQL database
        nosql_pydantic_builder = registry.create_query_builder("nosql", "pydantic")
        with contextlib.suppress(Exception):
            nosql_pydantic_builder.query(User)


async def _demo_same_database_different_models(adapters: dict[str, Any]) -> None:
    """Demo 2: Same database, different models."""
    if pydantic_available and sqlmodel_available:
        # SQL database with Pydantic model
        sql_pydantic_builder = registry.create_query_builder("sql", "pydantic")
        with contextlib.suppress(Exception):
            sql_pydantic_builder.query(User)

        # SQL database with SQLModel
        sql_sqlmodel_builder = registry.create_query_builder("sql", "sqlmodel")
        with contextlib.suppress(Exception):
            sql_sqlmodel_builder.query(SQLUser)


async def _demo_unified_query_interface() -> None:
    """Demo 3: Unified query interface."""
    if pydantic_available:
        builder = registry.create_query_builder()

        # Complex query example
        with contextlib.suppress(Exception):
            query = builder.query(User)
            (
                query.where_gt("age", 18)
                .where_like("email", "%@gmail.com")
                .order_by("created_at")
                .limit(10)
            )


async def _demo_type_safe_operations(adapters: dict[str, Any]) -> None:
    """Demo 4: Type-safe operations."""
    if pydantic_available:
        # Create operation
        with contextlib.suppress(Exception):
            new_user_data = {"name": "Alice", "email": "alice@example.com", "age": 28}

            # Validate data using model adapter
            adapters["pydantic"].validate_data(User, new_user_data)

            # This would work with any database
            # result = await builder.create(User, validated_data)


async def _demo_field_mapping_introspection(adapters: dict[str, Any]) -> None:
    """Demo 5: Field mapping and introspection."""
    if pydantic_available:
        pydantic_adapter = adapters["pydantic"]

        # Field mapping
        pydantic_adapter.get_field_mapping(User)

        # Primary key
        pydantic_adapter.get_primary_key_field(User)

        # Entity name
        pydantic_adapter.get_entity_name(User)


async def _demo_adapter_swapping() -> None:
    """Demo 6: Adapter swapping."""

    async def user_service_function(query_builder: QueryBuilder) -> str:  # noqa: ARG001
        """A service function that works with any adapter combination."""
        if pydantic_available:
            # This function works regardless of database or model adapter
            # query = query_builder.query(User)
            # users = await query.where_gt('age', 21).all()
            # return users
            return "Would return users over 21"
        return "No users (Pydantic not available)"

    # Same function, different adapters
    if pydantic_available:
        registry.create_query_builder("sql", "pydantic")

        registry.create_query_builder("nosql", "pydantic")


async def _demo_cross_adapter_compatibility() -> None:
    """Demo 7: Cross-adapter compatibility."""


def _print_demo_summary() -> None:
    """Print demo summary and key advantages."""


if __name__ == "__main__":
    asyncio.run(demo_agnostic_query_interface())

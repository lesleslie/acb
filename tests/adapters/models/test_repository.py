"""Tests for the Repository Pattern implementation."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acb.adapters.models._query import (
    QueryBuilder,
    QueryCondition,
    QueryOperator,
    QuerySpec,
)
from acb.adapters.models._repository import (
    AuditableRepository,
    GenericRepository,
    ReadOnlyRepository,
    Repository,
    RepositoryFactory,
    RepositoryOptions,
    RepositoryProtocol,
)
from acb.adapters.models._specification import Specification


class MockEntity:
    def __init__(self, id: int, name: str, status: str = "active") -> None:
        self.id = id
        self.name = name
        self.status = status
        self.created_at = datetime.now(tz=UTC)


class MockSpecification(Specification[MockEntity]):
    def __init__(self, status: str | None = None) -> None:
        self.status = status

    def is_satisfied_by(self, candidate: MockEntity) -> bool:
        """Check if the candidate entity satisfies this specification."""
        if self.status is None:
            return True
        return candidate.status == self.status

    def to_query_spec(self) -> QuerySpec:
        spec = QuerySpec()
        if self.status:
            spec.filter.conditions.append(
                QueryCondition("status", QueryOperator.EQ, self.status)
            )
        return spec


@pytest.fixture
def mock_query_builder():
    query_builder = MagicMock(spec=QueryBuilder)
    query_builder.model_adapter = MagicMock()
    query_builder.model_adapter.serialize = lambda x: {
        "id": x.id,
        "name": x.name,
        "status": x.status,
    }
    query_builder.model_adapter.deserialize_to_class = lambda cls, data: MockEntity(
        **data
    )
    query_builder.model_adapter.get_primary_key_field = lambda x: "id"

    # Mock query chain
    query_mock = MagicMock()
    query_mock.where = MagicMock(return_value=query_mock)
    query_mock.where_null = MagicMock(return_value=query_mock)
    query_mock.where_in = MagicMock(return_value=query_mock)
    query_mock.where_gte = MagicMock(return_value=query_mock)
    query_mock.order_by_desc = MagicMock(return_value=query_mock)
    query_mock.limit = MagicMock(return_value=query_mock)
    query_mock.offset = MagicMock(return_value=query_mock)
    query_mock.first = AsyncMock(return_value=None)
    query_mock.all = AsyncMock(return_value=[])
    query_mock.count = AsyncMock(return_value=0)
    query_mock.update = AsyncMock(return_value=True)
    query_mock.delete = AsyncMock(return_value=True)

    query_builder.query = MagicMock(return_value=query_mock)
    query_builder.create = AsyncMock(
        return_value={"id": 1, "name": "test", "status": "active"}
    )

    # Set up transaction as an async context manager
    @asynccontextmanager
    async def mock_transaction():
        yield MagicMock()

    query_builder.transaction = mock_transaction

    return query_builder


@pytest.fixture
def repository_options():
    return RepositoryOptions(
        cache_enabled=True,
        cache_ttl=60,
        batch_size=50,
        enable_soft_delete=False,
        audit_enabled=False,
    )


@pytest.fixture
def generic_repository(mock_query_builder, repository_options):
    return GenericRepository(MockEntity, mock_query_builder, repository_options)


class TestRepositoryOptions:
    def test_default_options(self) -> None:
        options = RepositoryOptions()
        assert options.cache_enabled
        assert options.cache_ttl == 300
        assert options.batch_size == 100
        assert not options.enable_soft_delete
        assert options.soft_delete_field == "deleted_at"
        assert not options.audit_enabled
        assert options.audit_fields == [
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class TestRepositoryProtocol:
    def test_protocol_check(self) -> None:
        # Create a mock that implements the protocol
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock()
        mock_repo.find_all = AsyncMock()
        mock_repo.find_by_specification = AsyncMock()
        mock_repo.count = AsyncMock()
        mock_repo.exists = AsyncMock()
        mock_repo.create = AsyncMock()
        mock_repo.update = AsyncMock()
        mock_repo.delete = AsyncMock()

        assert isinstance(mock_repo, RepositoryProtocol)


class TestGenericRepository:
    async def test_find_by_id_not_cached(
        self, generic_repository, mock_query_builder
    ) -> None:
        entity = MockEntity(1, "test")
        mock_query_builder.query().first.return_value = entity

        result = await generic_repository.find_by_id(1)

        assert result == entity
        assert 1 in generic_repository._cache
        mock_query_builder.query().where.assert_called_with("id", 1)

    async def test_find_by_id_cached(self, generic_repository) -> None:
        entity = MockEntity(1, "test")
        generic_repository._add_to_cache(1, entity)

        with patch.object(generic_repository, "_is_cache_valid", return_value=True):
            result = await generic_repository.find_by_id(1)

        assert result == entity

    async def test_find_by_id_cache_expired(
        self, generic_repository, mock_query_builder
    ) -> None:
        entity = MockEntity(1, "test")
        generic_repository._add_to_cache(1, entity)
        new_entity = MockEntity(1, "updated")
        mock_query_builder.query().first.return_value = new_entity

        with patch.object(generic_repository, "_is_cache_valid", return_value=False):
            result = await generic_repository.find_by_id(1)

        assert result == new_entity
        assert (
            1 in generic_repository._cache_timestamps
        )  # Should be re-cached with new timestamp

    async def test_find_all(self, generic_repository, mock_query_builder) -> None:
        entities = [MockEntity(1, "test1"), MockEntity(2, "test2")]
        mock_query_builder.query().all.return_value = entities

        result = await generic_repository.find_all(limit=10, offset=5)

        assert result == entities
        mock_query_builder.query().limit.assert_called_with(10)
        mock_query_builder.query().offset.assert_called_with(5)

    async def test_find_all_with_soft_delete(self, mock_query_builder) -> None:
        options = RepositoryOptions(enable_soft_delete=True)
        repo = GenericRepository(MockEntity, mock_query_builder, options)

        await repo.find_all()

        mock_query_builder.query().where_null.assert_called_with("deleted_at")

    async def test_find_by_specification(
        self, generic_repository, mock_query_builder
    ) -> None:
        spec = MockSpecification(status="active")
        entities = [MockEntity(1, "test1")]
        mock_query_builder.query().all.return_value = entities

        result = await generic_repository.find_by_specification(spec)

        assert result == entities
        assert mock_query_builder.query().query_spec is not None

    async def test_count(self, generic_repository, mock_query_builder) -> None:
        mock_query_builder.query().count.return_value = 5

        result = await generic_repository.count()

        assert result == 5

    async def test_count_with_specification(
        self, generic_repository, mock_query_builder
    ) -> None:
        spec = MockSpecification(status="active")
        mock_query_builder.query().count.return_value = 3

        result = await generic_repository.count(spec)

        assert result == 3

    async def test_exists(self, generic_repository, mock_query_builder) -> None:
        spec = MockSpecification(status="active")
        mock_query_builder.query().count.return_value = 1

        result = await generic_repository.exists(spec)

        assert result

    async def test_exists_false(self, generic_repository, mock_query_builder) -> None:
        spec = MockSpecification(status="inactive")
        mock_query_builder.query().count.return_value = 0

        result = await generic_repository.exists(spec)

        assert not result

    async def test_create(self, generic_repository, mock_query_builder) -> None:
        entity_data = {"name": "test", "status": "active"}
        mock_query_builder.create.return_value = {"id": 1} | entity_data

        result = await generic_repository.create(entity_data)

        assert isinstance(result, MockEntity)
        assert result.id == 1
        assert result.name == "test"
        assert 1 in generic_repository._cache

    async def test_create_with_audit(self, mock_query_builder) -> None:
        options = RepositoryOptions(audit_enabled=True)
        repo = GenericRepository(MockEntity, mock_query_builder, options)
        entity_data = {"name": "test"}

        with patch("datetime.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now

            await repo.create(entity_data)

            call_args = mock_query_builder.create.call_args[0][1]
            assert call_args["created_at"] == mock_now
            assert call_args["updated_at"] == mock_now

    async def test_update(self, generic_repository, mock_query_builder) -> None:
        entity = MockEntity(1, "updated")
        mock_query_builder.query().first.return_value = entity

        result = await generic_repository.update(1, {"name": "updated"})

        assert result == entity
        mock_query_builder.query().where.assert_called_with("id", 1)
        mock_query_builder.query().update.assert_called_with({"name": "updated"})

    async def test_update_removes_from_cache(
        self, generic_repository, mock_query_builder
    ) -> None:
        entity = MockEntity(1, "test")
        generic_repository._add_to_cache(1, entity)

        await generic_repository.update(1, {"name": "updated"})

        assert 1 not in generic_repository._cache

    async def test_delete(self, generic_repository, mock_query_builder) -> None:
        result = await generic_repository.delete(1)

        assert result
        mock_query_builder.query().where.assert_called_with("id", 1)
        mock_query_builder.query().delete.assert_called_once()

    async def test_soft_delete(self, mock_query_builder) -> None:
        options = RepositoryOptions(enable_soft_delete=True)
        repo = GenericRepository(MockEntity, mock_query_builder, options)

        with patch("datetime.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now

            result = await repo.delete(1)

            assert result
            mock_query_builder.query().update.assert_called_with(
                {"deleted_at": mock_now}
            )

    async def test_batch_create(self, generic_repository, mock_query_builder) -> None:
        entities_data = [{"name": f"test{i}"} for i in range(5)]
        mock_query_builder.create.return_value = [
            {"id": i} | data for i, data in enumerate(entities_data)
        ]

        result = await generic_repository.batch_create(entities_data)

        assert len(result) == 5

    async def test_batch_create_with_batching(
        self, generic_repository, mock_query_builder
    ) -> None:
        generic_repository.options.batch_size = 2
        entities_data = [{"name": f"test{i}"} for i in range(5)]
        mock_query_builder.create.side_effect = [
            [{"id": 0, "name": "test0"}, {"id": 1, "name": "test1"}],
            [{"id": 2, "name": "test2"}, {"id": 3, "name": "test3"}],
            [{"id": 4, "name": "test4"}],
        ]

        result = await generic_repository.batch_create(entities_data)

        assert len(result) == 5
        assert mock_query_builder.create.call_count == 3

    async def test_batch_update(self, generic_repository, mock_query_builder) -> None:
        updates = [
            {"id": 1, "name": "updated1"},
            {"id": 2, "name": "updated2"},
        ]
        mock_query_builder.query().first.side_effect = [
            MockEntity(1, "updated1"),
            MockEntity(2, "updated2"),
        ]

        result = await generic_repository.batch_update(updates)

        assert len(result) == 2

    async def test_batch_delete(self, generic_repository, mock_query_builder) -> None:
        ids = [1, 2, 3]

        result = await generic_repository.batch_delete(ids)

        assert result == 3
        mock_query_builder.query().where_in.assert_called_with("id", ids)

    async def test_transaction(self, generic_repository) -> None:
        async with generic_repository.transaction() as txn:
            assert txn is not None

    def test_cache_operations(self, generic_repository) -> None:
        entity = MockEntity(1, "test")

        # Test add to cache
        generic_repository._add_to_cache(1, entity)
        assert 1 in generic_repository._cache
        assert 1 in generic_repository._cache_timestamps

        # Test cache validity
        assert generic_repository._is_cache_valid(1)

        # Test invalid cache
        generic_repository._cache_timestamps[1] = 0
        assert not generic_repository._is_cache_valid(1)

        # Test remove from cache
        generic_repository._remove_from_cache(1)
        assert 1 not in generic_repository._cache
        assert 1 not in generic_repository._cache_timestamps

    def test_clear_cache(self, generic_repository) -> None:
        entity = MockEntity(1, "test")
        generic_repository._add_to_cache(1, entity)

        generic_repository.clear_cache()

        assert len(generic_repository._cache) == 0
        assert len(generic_repository._cache_timestamps) == 0

    def test_warm_cache(self, generic_repository) -> None:
        entities = [MockEntity(1, "test1"), MockEntity(2, "test2")]

        generic_repository.warm_cache(entities)

        assert 1 in generic_repository._cache
        assert 2 in generic_repository._cache

    async def test_find_active(self, generic_repository, mock_query_builder) -> None:
        entities = [MockEntity(1, "test1")]
        mock_query_builder.query().all.return_value = entities

        result = await generic_repository.find_active()

        assert result == entities
        mock_query_builder.query().where.assert_called_with("status", "active")

    async def test_find_active_fallback(
        self, generic_repository, mock_query_builder
    ) -> None:
        # Create a mock that fails on the first two attempts but succeeds on the third
        mock_query = mock_query_builder.query.return_value

        # First call to where("status", "active") raises exception
        def where_side_effect(*args, **kwargs):
            if args == ("status", "active"):
                raise Exception("First attempt fails")
            if args == ("active", True):
                # Return a mock that will fail on .all()
                failed_query = MagicMock()
                failed_query.all = AsyncMock(
                    side_effect=Exception("Second attempt fails")
                )
                return failed_query
            return mock_query

        mock_query.where.side_effect = where_side_effect
        mock_query.all.return_value = []  # For the final find_all() call

        result = await generic_repository.find_active()

        assert not result

    async def test_find_recent(self, generic_repository, mock_query_builder) -> None:
        entities = [MockEntity(1, "test1")]
        mock_query_builder.query().all.return_value = entities

        with patch("datetime.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 8, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now

            await generic_repository.find_recent(days=7)

            expected_cutoff = mock_now - timedelta(days=7)
            mock_query_builder.query().where_gte.assert_called_with(
                "created_at", expected_cutoff
            )


class TestRepositoryFactory:
    def test_get_repository_creates_new(self) -> None:
        query_builder = MagicMock()
        factory = RepositoryFactory(query_builder)

        assert isinstance(repo := factory.get_repository(MockEntity), GenericRepository)
        assert repo.model_class == MockEntity

    def test_get_repository_returns_cached(self) -> None:
        query_builder = MagicMock()
        factory = RepositoryFactory(query_builder)

        repo1 = factory.get_repository(MockEntity)
        repo2 = factory.get_repository(MockEntity)

        assert repo1 is repo2

    def test_register_repository(self) -> None:
        query_builder = MagicMock()
        factory = RepositoryFactory(query_builder)
        custom_repo = MagicMock(spec=Repository)

        factory.register_repository(MockEntity, custom_repo)
        repo = factory.get_repository(MockEntity)

        assert repo is custom_repo

    def test_create_repository(self) -> None:
        query_builder = MagicMock()
        factory = RepositoryFactory(query_builder)
        options = RepositoryOptions(cache_ttl=60)

        repo = factory.create_repository(MockEntity, options)

        assert isinstance(repo, GenericRepository)
        assert repo.options.cache_ttl == 60


class TestReadOnlyRepository:
    @pytest.fixture
    def readonly_repo(self, mock_query_builder):
        class TestReadOnlyRepo(ReadOnlyRepository[MockEntity]):
            async def find_active(self):
                return []

            async def find_recent(self, days: int = 7):
                return []

        return TestReadOnlyRepo(MockEntity, mock_query_builder)

    async def test_create_not_allowed(self, readonly_repo) -> None:
        with pytest.raises(
            NotImplementedError, match="Create operation is not allowed"
        ):
            await readonly_repo.create({"name": "test"})

    async def test_update_not_allowed(self, readonly_repo) -> None:
        with pytest.raises(
            NotImplementedError, match="Update operation is not allowed"
        ):
            await readonly_repo.update(1, {"name": "test"})

    async def test_delete_not_allowed(self, readonly_repo) -> None:
        with pytest.raises(
            NotImplementedError, match="Delete operation is not allowed"
        ):
            await readonly_repo.delete(1)

    async def test_batch_create_not_allowed(self, readonly_repo) -> None:
        with pytest.raises(
            NotImplementedError, match="Batch create operation is not allowed"
        ):
            await readonly_repo.batch_create([{"name": "test"}])

    async def test_batch_update_not_allowed(self, readonly_repo) -> None:
        with pytest.raises(
            NotImplementedError, match="Batch update operation is not allowed"
        ):
            await readonly_repo.batch_update([{"id": 1, "name": "test"}])

    async def test_batch_delete_not_allowed(self, readonly_repo) -> None:
        with pytest.raises(
            NotImplementedError, match="Batch delete operation is not allowed"
        ):
            await readonly_repo.batch_delete([1, 2, 3])


class TestAuditableRepository:
    @pytest.fixture
    def auditable_repo(self, mock_query_builder):
        class TestAuditableRepo(AuditableRepository[MockEntity]):
            async def find_active(self):
                return []

            async def find_recent(self, days: int = 7):
                return []

        return TestAuditableRepo(MockEntity, mock_query_builder)

    def test_audit_enabled_by_default(self, auditable_repo) -> None:
        assert auditable_repo.options.audit_enabled

    async def test_get_audit_trail(self, auditable_repo) -> None:
        result = await auditable_repo.get_audit_trail(1)
        assert not result

    async def test_get_entity_versions(self, auditable_repo) -> None:
        result = await auditable_repo.get_entity_versions(1)
        assert not result


class TestAuditFields:
    def test_add_audit_fields_create(self, generic_repository) -> None:
        generic_repository.options.audit_enabled = True
        data = {"name": "test"}

        with patch("datetime.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now

            result = generic_repository._add_audit_fields(data, is_create=True)

            assert result["created_at"] == mock_now
            assert result["updated_at"] == mock_now
            assert result["created_by"] is None
            assert result["updated_by"] is None

    def test_add_audit_fields_update(self, generic_repository) -> None:
        generic_repository.options.audit_enabled = True
        data = {"name": "test"}

        with patch("datetime.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now

            result = generic_repository._add_audit_fields(data, is_create=False)

            assert "created_at" not in result
            assert result["updated_at"] == mock_now
            assert "created_by" not in result
            assert result["updated_by"] is None

    def test_get_current_user_id(self, generic_repository) -> None:
        assert generic_repository._get_current_user_id() is None

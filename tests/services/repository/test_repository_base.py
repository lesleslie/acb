"""Tests for Repository Base Classes."""

import pytest
from dataclasses import dataclass
from typing import Any

from acb.services.repository._base import (
    DuplicateEntityError,
    EntityNotFoundError,
    PaginationInfo,
    RepositoryBase,
    RepositorySettings,
    SortCriteria,
    SortDirection,
)


@dataclass
class SampleEntity:
    """Test entity for repository tests."""

    id: int | None = None
    name: str = ""
    active: bool = True


class SampleRepository(RepositoryBase[SampleEntity, int]):
    """Test repository implementation."""

    def __init__(self):
        super().__init__(SampleEntity, RepositorySettings())
        self._entities: dict[int, SampleEntity] = {}
        self._next_id = 1

    async def create(self, entity: SampleEntity) -> SampleEntity:
        """Create test entity."""
        if entity.id and entity.id in self._entities:
            raise DuplicateEntityError("SampleEntity", "id", entity.id)

        if not entity.id:
            entity.id = self._next_id
            self._next_id += 1

        self._entities[entity.id] = entity
        await self._increment_metric("create", True)
        return entity

    async def get_by_id(self, entity_id: int) -> SampleEntity | None:
        """Get test entity by ID."""
        await self._increment_metric("get_by_id", True)
        return self._entities.get(entity_id)

    async def update(self, entity: SampleEntity) -> SampleEntity:
        """Update test entity."""
        if not entity.id or entity.id not in self._entities:
            raise EntityNotFoundError("SampleEntity", entity.id)

        self._entities[entity.id] = entity
        await self._increment_metric("update", True)
        return entity

    async def delete(self, entity_id: int) -> bool:
        """Delete test entity."""
        if entity_id in self._entities:
            del self._entities[entity_id]
            await self._increment_metric("delete", True)
            return True
        return False

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        sort: list[SortCriteria] | None = None,
        pagination: PaginationInfo | None = None,
    ) -> list[SampleEntity]:
        """List test entities."""
        entities = list(self._entities.values())

        # Apply filters
        if filters:
            filtered = []
            for entity in entities:
                match = True
                for key, value in filters.items():
                    if not hasattr(entity, key) or getattr(entity, key) != value:
                        match = False
                        break
                if match:
                    filtered.append(entity)
            entities = filtered

        # Apply sorting
        if sort:
            for sort_criteria in reversed(sort):
                entities.sort(
                    key=lambda e: getattr(e, sort_criteria.field, None),
                    reverse=(sort_criteria.direction == SortDirection.DESC),
                )

        # Apply pagination
        if pagination:
            start_idx = pagination.offset
            end_idx = start_idx + pagination.page_size
            entities = entities[start_idx:end_idx]

        await self._increment_metric("list", True)
        return entities

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count test entities."""
        if not filters:
            count = len(self._entities)
        else:
            count = 0
            for entity in self._entities.values():
                match = True
                for key, value in filters.items():
                    if not hasattr(entity, key) or getattr(entity, key) != value:
                        match = False
                        break
                if match:
                    count += 1

        await self._increment_metric("count", True)
        return count


@pytest.fixture
def repository():
    """Create test repository."""
    return SampleRepository()


@pytest.fixture
def test_entity():
    """Create test entity."""
    return SampleEntity(name="Test Entity", active=True)


class SampleRepositoryBase:
    """Test RepositoryBase functionality."""

    @pytest.mark.asyncio
    async def test_create_entity(self, repository, test_entity):
        """Test entity creation."""
        created = await repository.create(test_entity)

        assert created.id is not None
        assert created.name == test_entity.name
        assert created.active == test_entity.active

    @pytest.mark.asyncio
    async def test_get_by_id(self, repository, test_entity):
        """Test get entity by ID."""
        created = await repository.create(test_entity)
        retrieved = await repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository):
        """Test get entity by ID when not found."""
        retrieved = await repository.get_by_id(999)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise(self, repository, test_entity):
        """Test get entity by ID or raise."""
        created = await repository.create(test_entity)
        retrieved = await repository.get_by_id_or_raise(created.id)

        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_not_found(self, repository):
        """Test get entity by ID or raise when not found."""
        with pytest.raises(EntityNotFoundError) as exc_info:
            await repository.get_by_id_or_raise(999)

        assert exc_info.value.entity_type == "SampleEntity"
        assert exc_info.value.entity_id == 999

    @pytest.mark.asyncio
    async def test_update_entity(self, repository, test_entity):
        """Test entity update."""
        created = await repository.create(test_entity)
        created.name = "Updated Name"

        updated = await repository.update(created)
        assert updated.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_entity_not_found(self, repository):
        """Test update entity when not found."""
        entity = SampleEntity(id=999, name="Not Found")

        with pytest.raises(EntityNotFoundError):
            await repository.update(entity)

    @pytest.mark.asyncio
    async def test_delete_entity(self, repository, test_entity):
        """Test entity deletion."""
        created = await repository.create(test_entity)
        deleted = await repository.delete(created.id)

        assert deleted is True

        # Verify entity is gone
        retrieved = await repository.get_by_id(created.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_entity_not_found(self, repository):
        """Test delete entity when not found."""
        deleted = await repository.delete(999)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_or_raise(self, repository, test_entity):
        """Test delete entity or raise."""
        created = await repository.create(test_entity)
        await repository.delete_or_raise(created.id)

        # Verify entity is gone
        retrieved = await repository.get_by_id(created.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_or_raise_not_found(self, repository):
        """Test delete entity or raise when not found."""
        with pytest.raises(EntityNotFoundError):
            await repository.delete_or_raise(999)

    @pytest.mark.asyncio
    async def test_list_entities(self, repository):
        """Test listing entities."""
        # Create test entities
        entity1 = SampleEntity(name="Entity 1", active=True)
        entity2 = SampleEntity(name="Entity 2", active=False)

        await repository.create(entity1)
        await repository.create(entity2)

        # List all entities
        entities = await repository.list()
        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_list_entities_with_filters(self, repository):
        """Test listing entities with filters."""
        # Create test entities
        entity1 = SampleEntity(name="Entity 1", active=True)
        entity2 = SampleEntity(name="Entity 2", active=False)

        await repository.create(entity1)
        await repository.create(entity2)

        # List active entities only
        active_entities = await repository.list(filters={"active": True})
        assert len(active_entities) == 1
        assert active_entities[0].active is True

    @pytest.mark.asyncio
    async def test_list_entities_with_sorting(self, repository):
        """Test listing entities with sorting."""
        # Create test entities
        entity1 = SampleEntity(name="B Entity")
        entity2 = SampleEntity(name="A Entity")

        await repository.create(entity1)
        await repository.create(entity2)

        # Sort by name ascending
        sorted_entities = await repository.list(
            sort=[SortCriteria("name", SortDirection.ASC)]
        )
        assert sorted_entities[0].name == "A Entity"
        assert sorted_entities[1].name == "B Entity"

    @pytest.mark.asyncio
    async def test_list_entities_with_pagination(self, repository):
        """Test listing entities with pagination."""
        # Create test entities
        for i in range(5):
            entity = SampleEntity(name=f"Entity {i}")
            await repository.create(entity)

        # Get first page
        pagination = PaginationInfo(page=1, page_size=2)
        entities = await repository.list(pagination=pagination)
        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_count_entities(self, repository):
        """Test counting entities."""
        # Create test entities
        entity1 = SampleEntity(name="Entity 1", active=True)
        entity2 = SampleEntity(name="Entity 2", active=False)

        await repository.create(entity1)
        await repository.create(entity2)

        # Count all entities
        total_count = await repository.count()
        assert total_count == 2

        # Count active entities
        active_count = await repository.count(filters={"active": True})
        assert active_count == 1

    @pytest.mark.asyncio
    async def test_exists(self, repository, test_entity):
        """Test entity existence check."""
        # Entity doesn't exist yet
        exists_before = await repository.exists(1)
        assert exists_before is False

        # Create entity
        created = await repository.create(test_entity)

        # Entity exists now
        exists_after = await repository.exists(created.id)
        assert exists_after is True

    @pytest.mark.asyncio
    async def test_list_paginated(self, repository):
        """Test paginated listing."""
        # Create test entities
        for i in range(5):
            entity = SampleEntity(name=f"Entity {i}")
            await repository.create(entity)

        # Get paginated results
        entities, pagination = await repository.list_paginated(page=1, page_size=2)

        assert len(entities) == 2
        assert pagination.page == 1
        assert pagination.page_size == 2
        assert pagination.total_items == 5
        assert pagination.total_pages == 3
        assert pagination.has_next is True
        assert pagination.has_previous is False

    @pytest.mark.asyncio
    async def test_batch_create(self, repository):
        """Test batch entity creation."""
        entities = [
            SampleEntity(name="Entity 1"),
            SampleEntity(name="Entity 2"),
            SampleEntity(name="Entity 3"),
        ]

        created_entities = await repository.batch_create(entities)
        assert len(created_entities) == 3

        for entity in created_entities:
            assert entity.id is not None

    @pytest.mark.asyncio
    async def test_batch_update(self, repository):
        """Test batch entity update."""
        # Create entities first
        entities = [SampleEntity(name="Entity 1"), SampleEntity(name="Entity 2")]
        created_entities = await repository.batch_create(entities)

        # Update them
        for entity in created_entities:
            entity.name = f"Updated {entity.name}"

        updated_entities = await repository.batch_update(created_entities)
        assert all("Updated" in entity.name for entity in updated_entities)

    @pytest.mark.asyncio
    async def test_batch_delete(self, repository):
        """Test batch entity deletion."""
        # Create entities first
        entities = [
            SampleEntity(name="Entity 1"),
            SampleEntity(name="Entity 2"),
            SampleEntity(name="Entity 3"),
        ]
        created_entities = await repository.batch_create(entities)

        # Delete them
        entity_ids = [entity.id for entity in created_entities]
        deleted_count = await repository.batch_delete(entity_ids)

        assert deleted_count == 3

        # Verify they're gone
        total_count = await repository.count()
        assert total_count == 0

    @pytest.mark.asyncio
    async def test_get_metrics(self, repository, test_entity):
        """Test repository metrics."""
        # Perform some operations
        await repository.create(test_entity)
        await repository.get_by_id(1)
        await repository.count()

        metrics = await repository.get_metrics()

        assert metrics["entity_type"] == "SampleEntity"
        assert "operations" in metrics
        assert metrics["operations"]["create_success"] >= 1
        assert metrics["operations"]["get_by_id_success"] >= 1
        assert metrics["operations"]["count_success"] >= 1


class TestPaginationInfo:
    """Test PaginationInfo functionality."""

    def test_pagination_info_basic(self):
        """Test basic pagination info."""
        pagination = PaginationInfo(page=2, page_size=10, total_items=25)

        assert pagination.page == 2
        assert pagination.page_size == 10
        assert pagination.total_items == 25
        assert pagination.total_pages == 3
        assert pagination.offset == 10
        assert pagination.has_next is True
        assert pagination.has_previous is True

    def test_pagination_info_first_page(self):
        """Test pagination info for first page."""
        pagination = PaginationInfo(page=1, page_size=10, total_items=5)

        assert pagination.offset == 0
        assert pagination.has_next is False
        assert pagination.has_previous is False

    def test_pagination_info_last_page(self):
        """Test pagination info for last page."""
        pagination = PaginationInfo(page=3, page_size=10, total_items=25)

        assert pagination.offset == 20
        assert pagination.has_next is False
        assert pagination.has_previous is True


class SampleRepositorySettings:
    """Test RepositorySettings functionality."""

    def test_repository_settings_defaults(self):
        """Test repository settings defaults."""
        settings = RepositorySettings()

        assert settings.cache_enabled is True
        assert settings.cache_ttl == 300
        assert settings.default_page_size == 50
        assert settings.max_page_size == 1000
        assert settings.query_timeout == 30.0

    def test_repository_settings_validation(self):
        """Test repository settings validation."""
        with pytest.raises(ValueError):
            RepositorySettings(default_page_size=2000, max_page_size=1000)


class SampleRepositoryErrors:
    """Test repository error handling."""

    def test_entity_not_found_error(self):
        """Test EntityNotFoundError."""
        error = EntityNotFoundError("SampleEntity", 123)

        assert error.entity_type == "SampleEntity"
        assert error.entity_id == 123
        assert error.operation == "find"
        assert "SampleEntity with ID 123 not found" in str(error)

    def test_duplicate_entity_error(self):
        """Test DuplicateEntityError."""
        error = DuplicateEntityError("SampleEntity", "email", "test@example.com")

        assert error.entity_type == "SampleEntity"
        assert error.conflict_field == "email"
        assert error.value == "test@example.com"
        assert error.operation == "create"
        assert "SampleEntity with email=test@example.com already exists" in str(error)

"""Tests for Custom Feature Store Adapter."""

import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from pathlib import Path

from acb.adapters.feature_store.custom import (
    CustomFeatureStoreAdapter,
    CustomFeatureStoreSettings,
)
from acb.adapters.feature_store._base import (
    FeatureDefinition,
    FeatureServingRequest,
    FeatureGroup,
    FeatureView,
    FeatureDataType,
    FeatureStatus,
)


@pytest.fixture
def temp_directory():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def custom_settings(temp_directory):
    """Create Custom Feature Store settings for testing."""
    return CustomFeatureStoreSettings(
        storage_path=temp_directory,
        online_store_type="memory",
        offline_store_type="file",
        enable_compression=True,
        cache_size=1000,
    )


class TestCustomFeatureStoreAdapter:
    """Test Custom Feature Store adapter implementation."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, custom_settings):
        """Test Custom adapter initialization."""
        adapter = CustomFeatureStoreAdapter(custom_settings)
        assert adapter.settings == custom_settings
        assert adapter._db_connection is None
        assert adapter._cache is None

    @pytest.mark.asyncio
    async def test_client_creation(self, custom_settings):
        """Test client creation."""
        adapter = CustomFeatureStoreAdapter(custom_settings)
        client = await adapter._create_client()

        assert client is not None
        assert "db" in client
        assert "cache" in client

    @pytest.mark.asyncio
    async def test_online_feature_serving(self, custom_settings):
        """Test online feature serving."""
        adapter = CustomFeatureStoreAdapter(custom_settings)

        # First register a feature
        feature_def = FeatureDefinition(
            name="user_age",
            data_type=FeatureDataType.INTEGER,
            description="User age",
            feature_group="user_features",
            status=FeatureStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await adapter.register_feature(feature_def)

        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age"],
        )

        response = await adapter.get_online_features(request)

        assert response.entity_id == "user_123"
        assert "user_age" in response.features

    @pytest.mark.asyncio
    async def test_offline_feature_serving(self, custom_settings):
        """Test offline feature serving."""
        adapter = CustomFeatureStoreAdapter(custom_settings)

        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age"],
        )

        vectors = await adapter.get_offline_features(request)
        assert isinstance(vectors, list)

    @pytest.mark.asyncio
    async def test_feature_registration(self, custom_settings):
        """Test feature registration."""
        adapter = CustomFeatureStoreAdapter(custom_settings)

        feature_def = FeatureDefinition(
            name="user_age",
            data_type=FeatureDataType.INTEGER,
            description="User age",
            feature_group="user_features",
            status=FeatureStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        result = await adapter.register_feature(feature_def)
        assert result is True

        # Verify feature was registered
        features = await adapter.list_features()
        assert len(features) == 1
        assert features[0].name == "user_age"

    @pytest.mark.asyncio
    async def test_feature_management(self, custom_settings):
        """Test feature CRUD operations."""
        adapter = CustomFeatureStoreAdapter(custom_settings)

        feature_def = FeatureDefinition(
            name="user_age",
            data_type=FeatureDataType.INTEGER,
            description="User age",
            feature_group="user_features",
            status=FeatureStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Create
        await adapter.register_feature(feature_def)

        # Read
        feature = await adapter.get_feature("user_age")
        assert feature is not None
        assert feature.name == "user_age"

        # List
        features = await adapter.list_features()
        assert len(features) == 1

        # Delete
        result = await adapter.delete_feature("user_age")
        assert result is True

        # Verify deletion
        feature = await adapter.get_feature("user_age")
        assert feature is None

    @pytest.mark.asyncio
    async def test_feature_group_management(self, custom_settings):
        """Test feature group CRUD operations."""
        adapter = CustomFeatureStoreAdapter(custom_settings)

        group = FeatureGroup(
            name="user_features",
            description="User-related features",
            entity_type="user",
            online_store_enabled=True,
            offline_store_enabled=True,
            created_at=datetime.now(),
        )

        # Create
        result = await adapter.create_feature_group(group)
        assert result is True

        # Read
        retrieved_group = await adapter.get_feature_group("user_features")
        assert retrieved_group is not None
        assert retrieved_group.name == "user_features"

        # List
        groups = await adapter.list_feature_groups()
        assert len(groups) == 1

        # Delete
        result = await adapter.delete_feature_group("user_features")
        assert result is True

    @pytest.mark.asyncio
    async def test_feature_view_management(self, custom_settings):
        """Test feature view CRUD operations."""
        adapter = CustomFeatureStoreAdapter(custom_settings)

        view = FeatureView(
            name="user_profile_view",
            description="User profile features",
            feature_group="user_features",
            feature_names=["user_age", "user_location"],
            ttl_hours=24,
            created_at=datetime.now(),
        )

        # Create
        result = await adapter.create_feature_view(view)
        assert result is True

        # Read
        retrieved_view = await adapter.get_feature_view("user_profile_view")
        assert retrieved_view is not None
        assert retrieved_view.name == "user_profile_view"

        # List
        views = await adapter.list_feature_views()
        assert len(views) == 1

        # Delete
        result = await adapter.delete_feature_view("user_profile_view")
        assert result is True

    @pytest.mark.asyncio
    async def test_storage_persistence(self, custom_settings):
        """Test that data persists to storage."""
        adapter = CustomFeatureStoreAdapter(custom_settings)

        feature_def = FeatureDefinition(
            name="user_age",
            data_type=FeatureDataType.INTEGER,
            description="User age",
            feature_group="user_features",
            status=FeatureStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        await adapter.register_feature(feature_def)

        # Check that storage file was created
        storage_path = Path(custom_settings.storage_path)
        db_file = storage_path / "feature_store.db"
        assert db_file.exists()

    @pytest.mark.asyncio
    async def test_caching(self, custom_settings):
        """Test caching functionality."""
        adapter = CustomFeatureStoreAdapter(custom_settings)

        # Register a feature
        feature_def = FeatureDefinition(
            name="user_age",
            data_type=FeatureDataType.INTEGER,
            description="User age",
            feature_group="user_features",
            status=FeatureStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await adapter.register_feature(feature_def)

        # First call should cache the result
        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age"],
        )

        response1 = await adapter.get_online_features(request)
        response2 = await adapter.get_online_features(request)

        # Both should return valid responses
        assert response1.entity_id == "user_123"
        assert response2.entity_id == "user_123"

    @pytest.mark.asyncio
    async def test_health_check(self, custom_settings):
        """Test health check."""
        adapter = CustomFeatureStoreAdapter(custom_settings)
        health = await adapter.health_check()
        assert health is True

    @pytest.mark.asyncio
    async def test_context_manager(self, custom_settings):
        """Test adapter as context manager."""
        adapter = CustomFeatureStoreAdapter(custom_settings)
        async with adapter:
            assert adapter._db_connection is not None
            assert adapter._cache is not None

    @pytest.mark.asyncio
    async def test_feature_monitoring(self, custom_settings):
        """Test feature monitoring."""
        adapter = CustomFeatureStoreAdapter(custom_settings)
        metrics = await adapter.monitor_features(["user_age"])

        assert metrics.feature_names == ["user_age"]
        assert metrics.request_count >= 0
        assert metrics.avg_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_data_quality_validation(self, custom_settings):
        """Test data quality validation."""
        adapter = CustomFeatureStoreAdapter(custom_settings)
        result = await adapter.validate_data_quality(["user_age"], "local_file")

        assert result.feature_names == ["user_age"]
        assert result.data_source == "local_file"

    @pytest.mark.asyncio
    async def test_feature_lineage(self, custom_settings):
        """Test feature lineage."""
        adapter = CustomFeatureStoreAdapter(custom_settings)
        lineage = await adapter.get_feature_lineage("user_age")

        assert lineage.feature_name == "user_age"
        assert isinstance(lineage.upstream_sources, list)
        assert isinstance(lineage.downstream_consumers, list)

    @pytest.mark.asyncio
    async def test_compression(self, custom_settings):
        """Test compression functionality."""
        # Enable compression
        custom_settings.enable_compression = True
        adapter = CustomFeatureStoreAdapter(custom_settings)

        feature_def = FeatureDefinition(
            name="user_age",
            data_type=FeatureDataType.INTEGER,
            description="User age",
            feature_group="user_features",
            status=FeatureStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        result = await adapter.register_feature(feature_def)
        assert result is True

    @pytest.mark.asyncio
    async def test_error_handling(self, custom_settings):
        """Test error handling."""
        # Test with invalid storage path
        custom_settings.storage_path = "/invalid/path/that/does/not/exist"
        adapter = CustomFeatureStoreAdapter(custom_settings)

        health = await adapter.health_check()
        # Should still return True as it creates directories
        assert health is True


class TestCustomFeatureStoreSettings:
    """Test Custom Feature Store settings."""

    def test_settings_creation(self):
        """Test settings creation."""
        settings = CustomFeatureStoreSettings(
            storage_path="/tmp/feature_store",
            online_store_type="memory",
            offline_store_type="file",
        )

        assert settings.storage_path == "/tmp/feature_store"
        assert settings.online_store_type == "memory"
        assert settings.offline_store_type == "file"

    def test_settings_defaults(self):
        """Test settings defaults."""
        settings = CustomFeatureStoreSettings()

        assert settings.storage_path == "./feature_store"
        assert settings.online_store_type == "memory"
        assert settings.offline_store_type == "file"
        assert settings.enable_compression is False
        assert settings.cache_size == 10000

    def test_sqlite_store_type(self):
        """Test SQLite store type."""
        settings = CustomFeatureStoreSettings(
            online_store_type="sqlite",
            offline_store_type="sqlite",
        )

        assert settings.online_store_type == "sqlite"
        assert settings.offline_store_type == "sqlite"

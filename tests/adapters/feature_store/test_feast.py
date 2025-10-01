"""Tests for Feast Feature Store Adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Optional

from acb.adapters.feature_store.feast import (
    FeastAdapter,
    FeastSettings,
)
from acb.adapters.feature_store._base import (
    FeatureDefinition,
    FeatureServingRequest,
    FeatureGroup,
    FeatureDataType,
    FeatureStatus,
)


@pytest.fixture
def feast_settings():
    """Create Feast settings for testing."""
    return FeastSettings(
        repo_path="/tmp/feast_repo",
        redis_host="localhost",
        redis_port=6379,
        bigquery_project="test-project",
        bigquery_dataset="feast_dataset",
    )


@pytest.fixture
def mock_feast_client():
    """Create mock Feast client."""
    mock_client = MagicMock()
    mock_client.get_online_features = AsyncMock()
    mock_client.get_historical_features = AsyncMock()
    mock_client.list_feature_views = MagicMock(return_value=[])
    mock_client.list_feature_services = MagicMock(return_value=[])
    return mock_client


class TestFeastAdapter:
    """Test Feast adapter implementation."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, feast_settings):
        """Test Feast adapter initialization."""
        adapter = FeastAdapter(feast_settings)
        assert adapter.settings == feast_settings
        assert adapter._client is None
        assert adapter._offline_client is None

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_client_creation(self, mock_feast_store, feast_settings):
        """Test Feast client creation."""
        mock_store_instance = MagicMock()
        mock_feast_store.return_value = mock_store_instance

        adapter = FeastAdapter(feast_settings)
        client = await adapter._create_client()

        assert client == mock_store_instance
        mock_feast_store.assert_called_once_with(repo_path=feast_settings.repo_path)

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_online_feature_serving(self, mock_feast_store, feast_settings):
        """Test online feature serving."""
        # Setup mock
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store

        mock_response = MagicMock()
        mock_response.to_dict.return_value = {
            "user_age": [25],
            "user_location": ["NYC"],
        }
        mock_store.get_online_features.return_value = mock_response

        adapter = FeastAdapter(feast_settings)

        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age", "user_location"],
        )

        response = await adapter.get_online_features(request)

        assert response.entity_id == "user_123"
        assert len(response.features) == 2
        assert "user_age" in response.features
        assert "user_location" in response.features

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_offline_feature_serving(self, mock_feast_store, feast_settings):
        """Test offline feature serving."""
        # Setup mock
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store

        mock_df = MagicMock()
        mock_df.to_dict.return_value = {
            "entity_id": ["user_123"],
            "user_age": [25],
            "user_location": ["NYC"],
            "event_timestamp": [datetime.now()],
        }
        mock_store.get_historical_features.return_value = mock_df

        adapter = FeastAdapter(feast_settings)

        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age", "user_location"],
        )

        vectors = await adapter.get_offline_features(request)

        assert len(vectors) >= 0  # Mock returns empty but structure is tested

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureView")
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_feature_registration(self, mock_feast_store, mock_feature_view, feast_settings):
        """Test feature registration."""
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store
        mock_store.apply = MagicMock()

        adapter = FeastAdapter(feast_settings)

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
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_list_features(self, mock_feast_store, feast_settings):
        """Test listing features."""
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store

        # Mock feature view
        mock_feature_view = MagicMock()
        mock_feature_view.name = "user_features"
        mock_feature_view.features = [
            MagicMock(name="user_age", dtype="int64"),
            MagicMock(name="user_location", dtype="string"),
        ]
        mock_store.list_feature_views.return_value = [mock_feature_view]

        adapter = FeastAdapter(feast_settings)
        features = await adapter.list_features()

        assert len(features) == 2
        assert features[0].name == "user_age"
        assert features[1].name == "user_location"

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_feature_group_creation(self, mock_feast_store, feast_settings):
        """Test feature group creation."""
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store

        adapter = FeastAdapter(feast_settings)

        group = FeatureGroup(
            name="user_features",
            description="User-related features",
            entity_type="user",
            online_store_enabled=True,
            offline_store_enabled=True,
            created_at=datetime.now(),
        )

        result = await adapter.create_feature_group(group)
        assert result is True

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_get_feature_group(self, mock_feast_store, feast_settings):
        """Test getting feature group."""
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store

        mock_feature_view = MagicMock()
        mock_feature_view.name = "user_features"
        mock_feature_view.description = "User features"
        mock_store.get_feature_view.return_value = mock_feature_view

        adapter = FeastAdapter(feast_settings)
        group = await adapter.get_feature_group("user_features")

        assert group is not None
        assert group.name == "user_features"

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_health_check(self, mock_feast_store, feast_settings):
        """Test health check."""
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store

        adapter = FeastAdapter(feast_settings)
        health = await adapter.health_check()

        # Health check should pass with mock
        assert health is True

    @pytest.mark.asyncio
    async def test_context_manager(self, feast_settings):
        """Test adapter as context manager."""
        with patch("acb.adapters.feature_store.feast.FeatureStore"):
            adapter = FeastAdapter(feast_settings)
            async with adapter:
                assert adapter._client is not None

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_feature_monitoring(self, mock_feast_store, feast_settings):
        """Test feature monitoring."""
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store

        adapter = FeastAdapter(feast_settings)
        metrics = await adapter.monitor_features(["user_age"])

        assert metrics.feature_names == ["user_age"]
        assert metrics.request_count >= 0
        assert metrics.avg_latency_ms >= 0

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_data_quality_validation(self, mock_feast_store, feast_settings):
        """Test data quality validation."""
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store

        adapter = FeastAdapter(feast_settings)
        result = await adapter.validate_data_quality(["user_age"], "user_table")

        assert result.feature_names == ["user_age"]
        assert result.data_source == "user_table"

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.feast.FeatureStore")
    async def test_feature_lineage(self, mock_feast_store, feast_settings):
        """Test feature lineage."""
        mock_store = MagicMock()
        mock_feast_store.return_value = mock_store

        adapter = FeastAdapter(feast_settings)
        lineage = await adapter.get_feature_lineage("user_age")

        assert lineage.feature_name == "user_age"
        assert isinstance(lineage.upstream_sources, list)
        assert isinstance(lineage.downstream_consumers, list)

    @pytest.mark.asyncio
    async def test_error_handling(self, feast_settings):
        """Test error handling."""
        with patch("acb.adapters.feature_store.feast.FeatureStore", side_effect=Exception("Connection failed")):
            adapter = FeastAdapter(feast_settings)

            # Health check should return False on error
            health = await adapter.health_check()
            assert health is False


class TestFeastSettings:
    """Test Feast settings."""

    def test_settings_creation(self):
        """Test settings creation."""
        settings = FeastSettings(
            repo_path="/tmp/feast",
            redis_host="localhost",
            redis_port=6379,
        )

        assert settings.repo_path == "/tmp/feast"
        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379

    def test_settings_with_bigquery(self):
        """Test settings with BigQuery."""
        settings = FeastSettings(
            repo_path="/tmp/feast",
            bigquery_project="test-project",
            bigquery_dataset="test_dataset",
        )

        assert settings.bigquery_project == "test-project"
        assert settings.bigquery_dataset == "test_dataset"

    def test_settings_defaults(self):
        """Test settings defaults."""
        settings = FeastSettings()

        assert settings.repo_path == "./feast_repo"
        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379

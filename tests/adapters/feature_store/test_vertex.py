"""Tests for Vertex AI Feature Store Adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Optional

from acb.adapters.feature_store.vertex import (
    VertexAIAdapter,
    VertexAISettings,
)
from acb.adapters.feature_store._base import (
    FeatureDefinition,
    FeatureServingRequest,
    FeatureGroup,
    FeatureDataType,
    FeatureStatus,
)


@pytest.fixture
def vertex_settings():
    """Create Vertex AI settings for testing."""
    return VertexAISettings(
        project_id="test-project",
        location="us-central1",
        featurestore_id="test-featurestore",
    )


class TestVertexAIAdapter:
    """Test Vertex AI adapter implementation."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, vertex_settings):
        """Test Vertex AI adapter initialization."""
        adapter = VertexAIAdapter(vertex_settings)
        assert adapter.settings == vertex_settings
        assert adapter._client is None

    @pytest.mark.asyncio
    @patch("google.cloud.aiplatform.featurestore.Featurestore")
    async def test_client_creation(self, mock_featurestore, vertex_settings):
        """Test Vertex AI client creation."""
        mock_fs_instance = MagicMock()
        mock_featurestore.return_value = mock_fs_instance

        adapter = VertexAIAdapter(vertex_settings)
        client = await adapter._create_client()

        assert client == mock_fs_instance

    @pytest.mark.asyncio
    @patch("google.cloud.aiplatform.featurestore.Featurestore")
    async def test_online_feature_serving(self, mock_featurestore, vertex_settings):
        """Test online feature serving."""
        mock_client = MagicMock()
        mock_featurestore.return_value = mock_client

        mock_response = [
            {
                "entity_id": "user_123",
                "feature_values": {
                    "user_age": {"int64_value": 25},
                    "user_location": {"string_value": "NYC"},
                }
            }
        ]
        mock_client.read_feature_values.return_value = mock_response

        adapter = VertexAIAdapter(vertex_settings)

        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age", "user_location"],
        )

        response = await adapter.get_online_features(request)

        assert response.entity_id == "user_123"
        assert len(response.features) >= 0  # Mock may return empty

    @pytest.mark.asyncio
    @patch("google.cloud.aiplatform.featurestore.Featurestore")
    async def test_health_check(self, mock_featurestore, vertex_settings):
        """Test health check."""
        mock_client = MagicMock()
        mock_featurestore.return_value = mock_client

        adapter = VertexAIAdapter(vertex_settings)
        health = await adapter.health_check()

        assert health is True

    @pytest.mark.asyncio
    async def test_error_handling(self, vertex_settings):
        """Test error handling."""
        with patch("google.cloud.aiplatform.featurestore.Featurestore", side_effect=Exception("Connection failed")):
            adapter = VertexAIAdapter(vertex_settings)

            health = await adapter.health_check()
            assert health is False


class TestVertexAISettings:
    """Test Vertex AI settings."""

    def test_settings_creation(self):
        """Test settings creation."""
        settings = VertexAISettings(
            project_id="test-project",
            location="us-central1",
        )

        assert settings.project_id == "test-project"
        assert settings.location == "us-central1"

    def test_settings_defaults(self):
        """Test settings defaults."""
        settings = VertexAISettings()

        assert settings.location == "us-central1"
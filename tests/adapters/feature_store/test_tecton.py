"""Tests for Tecton Feature Store Adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Optional

from acb.adapters.feature_store.tecton import (
    TectonAdapter,
    TectonSettings,
)
from acb.adapters.feature_store._base import (
    FeatureDefinition,
    FeatureServingRequest,
    FeatureGroup,
    FeatureDataType,
    FeatureStatus,
)


@pytest.fixture
def tecton_settings():
    """Create Tecton settings for testing."""
    return TectonSettings(
        api_key="test-api-key",
        workspace="test-workspace",
        cluster_endpoint="https://api.tecton.ai",
    )


class TestTectonAdapter:
    """Test Tecton adapter implementation."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, tecton_settings):
        """Test Tecton adapter initialization."""
        adapter = TectonAdapter(tecton_settings)
        assert adapter.settings == tecton_settings
        assert adapter._client is None

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.tecton.TectonClient")
    async def test_client_creation(self, mock_tecton_client, tecton_settings):
        """Test Tecton client creation."""
        mock_client_instance = MagicMock()
        mock_tecton_client.return_value = mock_client_instance

        adapter = TectonAdapter(tecton_settings)
        client = await adapter._create_client()

        assert client == mock_client_instance

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.tecton.TectonClient")
    async def test_online_feature_serving(self, mock_tecton_client, tecton_settings):
        """Test online feature serving."""
        mock_client = MagicMock()
        mock_tecton_client.return_value = mock_client

        mock_response = {
            "features": {
                "user_age": 25,
                "user_location": "NYC",
            }
        }
        mock_client.get_features.return_value = mock_response

        adapter = TectonAdapter(tecton_settings)

        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age", "user_location"],
        )

        response = await adapter.get_online_features(request)

        assert response.entity_id == "user_123"
        assert len(response.features) == 2
        assert "user_age" in response.features

    @pytest.mark.asyncio
    @patch("acb.adapters.feature_store.tecton.TectonClient")
    async def test_health_check(self, mock_tecton_client, tecton_settings):
        """Test health check."""
        mock_client = MagicMock()
        mock_tecton_client.return_value = mock_client

        adapter = TectonAdapter(tecton_settings)
        health = await adapter.health_check()

        assert health is True

    @pytest.mark.asyncio
    async def test_error_handling(self, tecton_settings):
        """Test error handling."""
        with patch("acb.adapters.feature_store.tecton.TectonClient", side_effect=Exception("Connection failed")):
            adapter = TectonAdapter(tecton_settings)

            health = await adapter.health_check()
            assert health is False


class TestTectonSettings:
    """Test Tecton settings."""

    def test_settings_creation(self):
        """Test settings creation."""
        settings = TectonSettings(
            api_key="test-key",
            workspace="test-workspace",
        )

        assert settings.api_key == "test-key"
        assert settings.workspace == "test-workspace"

    def test_settings_defaults(self):
        """Test settings defaults."""
        settings = TectonSettings()

        assert settings.cluster_endpoint == "https://api.tecton.ai"

"""Tests for TensorFlow Serving ML Model Adapter."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import aiohttp

from acb.adapters.mlmodel.tensorflow import TensorFlowServingAdapter, TensorFlowServingSettings
from acb.adapters.mlmodel._base import ModelPredictionRequest, BatchPredictionRequest


@pytest.fixture
def tf_settings():
    """Create TensorFlow Serving settings."""
    return TensorFlowServingSettings(
        host="localhost",
        grpc_port=8500,
        rest_port=8501,
        use_grpc=False,  # Use REST for easier testing
        timeout=30.0,
        enable_metrics=True,
    )


@pytest.fixture
def tf_adapter(tf_settings):
    """Create TensorFlow Serving adapter."""
    return TensorFlowServingAdapter(tf_settings)


class MockAsyncResponse:
    """Mock aiohttp response."""

    def __init__(self, status=200, json_data=None, text_data=""):
        self.status = status
        self._json_data = json_data or {}
        self._text_data = text_data

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data


@pytest.mark.unit
class TestTensorFlowServingSettings:
    """Test TensorFlow Serving settings."""

    def test_default_settings(self):
        """Test default settings."""
        settings = TensorFlowServingSettings()

        assert settings.use_grpc is True
        assert settings.grpc_port == 8500
        assert settings.rest_port == 8501
        assert settings.model_signature_name == "serving_default"

    def test_custom_settings(self):
        """Test custom settings."""
        settings = TensorFlowServingSettings(
            use_grpc=False,
            grpc_port=9000,
            rest_port=9001,
            model_signature_name="custom_signature",
        )

        assert settings.use_grpc is False
        assert settings.grpc_port == 9000
        assert settings.rest_port == 9001
        assert settings.model_signature_name == "custom_signature"


@pytest.mark.unit
class TestTensorFlowServingAdapter:
    """Test TensorFlow Serving adapter."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, tf_settings):
        """Test adapter initialization."""
        adapter = TensorFlowServingAdapter(tf_settings)

        assert adapter.tf_settings == tf_settings
        assert adapter._http_session is None

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_client_creation(self, mock_session_class, tf_adapter):
        """Test client creation."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session

        client = await tf_adapter._create_client()

        assert "http" in client
        assert tf_adapter._http_session is not None

    def test_rest_url_generation(self, tf_adapter):
        """Test REST URL generation."""
        url = tf_adapter._get_rest_url("my_model")
        assert url == "http://localhost:8501/v1/models/my_model:predict"

        url_with_version = tf_adapter._get_rest_url("my_model", "123")
        assert url_with_version == "http://localhost:8501/v1/models/my_model/versions/123:predict"

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_rest_prediction(self, mock_post, tf_adapter):
        """Test REST prediction."""
        # Mock response
        mock_response = MockAsyncResponse(
            status=200,
            json_data={"outputs": {"prediction": [[0.1, 0.9]]}}
        )
        mock_post.return_value.__aenter__.return_value = mock_response

        # Mock client creation
        tf_adapter._http_session = AsyncMock()

        request = ModelPredictionRequest(
            inputs={"input_1": [[1.0, 2.0]]},
            model_name="test_model",
        )

        response = await tf_adapter.predict(request)

        assert response.model_name == "test_model"
        assert response.predictions == {"prediction": [[0.1, 0.9]]}
        assert response.latency_ms > 0

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_rest_prediction_error(self, mock_post, tf_adapter):
        """Test REST prediction error handling."""
        # Mock error response
        mock_response = MockAsyncResponse(
            status=400,
            text_data="Model not found"
        )
        mock_post.return_value.__aenter__.return_value = mock_response

        # Mock client creation
        tf_adapter._http_session = AsyncMock()

        request = ModelPredictionRequest(
            inputs={"input_1": [[1.0, 2.0]]},
            model_name="nonexistent_model",
        )

        with pytest.raises(RuntimeError, match="TensorFlow Serving prediction failed"):
            await tf_adapter.predict(request)

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_batch_prediction(self, mock_post, tf_adapter):
        """Test batch prediction."""
        # Mock response
        mock_response = MockAsyncResponse(
            status=200,
            json_data={"outputs": {"prediction": [[0.1, 0.9], [0.8, 0.2]]}}
        )
        mock_post.return_value.__aenter__.return_value = mock_response

        # Mock client creation
        tf_adapter._http_session = AsyncMock()

        request = BatchPredictionRequest(
            inputs=[
                {"input_1": [1.0, 2.0]},
                {"input_1": [3.0, 4.0]},
            ],
            model_name="test_model",
        )

        response = await tf_adapter.batch_predict(request)

        assert response.model_name == "test_model"
        assert response.batch_size == 2
        assert len(response.predictions) == 2
        assert response.total_latency_ms > 0

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_list_models(self, mock_get, tf_adapter):
        """Test list models."""
        # Mock response
        mock_response = MockAsyncResponse(
            status=200,
            json_data={
                "models": [
                    {
                        "name": "model1",
                        "version_labels": {
                            "1": {"state": "AVAILABLE"},
                            "2": {"state": "LOADING"}
                        }
                    }
                ]
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        # Mock client creation
        tf_adapter._http_session = AsyncMock()

        models = await tf_adapter.list_models()

        assert len(models) == 2
        assert models[0].name == "model1"
        assert models[0].framework == "tensorflow"
        assert models[1].name == "model1"

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_get_model_info(self, mock_get, tf_adapter):
        """Test get model info."""
        # Mock response
        mock_response = MockAsyncResponse(
            status=200,
            json_data={
                "model_version": "1",
                "metadata": {
                    "signature_def": {
                        "inputs": {"input_1": {"dtype": "DT_FLOAT"}},
                        "outputs": {"output_1": {"dtype": "DT_FLOAT"}}
                    }
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        # Mock client creation
        tf_adapter._http_session = AsyncMock()

        info = await tf_adapter.get_model_info("test_model")

        assert info.name == "test_model"
        assert info.framework == "tensorflow"
        assert info.input_schema is not None
        assert info.output_schema is not None

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_get_model_health(self, mock_get, tf_adapter):
        """Test get model health."""
        # Mock response
        mock_response = MockAsyncResponse(
            status=200,
            json_data={
                "model_version_status": [
                    {
                        "state": "AVAILABLE",
                        "status": {"error_code": "OK"}
                    }
                ]
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        # Mock client creation
        tf_adapter._http_session = AsyncMock()

        health = await tf_adapter.get_model_health("test_model")

        assert health.model_name == "test_model"
        assert health.status == "healthy"

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_health_check(self, mock_get, tf_adapter):
        """Test adapter health check."""
        # Mock response
        mock_response = MockAsyncResponse(status=200)
        mock_get.return_value.__aenter__.return_value = mock_response

        # Mock client creation
        tf_adapter._http_session = AsyncMock()

        healthy = await tf_adapter.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_health_check_failure(self, mock_get, tf_adapter):
        """Test adapter health check failure."""
        # Mock error response
        mock_response = MockAsyncResponse(status=500)
        mock_get.return_value.__aenter__.return_value = mock_response

        # Mock client creation
        tf_adapter._http_session = AsyncMock()

        healthy = await tf_adapter.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_cleanup(self, tf_adapter):
        """Test cleanup."""
        # Mock sessions
        tf_adapter._http_session = AsyncMock()
        tf_adapter._grpc_channel = AsyncMock()

        await tf_adapter.cleanup()

        tf_adapter._http_session.close.assert_called_once()
        tf_adapter._grpc_channel.close.assert_called_once()


@pytest.mark.integration
class TestTensorFlowServingIntegration:
    """Integration tests for TensorFlow Serving adapter."""

    @pytest.mark.asyncio
    async def test_full_workflow_rest(self, tf_adapter):
        """Test complete workflow with REST API."""
        # Mock all HTTP calls
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock list models
            mock_session.get.return_value.__aenter__.return_value = MockAsyncResponse(
                status=200,
                json_data={"models": [{"name": "test_model", "version_labels": {"1": {"state": "AVAILABLE"}}}]}
            )

            # Mock prediction
            mock_session.post.return_value.__aenter__.return_value = MockAsyncResponse(
                status=200,
                json_data={"outputs": {"prediction": [[0.9, 0.1]]}}
            )

            async with tf_adapter as adapter:
                # List models
                models = await adapter.list_models()
                assert len(models) > 0

                # Prediction
                request = ModelPredictionRequest(
                    inputs={"input_1": [[1.0, 2.0]]},
                    model_name="test_model",
                )
                response = await adapter.predict(request)
                assert response.model_name == "test_model"

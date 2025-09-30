"""Tests for TorchServe ML Model Adapter."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import aiohttp

from acb.adapters.mlmodel.torchserve import TorchServeAdapter, TorchServeSettings
from acb.adapters.mlmodel._base import ModelPredictionRequest, BatchPredictionRequest


@pytest.fixture
def torchserve_settings():
    """Create TorchServe settings."""
    return TorchServeSettings(
        host="localhost",
        inference_port=8080,
        management_port=8081,
        metrics_port=8082,
        timeout=30.0,
        enable_metrics=True,
    )


@pytest.fixture
def torchserve_adapter(torchserve_settings):
    """Create TorchServe adapter."""
    return TorchServeAdapter(torchserve_settings)


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
class TestTorchServeSettings:
    """Test TorchServe settings."""

    def test_default_settings(self):
        """Test default settings."""
        settings = TorchServeSettings()
        
        assert settings.inference_port == 8080
        assert settings.management_port == 8081
        assert settings.metrics_port == 8082
        assert settings.initial_workers == 1
        assert settings.max_workers == 4

    def test_custom_settings(self):
        """Test custom settings."""
        settings = TorchServeSettings(
            inference_port=9080,
            management_port=9081,
            initial_workers=2,
            max_workers=8,
            enable_auto_scaling=True,
        )
        
        assert settings.inference_port == 9080
        assert settings.management_port == 9081
        assert settings.initial_workers == 2
        assert settings.max_workers == 8
        assert settings.enable_auto_scaling is True


@pytest.mark.unit
class TestTorchServeAdapter:
    """Test TorchServe adapter."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, torchserve_settings):
        """Test adapter initialization."""
        adapter = TorchServeAdapter(torchserve_settings)
        
        assert adapter.ts_settings == torchserve_settings
        assert adapter._inference_session is None
        assert adapter._management_session is None

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_client_creation(self, mock_session_class, torchserve_adapter):
        """Test client creation."""
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session
        
        client = await torchserve_adapter._create_client()
        
        assert "inference" in client
        assert "management" in client
        assert "metrics" in client

    def test_url_generation(self, torchserve_adapter):
        """Test URL generation."""
        inference_url = torchserve_adapter._get_inference_url("my_model")
        assert inference_url == "http://localhost:8080/predictions/my_model"
        
        inference_url_versioned = torchserve_adapter._get_inference_url("my_model", "1.0")
        assert inference_url_versioned == "http://localhost:8080/predictions/my_model/1.0"
        
        management_url = torchserve_adapter._get_management_url("/models")
        assert management_url == "http://localhost:8081/models"

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_prediction(self, mock_post, torchserve_adapter):
        """Test prediction."""
        # Mock response
        mock_response = MockAsyncResponse(
            status=200,
            json_data={"prediction": [0.1, 0.9]}
        )
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Mock client creation
        torchserve_adapter._inference_session = AsyncMock()
        
        request = ModelPredictionRequest(
            inputs={"data": [[1.0, 2.0]]},
            model_name="test_model",
        )
        
        response = await torchserve_adapter.predict(request)
        
        assert response.model_name == "test_model"
        assert response.predictions["prediction"] == [0.1, 0.9]
        assert response.latency_ms > 0

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_prediction_error(self, mock_post, torchserve_adapter):
        """Test prediction error handling."""
        # Mock error response
        mock_response = MockAsyncResponse(
            status=404,
            text_data="Model not found"
        )
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Mock client creation
        torchserve_adapter._inference_session = AsyncMock()
        
        request = ModelPredictionRequest(
            inputs={"data": [[1.0, 2.0]]},
            model_name="nonexistent_model",
        )
        
        with pytest.raises(RuntimeError, match="TorchServe prediction failed"):
            await torchserve_adapter.predict(request)

    @pytest.mark.asyncio
    async def test_batch_prediction(self, torchserve_adapter):
        """Test batch prediction."""
        # Mock individual predictions since TorchServe processes them individually
        async def mock_predict(request):
            return type('MockResponse', (), {
                'predictions': {"class": "positive"},
                'model_name': request.model_name,
                'model_version': request.model_version or "1.0",
                'latency_ms': 10.0,
                'metadata': request.metadata,
            })()
        
        torchserve_adapter.predict = mock_predict
        
        request = BatchPredictionRequest(
            inputs=[
                {"data": [1.0, 2.0]},
                {"data": [3.0, 4.0]},
            ],
            model_name="test_model",
        )
        
        response = await torchserve_adapter.batch_predict(request)
        
        assert response.model_name == "test_model"
        assert response.batch_size == 2
        assert len(response.predictions) == 2

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_list_models(self, mock_get, torchserve_adapter):
        """Test list models."""
        # Mock management API responses
        mock_get.side_effect = [
            # First call - list models
            MockAsyncResponse(
                status=200,
                json_data={
                    "models": [
                        {"modelName": "model1", "modelUrl": "s3://bucket/model1.mar"}
                    ]
                }
            ).__aenter__(),
            # Second call - model details
            MockAsyncResponse(
                status=200,
                json_data=[
                    {
                        "modelName": "model1",
                        "modelVersion": "1.0",
                        "modelUrl": "s3://bucket/model1.mar",
                        "status": "Ready",
                        "workerId": "worker-1",
                        "gpu": 0,
                        "memoryUsage": 1024,
                    }
                ]
            ).__aenter__(),
        ]
        
        # Mock client creation
        torchserve_adapter._management_session = AsyncMock()
        
        models = await torchserve_adapter.list_models()
        
        assert len(models) == 1
        assert models[0].name == "model1"
        assert models[0].framework == "pytorch"
        assert models[0].status == "ready"

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_get_model_info(self, mock_get, torchserve_adapter):
        """Test get model info."""
        # Mock response
        mock_response = MockAsyncResponse(
            status=200,
            json_data=[
                {
                    "modelName": "test_model",
                    "modelVersion": "1.0",
                    "status": "Ready",
                    "workerId": "worker-1",
                    "gpu": 0,
                    "memoryUsage": 2048,
                    "loadTime": 5000,
                }
            ]
        )
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Mock client creation
        torchserve_adapter._management_session = AsyncMock()
        
        info = await torchserve_adapter.get_model_info("test_model")
        
        assert info.name == "test_model"
        assert info.version == "1.0"
        assert info.framework == "pytorch"
        assert info.status == "ready"

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_get_model_health(self, mock_get, torchserve_adapter):
        """Test get model health."""
        # Mock metrics and model info responses
        mock_get.side_effect = [
            # Metrics call
            MockAsyncResponse(
                status=200,
                text_data='inference_latency{model_name="test_model",quantile="0.95"} 0.015\n'
            ).__aenter__(),
        ]
        
        # Mock get_model_info
        async def mock_get_model_info(model_name, version=None):
            return type('MockInfo', (), {
                'name': model_name,
                'version': version or "1.0",
                'status': "ready",
                'metadata': {"worker_id": "worker-1", "gpu": 0, "memory_usage": 1024},
            })()
        
        torchserve_adapter.get_model_info = mock_get_model_info
        torchserve_adapter._metrics_session = AsyncMock()
        
        health = await torchserve_adapter.get_model_health("test_model")
        
        assert health.model_name == "test_model"
        assert health.status == "healthy"

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_load_model(self, mock_post, torchserve_adapter):
        """Test load model."""
        # Mock response
        mock_response = MockAsyncResponse(status=200)
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Mock client creation
        torchserve_adapter._management_session = AsyncMock()
        
        success = await torchserve_adapter.load_model("test_model", "/path/to/model.mar")
        
        assert success is True
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.delete')
    async def test_unload_model(self, mock_delete, torchserve_adapter):
        """Test unload model."""
        # Mock response
        mock_response = MockAsyncResponse(status=200)
        mock_delete.return_value.__aenter__.return_value = mock_response
        
        # Mock client creation
        torchserve_adapter._management_session = AsyncMock()
        
        success = await torchserve_adapter.unload_model("test_model")
        
        assert success is True
        mock_delete.assert_called_once()

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.put')
    async def test_scale_model(self, mock_put, torchserve_adapter):
        """Test scale model."""
        # Mock response
        mock_response = MockAsyncResponse(status=200)
        mock_put.return_value.__aenter__.return_value = mock_response
        
        # Mock client creation
        torchserve_adapter._management_session = AsyncMock()
        
        success = await torchserve_adapter.scale_model("test_model", 3)
        
        assert success is True
        mock_put.assert_called_once()

    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_health_check(self, mock_get, torchserve_adapter):
        """Test adapter health check."""
        # Mock responses
        mock_get.side_effect = [
            # Ping endpoint
            MockAsyncResponse(status=200).__aenter__(),
            # Management endpoint
            MockAsyncResponse(status=200).__aenter__(),
        ]
        
        # Mock client creation
        torchserve_adapter._inference_session = AsyncMock()
        torchserve_adapter._management_session = AsyncMock()
        
        healthy = await torchserve_adapter.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_cleanup(self, torchserve_adapter):
        """Test cleanup."""
        # Mock sessions
        torchserve_adapter._inference_session = AsyncMock()
        torchserve_adapter._management_session = AsyncMock()
        torchserve_adapter._metrics_session = AsyncMock()
        
        await torchserve_adapter.cleanup()
        
        torchserve_adapter._inference_session.close.assert_called_once()
        torchserve_adapter._management_session.close.assert_called_once()
        torchserve_adapter._metrics_session.close.assert_called_once()


@pytest.mark.integration
class TestTorchServeIntegration:
    """Integration tests for TorchServe adapter."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, torchserve_adapter):
        """Test complete workflow."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            # Mock various API calls
            mock_session.get.side_effect = [
                # List models
                MockAsyncResponse(
                    status=200,
                    json_data={"models": [{"modelName": "test_model", "modelUrl": "s3://bucket/model.mar"}]}
                ).__aenter__(),
                # Model details
                MockAsyncResponse(
                    status=200,
                    json_data=[{"modelName": "test_model", "status": "Ready", "workerId": "worker-1"}]
                ).__aenter__(),
            ]
            
            # Mock prediction
            mock_session.post.return_value.__aenter__.return_value = MockAsyncResponse(
                status=200,
                json_data={"prediction": [0.9, 0.1]}
            )
            
            async with torchserve_adapter as adapter:
                # List models
                models = await adapter.list_models()
                assert len(models) > 0
                
                # Prediction
                request = ModelPredictionRequest(
                    inputs={"data": [[1.0, 2.0]]},
                    model_name="test_model",
                )
                response = await adapter.predict(request)
                assert response.model_name == "test_model"
"""Tests for ML Model Base Adapter."""

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pandas as pd

from acb.adapters.mlmodel._base import (
    BaseMLModelAdapter,
    MLModelSettings,
    ModelPredictionRequest,
    ModelPredictionResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    ModelInfo,
    ModelHealth,
)


class MockMLModelAdapter(BaseMLModelAdapter):
    """Mock ML model adapter for testing."""

    def __init__(self, settings: Optional[MLModelSettings] = None) -> None:
        super().__init__(settings)
        self._mock_client = None
        self._predictions = {}
        self._models = {}
        self._health_status = {}

    async def _create_client(self) -> Any:
        """Create mock client."""
        self._mock_client = MagicMock()
        return self._mock_client

    async def predict(self, request: ModelPredictionRequest) -> ModelPredictionResponse:
        """Mock prediction."""
        # Simulate prediction logic
        predictions = self._predictions.get(request.model_name, {"output": "mock_prediction"})
        
        return ModelPredictionResponse(
            predictions=predictions,
            model_name=request.model_name,
            model_version=request.model_version or "1.0",
            latency_ms=10.0,
            metadata=request.metadata,
        )

    async def batch_predict(
        self, request: BatchPredictionRequest
    ) -> BatchPredictionResponse:
        """Mock batch prediction."""
        all_predictions = []
        for _ in request.inputs:
            predictions = self._predictions.get(request.model_name, {"output": "mock_prediction"})
            all_predictions.append(predictions)
        
        return BatchPredictionResponse(
            predictions=all_predictions,
            model_name=request.model_name,
            model_version=request.model_version or "1.0",
            batch_size=len(request.inputs),
            total_latency_ms=50.0,
            avg_latency_ms=5.0,
            metadata=request.metadata,
        )

    async def list_models(self) -> List[ModelInfo]:
        """Mock list models."""
        return [
            ModelInfo(
                name=name,
                version="1.0",
                status="ready",
                framework="mock",
                description=f"Mock model {name}",
                metadata={"platform": "mock"},
            )
            for name in self._models.keys()
        ]

    async def get_model_info(self, model_name: str, version: Optional[str] = None) -> ModelInfo:
        """Mock get model info."""
        if model_name not in self._models:
            raise RuntimeError(f"Model {model_name} not found")
        
        return ModelInfo(
            name=model_name,
            version=version or "1.0",
            status="ready",
            framework="mock",
            description=f"Mock model {model_name}",
            metadata={"platform": "mock"},
        )

    async def get_model_health(
        self, model_name: str, version: Optional[str] = None
    ) -> ModelHealth:
        """Mock get model health."""
        status = self._health_status.get(model_name, "healthy")
        
        return ModelHealth(
            model_name=model_name,
            model_version=version or "1.0",
            status=status,
            latency_p95=15.0,
            error_rate=0.01,
            last_check=pd.Timestamp.now().isoformat(),
            metadata={"platform": "mock"},
        )

    def set_mock_prediction(self, model_name: str, predictions: Dict[str, Any]) -> None:
        """Set mock prediction for a model."""
        self._predictions[model_name] = predictions

    def add_mock_model(self, model_name: str) -> None:
        """Add a mock model."""
        self._models[model_name] = {"status": "ready"}

    def set_mock_health(self, model_name: str, status: str) -> None:
        """Set mock health status for a model."""
        self._health_status[model_name] = status


@pytest.fixture
def mock_settings():
    """Create mock ML model settings."""
    return MLModelSettings(
        host="localhost",
        port=8501,
        timeout=30.0,
        enable_metrics=True,
        enable_health_checks=True,
    )


@pytest.fixture
def mock_adapter(mock_settings):
    """Create mock ML model adapter."""
    return MockMLModelAdapter(mock_settings)


@pytest.mark.unit
class TestMLModelSettings:
    """Test ML model settings."""

    def test_default_settings(self):
        """Test default settings."""
        settings = MLModelSettings()
        
        assert settings.host == "localhost"
        assert settings.port == 8501
        assert settings.timeout == 30.0
        assert settings.enable_metrics is True
        assert settings.enable_health_checks is True

    def test_custom_settings(self):
        """Test custom settings."""
        settings = MLModelSettings(
            host="ml-server",
            port=9000,
            timeout=60.0,
            enable_metrics=False,
        )
        
        assert settings.host == "ml-server"
        assert settings.port == 9000
        assert settings.timeout == 60.0
        assert settings.enable_metrics is False


@pytest.mark.unit
class TestModelDataTypes:
    """Test ML model data types."""

    def test_prediction_request(self):
        """Test prediction request creation."""
        request = ModelPredictionRequest(
            inputs={"feature1": [1.0, 2.0], "feature2": [3.0, 4.0]},
            model_name="test_model",
            model_version="1.0",
            timeout=30.0,
            metadata={"source": "test"},
        )
        
        assert request.model_name == "test_model"
        assert request.model_version == "1.0"
        assert request.timeout == 30.0
        assert request.inputs["feature1"] == [1.0, 2.0]
        assert request.metadata["source"] == "test"

    def test_prediction_response(self):
        """Test prediction response creation."""
        response = ModelPredictionResponse(
            predictions={"class": "positive", "score": 0.95},
            model_name="test_model",
            model_version="1.0",
            latency_ms=25.5,
        )
        
        assert response.model_name == "test_model"
        assert response.model_version == "1.0"
        assert response.latency_ms == 25.5
        assert response.predictions["class"] == "positive"
        assert response.predictions["score"] == 0.95

    def test_batch_prediction_request(self):
        """Test batch prediction request creation."""
        request = BatchPredictionRequest(
            inputs=[
                {"feature1": 1.0, "feature2": 2.0},
                {"feature1": 3.0, "feature2": 4.0},
            ],
            model_name="test_model",
            batch_size=2,
        )
        
        assert request.model_name == "test_model"
        assert request.batch_size == 2
        assert len(request.inputs) == 2

    def test_model_info(self):
        """Test model info creation."""
        info = ModelInfo(
            name="test_model",
            version="1.0",
            status="ready",
            framework="tensorflow",
            description="Test model",
            metrics={"accuracy": 0.95},
        )
        
        assert info.name == "test_model"
        assert info.version == "1.0"
        assert info.status == "ready"
        assert info.framework == "tensorflow"
        assert info.metrics["accuracy"] == 0.95

    def test_model_health(self):
        """Test model health creation."""
        health = ModelHealth(
            model_name="test_model",
            model_version="1.0",
            status="healthy",
            latency_p95=15.0,
            error_rate=0.01,
            throughput_qps=100.0,
        )
        
        assert health.model_name == "test_model"
        assert health.status == "healthy"
        assert health.latency_p95 == 15.0
        assert health.error_rate == 0.01
        assert health.throughput_qps == 100.0


@pytest.mark.unit
class TestBaseMLModelAdapter:
    """Test base ML model adapter."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, mock_settings):
        """Test adapter initialization."""
        adapter = MockMLModelAdapter(mock_settings)
        
        assert adapter.settings == mock_settings
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_client_creation(self, mock_adapter):
        """Test client creation."""
        client = await mock_adapter._ensure_client()
        
        assert client is not None
        assert mock_adapter._client is not None

    @pytest.mark.asyncio
    async def test_prediction(self, mock_adapter):
        """Test single prediction."""
        mock_adapter.add_mock_model("test_model")
        mock_adapter.set_mock_prediction("test_model", {"class": "positive", "score": 0.95})
        
        request = ModelPredictionRequest(
            inputs={"feature1": [1.0, 2.0]},
            model_name="test_model",
        )
        
        response = await mock_adapter.predict(request)
        
        assert response.model_name == "test_model"
        assert response.predictions["class"] == "positive"
        assert response.predictions["score"] == 0.95
        assert response.latency_ms > 0

    @pytest.mark.asyncio
    async def test_batch_prediction(self, mock_adapter):
        """Test batch prediction."""
        mock_adapter.add_mock_model("test_model")
        mock_adapter.set_mock_prediction("test_model", {"class": "positive"})
        
        request = BatchPredictionRequest(
            inputs=[
                {"feature1": 1.0},
                {"feature1": 2.0},
            ],
            model_name="test_model",
        )
        
        response = await mock_adapter.batch_predict(request)
        
        assert response.model_name == "test_model"
        assert response.batch_size == 2
        assert len(response.predictions) == 2
        assert response.total_latency_ms > 0

    @pytest.mark.asyncio
    async def test_list_models(self, mock_adapter):
        """Test list models."""
        mock_adapter.add_mock_model("model1")
        mock_adapter.add_mock_model("model2")
        
        models = await mock_adapter.list_models()
        
        assert len(models) == 2
        model_names = [m.name for m in models]
        assert "model1" in model_names
        assert "model2" in model_names

    @pytest.mark.asyncio
    async def test_get_model_info(self, mock_adapter):
        """Test get model info."""
        mock_adapter.add_mock_model("test_model")
        
        info = await mock_adapter.get_model_info("test_model")
        
        assert info.name == "test_model"
        assert info.status == "ready"
        assert info.framework == "mock"

    @pytest.mark.asyncio
    async def test_get_model_info_not_found(self, mock_adapter):
        """Test get model info for non-existent model."""
        with pytest.raises(RuntimeError, match="Model nonexistent not found"):
            await mock_adapter.get_model_info("nonexistent")

    @pytest.mark.asyncio
    async def test_get_model_health(self, mock_adapter):
        """Test get model health."""
        mock_adapter.add_mock_model("test_model")
        mock_adapter.set_mock_health("test_model", "healthy")
        
        health = await mock_adapter.get_model_health("test_model")
        
        assert health.model_name == "test_model"
        assert health.status == "healthy"
        assert health.latency_p95 == 15.0
        assert health.error_rate == 0.01

    @pytest.mark.asyncio
    async def test_health_check(self, mock_adapter):
        """Test adapter health check."""
        # Initialize client first
        await mock_adapter._ensure_client()
        
        healthy = await mock_adapter.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_get_metrics(self, mock_adapter):
        """Test get metrics."""
        metrics = await mock_adapter.get_metrics()
        
        assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_health_monitoring(self, mock_adapter):
        """Test health monitoring."""
        await mock_adapter.start_health_monitoring()
        
        # Wait a bit for monitoring to run
        await asyncio.sleep(0.1)
        
        await mock_adapter.stop_health_monitoring()

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_adapter):
        """Test async context manager."""
        async with mock_adapter as adapter:
            assert adapter is mock_adapter
            # Client should be initialized
            assert adapter._client is not None

    @pytest.mark.asyncio
    async def test_unsupported_operations(self, mock_adapter):
        """Test unsupported operations raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await mock_adapter.load_model("model", "/path/to/model")
        
        with pytest.raises(NotImplementedError):
            await mock_adapter.unload_model("model")
        
        with pytest.raises(NotImplementedError):
            await mock_adapter.scale_model("model", 3)


@pytest.mark.integration
class TestMLModelAdapterIntegration:
    """Integration tests for ML model adapter."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_adapter):
        """Test complete workflow."""
        # Setup
        mock_adapter.add_mock_model("workflow_model")
        mock_adapter.set_mock_prediction("workflow_model", {"result": "success"})
        
        # Initialize
        async with mock_adapter as adapter:
            # List models
            models = await adapter.list_models()
            assert len(models) > 0
            
            # Get model info
            info = await adapter.get_model_info("workflow_model")
            assert info.name == "workflow_model"
            
            # Check health
            health = await adapter.get_model_health("workflow_model")
            assert health.status == "healthy"
            
            # Single prediction
            pred_request = ModelPredictionRequest(
                inputs={"data": [1, 2, 3]},
                model_name="workflow_model",
            )
            pred_response = await adapter.predict(pred_request)
            assert pred_response.predictions["result"] == "success"
            
            # Batch prediction
            batch_request = BatchPredictionRequest(
                inputs=[{"data": [1]}, {"data": [2]}],
                model_name="workflow_model",
            )
            batch_response = await adapter.batch_predict(batch_request)
            assert len(batch_response.predictions) == 2
            
            # Get metrics
            metrics = await adapter.get_metrics()
            assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_adapter):
        """Test error handling."""
        async with mock_adapter as adapter:
            # Test non-existent model
            with pytest.raises(RuntimeError):
                await adapter.get_model_info("nonexistent_model")
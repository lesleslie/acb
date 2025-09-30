"""Tests for MLflow ML model adapter."""

import json
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from httpx import Response

from acb.adapters.mlmodel._base import (
    ModelInfo,
    ModelPredictionRequest,
    ModelPredictionResponse,
)
from acb.adapters.mlmodel.mlflow import MLflowAdapter
from acb.config import Config


class MockMLflowClient:
    """Mock MLflow client for testing."""

    def __init__(self):
        self.models = {}
        self.experiments = {}
        self.runs = {}

    def get_model_version(self, name, version):
        """Mock get model version."""
        model_key = f"{name}:{version}"
        if model_key not in self.models:
            raise Exception(f"Model {name} version {version} not found")
        return Mock(
            name=name,
            version=version,
            status="READY",
            source=f"s3://models/{name}/{version}",
            current_stage="Production",
        )

    def get_latest_versions(self, name, stages=None):
        """Mock get latest versions."""
        versions = [v for k, v in self.models.items() if k.startswith(f"{name}:")]
        if stages:
            versions = [v for v in versions if v.current_stage in stages]
        return versions

    def create_experiment(self, name):
        """Mock create experiment."""
        exp_id = str(len(self.experiments) + 1)
        self.experiments[exp_id] = Mock(experiment_id=exp_id, name=name)
        return exp_id

    def get_experiment_by_name(self, name):
        """Mock get experiment by name."""
        for exp in self.experiments.values():
            if exp.name == name:
                return exp
        return None

    def start_run(self, experiment_id=None, run_name=None):
        """Mock start run."""
        run_id = str(uuid4())
        run = Mock(
            info=Mock(run_id=run_id, experiment_id=experiment_id, run_name=run_name),
            data=Mock(metrics={}, params={}, tags={}),
        )
        self.runs[run_id] = run
        return run

    def log_metric(self, run_id, key, value, step=None):
        """Mock log metric."""
        if run_id in self.runs:
            self.runs[run_id].data.metrics[key] = value

    def log_param(self, run_id, key, value):
        """Mock log param."""
        if run_id in self.runs:
            self.runs[run_id].data.params[key] = value

    def set_tag(self, run_id, key, value):
        """Mock set tag."""
        if run_id in self.runs:
            self.runs[run_id].data.tags[key] = value


class MockMLflowHTTPClient:
    """Mock HTTP client for MLflow serving."""

    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.responses = {}

    async def post(self, url, json=None, headers=None):
        """Mock POST request."""
        if "/invocations" in url:
            # Simulate prediction response
            predictions = [[0.8, 0.2]] * len(json.get("instances", [{}]))
            response_data = {"predictions": predictions}

            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = response_data
            response.text = json.dumps(response_data)
            return response

        raise ValueError(f"Unexpected URL: {url}")

    async def get(self, url, headers=None):
        """Mock GET request."""
        if "/health" in url:
            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = {"status": "healthy"}
            return response

        raise ValueError(f"Unexpected URL: {url}")


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = Mock(spec=Config)
    config.get_settings.return_value = {
        "mlflow_tracking_uri": "http://localhost:5000",
        "mlflow_registry_uri": "http://localhost:5000",
        "mlflow_serving_uri": "http://localhost:5001",
        "default_timeout": 30.0,
        "enable_metrics": True,
        "enable_health_monitoring": True,
    }
    return config


@pytest.fixture
def mock_mlflow_client():
    """Mock MLflow client."""
    return MockMLflowClient()


@pytest.fixture
def mock_http_client():
    """Mock HTTP client."""
    return MockMLflowHTTPClient()


@pytest.fixture
async def adapter(mock_config):
    """Create MLflow adapter for testing."""
    adapter = MLflowAdapter()
    adapter._settings = mock_config.get_settings()
    return adapter


class TestMLflowAdapterUnit:
    """Unit tests for MLflow adapter."""

    async def test_init(self, adapter):
        """Test adapter initialization."""
        assert adapter._client is None
        assert adapter._http_client is None
        assert adapter._settings is not None

    @patch("acb.adapters.mlmodel.mlflow.mlflow.MlflowClient")
    async def test_ensure_client(self, mock_client_class, adapter, mock_mlflow_client):
        """Test client initialization."""
        mock_client_class.return_value = mock_mlflow_client

        client = await adapter._ensure_client()
        assert client is mock_mlflow_client
        assert adapter._client is mock_mlflow_client

        # Second call should return cached client
        client2 = await adapter._ensure_client()
        assert client2 is mock_mlflow_client
        mock_client_class.assert_called_once()

    @patch("acb.adapters.mlmodel.mlflow.httpx.AsyncClient")
    async def test_ensure_http_client(self, mock_http_class, adapter, mock_http_client):
        """Test HTTP client initialization."""
        mock_http_class.return_value = mock_http_client

        client = await adapter._ensure_http_client()
        assert client is mock_http_client
        assert adapter._http_client is mock_http_client

    @patch("acb.adapters.mlmodel.mlflow.mlflow.MlflowClient")
    async def test_get_model_info(self, mock_client_class, adapter, mock_mlflow_client):
        """Test getting model information."""
        mock_client_class.return_value = mock_mlflow_client

        # Add test model
        mock_mlflow_client.models["test-model:1"] = Mock(
            name="test-model",
            version="1",
            status="READY",
            source="s3://models/test-model/1",
            current_stage="Production",
        )

        model_info = await adapter.get_model_info("test-model", "1")

        assert isinstance(model_info, ModelInfo)
        assert model_info.name == "test-model"
        assert model_info.version == "1"
        assert model_info.status == "READY"

    @patch("acb.adapters.mlmodel.mlflow.mlflow.MlflowClient")
    @patch("acb.adapters.mlmodel.mlflow.httpx.AsyncClient")
    async def test_predict(self, mock_http_class, mock_client_class, adapter, mock_mlflow_client, mock_http_client):
        """Test model prediction."""
        mock_client_class.return_value = mock_mlflow_client
        mock_http_class.return_value = mock_http_client

        request = ModelPredictionRequest(
            model_name="test-model",
            model_version="1",
            inputs={"instances": [[1.0, 2.0, 3.0]]},
            parameters={"temperature": 0.8},
        )

        response = await adapter.predict(request)

        assert isinstance(response, ModelPredictionResponse)
        assert "predictions" in response.outputs
        assert response.model_name == "test-model"
        assert response.model_version == "1"

    @patch("acb.adapters.mlmodel.mlflow.mlflow.MlflowClient")
    async def test_list_models(self, mock_client_class, adapter, mock_mlflow_client):
        """Test listing models."""
        mock_client_class.return_value = mock_mlflow_client

        # Add test models
        mock_mlflow_client.models["model1:1"] = Mock(name="model1", version="1")
        mock_mlflow_client.models["model1:2"] = Mock(name="model1", version="2")
        mock_mlflow_client.models["model2:1"] = Mock(name="model2", version="1")

        with patch.object(mock_mlflow_client, "search_registered_models") as mock_search:
            mock_search.return_value = [
                Mock(name="model1", latest_versions=[Mock(version="2")]),
                Mock(name="model2", latest_versions=[Mock(version="1")]),
            ]

            models = await adapter.list_models()

            assert len(models) == 2
            assert all(isinstance(model, ModelInfo) for model in models)

    @patch("acb.adapters.mlmodel.mlflow.mlflow.MlflowClient")
    async def test_create_experiment(self, mock_client_class, adapter, mock_mlflow_client):
        """Test creating experiment."""
        mock_client_class.return_value = mock_mlflow_client

        experiment_id = await adapter.create_experiment("test-experiment")

        assert experiment_id == "1"
        assert "1" in mock_mlflow_client.experiments

    @patch("acb.adapters.mlmodel.mlflow.mlflow.MlflowClient")
    async def test_start_run(self, mock_client_class, adapter, mock_mlflow_client):
        """Test starting run."""
        mock_client_class.return_value = mock_mlflow_client

        # Create experiment first
        exp_id = await adapter.create_experiment("test-experiment")

        run_id = await adapter.start_run(experiment_id=exp_id, run_name="test-run")

        assert run_id in mock_mlflow_client.runs
        assert mock_mlflow_client.runs[run_id].info.experiment_id == exp_id

    @patch("acb.adapters.mlmodel.mlflow.mlflow.MlflowClient")
    async def test_log_metrics(self, mock_client_class, adapter, mock_mlflow_client):
        """Test logging metrics."""
        mock_client_class.return_value = mock_mlflow_client

        # Create run
        exp_id = await adapter.create_experiment("test-experiment")
        run_id = await adapter.start_run(experiment_id=exp_id)

        await adapter.log_metrics(run_id, {"accuracy": 0.95, "loss": 0.05})

        run = mock_mlflow_client.runs[run_id]
        assert run.data.metrics["accuracy"] == 0.95
        assert run.data.metrics["loss"] == 0.05

    @patch("acb.adapters.mlmodel.mlflow.httpx.AsyncClient")
    async def test_health_check(self, mock_http_class, adapter, mock_http_client):
        """Test health check."""
        mock_http_class.return_value = mock_http_client

        is_healthy = await adapter.health_check()

        assert is_healthy is True

    async def test_get_metrics(self, adapter):
        """Test getting metrics."""
        # Simulate some operations
        adapter._metrics["predictions_total"] = 100
        adapter._metrics["prediction_latency_ms"] = 50.0

        metrics = await adapter.get_metrics()

        assert "predictions_total" in metrics
        assert "prediction_latency_ms" in metrics
        assert metrics["predictions_total"] == 100


class TestMLflowAdapterIntegration:
    """Integration tests for MLflow adapter."""

    @patch("acb.adapters.mlmodel.mlflow.mlflow.MlflowClient")
    @patch("acb.adapters.mlmodel.mlflow.httpx.AsyncClient")
    async def test_end_to_end_prediction_workflow(
        self, mock_http_class, mock_client_class, adapter, mock_mlflow_client, mock_http_client
    ):
        """Test complete prediction workflow."""
        mock_client_class.return_value = mock_mlflow_client
        mock_http_class.return_value = mock_http_client

        # Setup model
        mock_mlflow_client.models["classifier:1"] = Mock(
            name="classifier",
            version="1",
            status="READY",
            source="s3://models/classifier/1",
            current_stage="Production",
        )

        # Get model info
        model_info = await adapter.get_model_info("classifier", "1")
        assert model_info.name == "classifier"

        # Make prediction
        request = ModelPredictionRequest(
            model_name="classifier",
            model_version="1",
            inputs={"instances": [[1.0, 2.0, 3.0]]},
        )

        response = await adapter.predict(request)
        assert response.model_name == "classifier"
        assert "predictions" in response.outputs

        # Check health
        is_healthy = await adapter.health_check()
        assert is_healthy is True

    @patch("acb.adapters.mlmodel.mlflow.mlflow.MlflowClient")
    async def test_experiment_tracking_workflow(self, mock_client_class, adapter, mock_mlflow_client):
        """Test experiment tracking workflow."""
        mock_client_class.return_value = mock_mlflow_client

        # Create experiment
        exp_id = await adapter.create_experiment("model-training")
        assert exp_id == "1"

        # Start run
        run_id = await adapter.start_run(experiment_id=exp_id, run_name="baseline")
        assert run_id in mock_mlflow_client.runs

        # Log parameters
        await adapter.log_parameters(run_id, {"learning_rate": 0.01, "batch_size": 32})

        # Log metrics
        await adapter.log_metrics(run_id, {"accuracy": 0.95, "f1_score": 0.93})

        # Verify data was logged
        run = mock_mlflow_client.runs[run_id]
        assert run.data.params["learning_rate"] == 0.01
        assert run.data.metrics["accuracy"] == 0.95

    async def test_error_handling(self, adapter):
        """Test error handling in various scenarios."""
        # Test predict without client
        request = ModelPredictionRequest(
            model_name="nonexistent",
            model_version="1",
            inputs={"instances": [[1.0]]},
        )

        with pytest.raises(Exception):
            await adapter.predict(request)

    async def test_batch_prediction(self, adapter):
        """Test batch prediction capabilities."""
        with patch.object(adapter, "_ensure_http_client") as mock_ensure:
            mock_client = MockMLflowHTTPClient()
            mock_ensure.return_value = mock_client

            request = ModelPredictionRequest(
                model_name="batch-model",
                model_version="1",
                inputs={"instances": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]},
            )

            response = await adapter.predict(request)

            assert len(response.outputs["predictions"]) == 3
            assert response.model_name == "batch-model"
"""Tests for BentoML ML model adapter."""

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
from acb.adapters.mlmodel.bentoml import BentoMLAdapter
from acb.config import Config


class MockBentoMLClient:
    """Mock BentoML client for testing."""

    def __init__(self):
        self.bentos = {}
        self.models = {}
        self.deployments = {}

    def get_bento(self, tag):
        """Mock get bento."""
        if tag not in self.bentos:
            raise Exception(f"Bento {tag} not found")
        return self.bentos[tag]

    def list_bentos(self):
        """Mock list bentos."""
        return list(self.bentos.values())

    def build_bento(self, service, labels=None, description=None):
        """Mock build bento."""
        tag = f"test_service:{len(self.bentos) + 1}"
        bento = Mock(
            tag=tag,
            service=service,
            labels=labels or {},
            creation_time="2024-01-01T00:00:00Z",
            size_bytes=1024 * 1024,
        )
        self.bentos[tag] = bento
        return bento

    def delete_bento(self, tag):
        """Mock delete bento."""
        if tag in self.bentos:
            del self.bentos[tag]

    def import_model(self, name, module, metadata=None):
        """Mock import model."""
        model = Mock(
            tag=f"{name}:latest",
            module=module,
            metadata=metadata or {},
            creation_time="2024-01-01T00:00:00Z",
        )
        self.models[name] = model
        return model

    def list_models(self):
        """Mock list models."""
        return list(self.models.values())


class MockBentoMLHTTPClient:
    """Mock HTTP client for BentoML serving."""

    def __init__(self):
        self.base_url = "http://localhost:3000"
        self.responses = {}

    async def post(self, url, json=None, headers=None, files=None):
        """Mock POST request."""
        if "/predict" in url:
            # Simulate prediction response
            if json:
                inputs = json.get("inputs") or json.get("instances", [])
            else:
                inputs = [{}]  # Default for file uploads

            predictions = [{"class": "A", "probability": 0.8}] * len(inputs)
            response_data = {"predictions": predictions}

            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = response_data
            response.text = json.dumps(response_data)
            return response

        elif "/classify" in url:
            # Image classification endpoint
            response_data = {
                "prediction": "cat",
                "confidence": 0.95,
                "probabilities": {"cat": 0.95, "dog": 0.05}
            }

            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = response_data
            response.text = json.dumps(response_data)
            return response

        raise ValueError(f"Unexpected URL: {url}")

    async def get(self, url, headers=None):
        """Mock GET request."""
        if "/healthz" in url:
            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = {"status": "healthy"}
            return response

        elif "/metrics" in url:
            response = Mock(spec=Response)
            response.status_code = 200
            response.text = """
# HELP bentoml_service_request_total Total service requests
# TYPE bentoml_service_request_total counter
bentoml_service_request_total{service_name="test_service",service_version="1.0.0"} 100
# HELP bentoml_service_request_duration_seconds Service request duration
# TYPE bentoml_service_request_duration_seconds histogram
bentoml_service_request_duration_seconds_sum{service_name="test_service"} 50.0
bentoml_service_request_duration_seconds_count{service_name="test_service"} 100
"""
            return response

        elif "/docs.json" in url:
            # OpenAPI schema
            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = {
                "openapi": "3.0.0",
                "info": {"title": "Test Service", "version": "1.0.0"},
                "paths": {
                    "/predict": {
                        "post": {
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "schema": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
            return response

        raise ValueError(f"Unexpected URL: {url}")


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = Mock(spec=Config)
    config.get_settings.return_value = {
        "bentoml_home": "/tmp/bentoml",
        "bento_store_url": "http://localhost:7000",
        "default_port": 3000,
        "default_timeout": 30.0,
        "enable_metrics": True,
        "enable_health_monitoring": True,
        "containerization": {
            "base_image": "python:3.11-slim",
            "python_packages": ["numpy", "pandas"],
            "system_packages": ["git"]
        },
        "deployment": {
            "cloud_provider": "aws",
            "instance_type": "t3.medium",
            "auto_scaling": True
        }
    }
    return config


@pytest.fixture
def mock_bentoml_client():
    """Mock BentoML client."""
    return MockBentoMLClient()


@pytest.fixture
def mock_http_client():
    """Mock HTTP client."""
    return MockBentoMLHTTPClient()


@pytest.fixture
async def adapter(mock_config):
    """Create BentoML adapter for testing."""
    adapter = BentoMLAdapter()
    adapter._settings = mock_config.get_settings()
    return adapter


class TestBentoMLAdapterUnit:
    """Unit tests for BentoML adapter."""

    async def test_init(self, adapter):
        """Test adapter initialization."""
        assert adapter._client is None
        assert adapter._http_client is None
        assert adapter._settings is not None

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_ensure_client(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test BentoML client initialization."""
        mock_bentoml.client = mock_bentoml_client

        client = await adapter._ensure_client()
        assert client is mock_bentoml_client
        assert adapter._client is mock_bentoml_client

        # Second call should return cached client
        client2 = await adapter._ensure_client()
        assert client2 is mock_bentoml_client

    @patch("acb.adapters.mlmodel.bentoml.httpx.AsyncClient")
    async def test_ensure_http_client(self, mock_http_class, adapter, mock_http_client):
        """Test HTTP client initialization."""
        mock_http_class.return_value = mock_http_client

        client = await adapter._ensure_http_client()
        assert client is mock_http_client
        assert adapter._http_client is mock_http_client

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_build_service(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test building BentoML service."""
        mock_bentoml.client = mock_bentoml_client

        service_code = '''
import bentoml
from bentoml.io import JSON

@bentoml.service
class TestService:
    @bentoml.api
    def predict(self, input_data: JSON) -> JSON:
        return {"prediction": "test"}
'''

        bento = await adapter.build_service(
            service_name="test_service",
            service_code=service_code,
            requirements=["numpy", "pandas"]
        )

        assert bento.tag.startswith("test_service:")
        assert "test_service:1" in mock_bentoml_client.bentos

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_get_model_info(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test getting model information."""
        mock_bentoml.client = mock_bentoml_client

        # Build a service first
        await adapter.build_service("test_service", "mock_code")

        model_info = await adapter.get_model_info("test_service:1")

        assert isinstance(model_info, ModelInfo)
        assert model_info.name == "test_service:1"

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    @patch("acb.adapters.mlmodel.bentoml.httpx.AsyncClient")
    async def test_predict(self, mock_http_class, mock_bentoml, adapter, mock_bentoml_client, mock_http_client):
        """Test model prediction."""
        mock_bentoml.client = mock_bentoml_client
        mock_http_class.return_value = mock_http_client

        request = ModelPredictionRequest(
            model_name="test_service",
            inputs={"inputs": [{"feature1": 1.0, "feature2": 2.0}]},
            endpoint="predict"
        )

        response = await adapter.predict(request)

        assert isinstance(response, ModelPredictionResponse)
        assert "predictions" in response.outputs
        assert response.model_name == "test_service"

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_list_models(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test listing models."""
        mock_bentoml.client = mock_bentoml_client

        # Build some services
        await adapter.build_service("service1", "code1")
        await adapter.build_service("service2", "code2")

        models = await adapter.list_models()

        assert len(models) == 2
        assert all(isinstance(model, ModelInfo) for model in models)

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_import_model(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test importing model."""
        mock_bentoml.client = mock_bentoml_client

        model_info = await adapter.import_model(
            model_name="sklearn_model",
            model_path="/path/to/model.pkl",
            framework="sklearn"
        )

        assert isinstance(model_info, ModelInfo)
        assert "sklearn_model" in mock_bentoml_client.models

    @patch("acb.adapters.mlmodel.bentoml.httpx.AsyncClient")
    async def test_generate_api_client(self, mock_http_class, adapter, mock_http_client):
        """Test API client generation."""
        mock_http_class.return_value = mock_http_client

        api_spec = await adapter.generate_api_client("test_service")

        assert "openapi" in api_spec
        assert "paths" in api_spec
        assert "/predict" in api_spec["paths"]

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_containerize_service(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test service containerization."""
        mock_bentoml.client = mock_bentoml_client

        # Build service first
        await adapter.build_service("container_service", "code")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Build successful")

            result = await adapter.containerize_service(
                service_tag="container_service:1",
                image_tag="my-service:latest"
            )

            assert result["status"] == "containerized"
            assert result["image_tag"] == "my-service:latest"

    @patch("acb.adapters.mlmodel.bentoml.httpx.AsyncClient")
    async def test_health_check(self, mock_http_class, adapter, mock_http_client):
        """Test health check."""
        mock_http_class.return_value = mock_http_client

        is_healthy = await adapter.health_check()

        assert is_healthy is True

    @patch("acb.adapters.mlmodel.bentoml.httpx.AsyncClient")
    async def test_get_metrics(self, mock_http_class, adapter, mock_http_client):
        """Test getting metrics from Prometheus endpoint."""
        mock_http_class.return_value = mock_http_client

        metrics = await adapter.get_metrics()

        assert "service_requests_total" in metrics
        assert "service_request_duration_avg" in metrics


class TestBentoMLAdapterIntegration:
    """Integration tests for BentoML adapter."""

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    @patch("acb.adapters.mlmodel.bentoml.httpx.AsyncClient")
    async def test_end_to_end_service_workflow(
        self, mock_http_class, mock_bentoml, adapter, mock_bentoml_client, mock_http_client
    ):
        """Test complete service development workflow."""
        mock_bentoml.client = mock_bentoml_client
        mock_http_class.return_value = mock_http_client

        # Build service
        service_code = '''
import bentoml
from bentoml.io import JSON

@bentoml.service
class ClassifierService:
    @bentoml.api
    def predict(self, input_data: JSON) -> JSON:
        return {"prediction": "positive", "confidence": 0.95}
'''

        bento = await adapter.build_service(
            service_name="classifier",
            service_code=service_code,
            requirements=["scikit-learn", "numpy"]
        )
        assert bento.tag.startswith("classifier:")

        # Get service info
        model_info = await adapter.get_model_info(bento.tag)
        assert model_info.name == bento.tag

        # Make prediction
        request = ModelPredictionRequest(
            model_name="classifier",
            inputs={"inputs": [{"text": "This is great!"}]},
            endpoint="predict"
        )

        response = await adapter.predict(request)
        assert response.model_name == "classifier"
        assert "predictions" in response.outputs

        # Generate API documentation
        api_spec = await adapter.generate_api_client("classifier")
        assert "openapi" in api_spec

        # Check health
        is_healthy = await adapter.health_check()
        assert is_healthy is True

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_model_import_workflow(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test model import and versioning workflow."""
        mock_bentoml.client = mock_bentoml_client

        # Import different model types
        sklearn_model = await adapter.import_model(
            model_name="iris_classifier",
            model_path="/models/iris.pkl",
            framework="sklearn",
            metadata={"accuracy": 0.95, "dataset": "iris"}
        )

        pytorch_model = await adapter.import_model(
            model_name="sentiment_analyzer",
            model_path="/models/sentiment.pth",
            framework="pytorch",
            metadata={"f1_score": 0.88}
        )

        # List all models
        models = await adapter.list_models()
        assert len(models) >= 2

        # Verify model metadata
        assert "iris_classifier" in mock_bentoml_client.models
        assert "sentiment_analyzer" in mock_bentoml_client.models

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    @patch("acb.adapters.mlmodel.bentoml.httpx.AsyncClient")
    async def test_image_prediction_workflow(
        self, mock_http_class, mock_bentoml, adapter, mock_bentoml_client, mock_http_client
    ):
        """Test image prediction with file upload."""
        mock_bentoml.client = mock_bentoml_client
        mock_http_class.return_value = mock_http_client

        # Build image classification service
        await adapter.build_service("image_classifier", "image_service_code")

        # Test image prediction
        request = ModelPredictionRequest(
            model_name="image_classifier",
            inputs={"image_file": "base64_encoded_image_data"},
            endpoint="classify",
            input_type="image"
        )

        response = await adapter.predict(request)
        assert response.model_name == "image_classifier"
        assert "prediction" in response.outputs

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_service_deployment_workflow(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test service deployment to cloud."""
        mock_bentoml.client = mock_bentoml_client

        # Build service
        await adapter.build_service("production_service", "service_code")

        # Deploy to cloud
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Deployment successful")

            deployment = await adapter.deploy_to_cloud(
                service_tag="production_service:1",
                cloud_provider="aws",
                instance_type="t3.medium",
                auto_scaling=True
            )

            assert deployment["status"] == "deployed"
            assert deployment["cloud_provider"] == "aws"

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_batch_prediction_workflow(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test batch prediction capabilities."""
        mock_bentoml.client = mock_bentoml_client

        # Build batch processing service
        await adapter.build_service("batch_processor", "batch_service_code")

        with patch.object(adapter, "_ensure_http_client") as mock_ensure:
            mock_client = MockBentoMLHTTPClient()
            mock_ensure.return_value = mock_client

            # Test batch prediction
            request = ModelPredictionRequest(
                model_name="batch_processor",
                inputs={
                    "instances": [
                        {"features": [1.0, 2.0, 3.0]},
                        {"features": [4.0, 5.0, 6.0]},
                        {"features": [7.0, 8.0, 9.0]}
                    ]
                },
                endpoint="predict"
            )

            response = await adapter.predict(request)
            assert len(response.outputs["predictions"]) == 3

    async def test_error_handling(self, adapter):
        """Test error handling in various scenarios."""
        # Test predict without service
        request = ModelPredictionRequest(
            model_name="nonexistent",
            inputs={"data": [1.0]},
        )

        with pytest.raises(Exception):
            await adapter.predict(request)

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_service_versioning(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test service versioning capabilities."""
        mock_bentoml.client = mock_bentoml_client

        # Build multiple versions of the same service
        v1_bento = await adapter.build_service("versioned_service", "v1_code")
        v2_bento = await adapter.build_service("versioned_service", "v2_code")

        # Verify both versions exist
        bentos = await adapter.list_services()
        versioned_bentos = [b for b in bentos if "versioned_service" in b.name]
        assert len(versioned_bentos) == 2

        # Test rollback capability
        await adapter.rollback_service("versioned_service", v1_bento.tag)

    @patch("acb.adapters.mlmodel.bentoml.bentoml")
    async def test_service_deletion(self, mock_bentoml, adapter, mock_bentoml_client):
        """Test service deletion."""
        mock_bentoml.client = mock_bentoml_client

        # Build service
        bento = await adapter.build_service("temp_service", "temp_code")
        assert bento.tag in mock_bentoml_client.bentos

        # Delete service
        result = await adapter.delete_service(bento.tag)
        assert result["status"] == "deleted"
        assert bento.tag not in mock_bentoml_client.bentos
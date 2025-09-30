"""Tests for KServe ML model adapter."""

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
from acb.adapters.mlmodel.kserve import KServeAdapter
from acb.config import Config


class MockKubernetesClient:
    """Mock Kubernetes client for testing."""

    def __init__(self):
        self.inference_services = {}
        self.deployments = {}
        self.services = {}

    def create_namespaced_custom_object(self, group, version, namespace, plural, body):
        """Mock create custom object."""
        name = body["metadata"]["name"]
        self.inference_services[name] = body
        return body

    def get_namespaced_custom_object(self, group, version, namespace, plural, name):
        """Mock get custom object."""
        if name not in self.inference_services:
            raise Exception(f"InferenceService {name} not found")
        return self.inference_services[name]

    def list_namespaced_custom_object(self, group, version, namespace, plural):
        """Mock list custom objects."""
        return {"items": list(self.inference_services.values())}

    def delete_namespaced_custom_object(self, group, version, namespace, plural, name):
        """Mock delete custom object."""
        if name in self.inference_services:
            del self.inference_services[name]
        return {"status": "Success"}

    def patch_namespaced_custom_object(self, group, version, namespace, plural, name, body):
        """Mock patch custom object."""
        if name in self.inference_services:
            self.inference_services[name].update(body)
        return self.inference_services[name]


class MockKServeHTTPClient:
    """Mock HTTP client for KServe serving."""

    def __init__(self):
        self.base_url = "http://localhost:8080"
        self.responses = {}

    async def post(self, url, json=None, headers=None):
        """Mock POST request."""
        if "/v1/models/" in url and ":predict" in url:
            # Simulate prediction response
            instances = json.get("instances", [])
            predictions = [[0.7, 0.3]] * len(instances)
            response_data = {"predictions": predictions}

            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = response_data
            response.text = json.dumps(response_data)
            return response

        elif "/v2/models/" in url and "/infer" in url:
            # V2 inference protocol
            inputs = json.get("inputs", [])
            outputs = []
            for inp in inputs:
                outputs.append({
                    "name": "output",
                    "shape": inp["shape"],
                    "datatype": "FP32",
                    "data": [0.8, 0.2] * (inp["shape"][0] if inp["shape"] else 1)
                })

            response_data = {"outputs": outputs}
            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = response_data
            response.text = json.dumps(response_data)
            return response

        raise ValueError(f"Unexpected URL: {url}")

    async def get(self, url, headers=None):
        """Mock GET request."""
        if "/v1/models/" in url and "/ready" in url:
            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = {"ready": True}
            return response

        elif "/v2/health/ready" in url:
            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = {"ready": True}
            return response

        elif "/v1/models/" in url and url.endswith("/metadata"):
            model_name = url.split("/")[-2]
            response = Mock(spec=Response)
            response.status_code = 200
            response.json.return_value = {
                "name": model_name,
                "versions": ["1"],
                "platform": "tensorflow_graphdef",
                "inputs": [{"name": "input", "datatype": "FP32", "shape": [-1, 4]}],
                "outputs": [{"name": "output", "datatype": "FP32", "shape": [-1, 2]}]
            }
            return response

        raise ValueError(f"Unexpected URL: {url}")


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = Mock(spec=Config)
    config.get_settings.return_value = {
        "kserve_namespace": "default",
        "kserve_ingress_host": "kserve.example.com",
        "kubernetes_config_file": None,
        "default_timeout": 30.0,
        "enable_metrics": True,
        "enable_health_monitoring": True,
        "auto_scaling": {
            "min_replicas": 1,
            "max_replicas": 10,
            "target_utilization": 70
        },
        "canary_traffic_percent": 10,
    }
    return config


@pytest.fixture
def mock_k8s_client():
    """Mock Kubernetes client."""
    return MockKubernetesClient()


@pytest.fixture
def mock_http_client():
    """Mock HTTP client."""
    return MockKServeHTTPClient()


@pytest.fixture
async def adapter(mock_config):
    """Create KServe adapter for testing."""
    adapter = KServeAdapter()
    adapter._settings = mock_config.get_settings()
    return adapter


class TestKServeAdapterUnit:
    """Unit tests for KServe adapter."""

    async def test_init(self, adapter):
        """Test adapter initialization."""
        assert adapter._client is None
        assert adapter._http_client is None
        assert adapter._settings is not None

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    async def test_ensure_client(self, mock_client_class, adapter, mock_k8s_client):
        """Test Kubernetes client initialization."""
        mock_client_class.return_value = mock_k8s_client

        client = await adapter._ensure_client()
        assert client is mock_k8s_client
        assert adapter._client is mock_k8s_client

        # Second call should return cached client
        client2 = await adapter._ensure_client()
        assert client2 is mock_k8s_client
        mock_client_class.assert_called_once()

    @patch("acb.adapters.mlmodel.kserve.httpx.AsyncClient")
    async def test_ensure_http_client(self, mock_http_class, adapter, mock_http_client):
        """Test HTTP client initialization."""
        mock_http_class.return_value = mock_http_client

        client = await adapter._ensure_http_client()
        assert client is mock_http_client
        assert adapter._http_client is mock_http_client

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    async def test_deploy_model(self, mock_client_class, adapter, mock_k8s_client):
        """Test model deployment."""
        mock_client_class.return_value = mock_k8s_client

        deployment_result = await adapter.deploy_model(
            model_name="test-model",
            model_uri="gs://bucket/model",
            framework="tensorflow",
            runtime_version="2.11.0"
        )

        assert "test-model" in mock_k8s_client.inference_services
        assert deployment_result["name"] == "test-model"
        assert deployment_result["status"] == "deployed"

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    async def test_get_model_info(self, mock_client_class, adapter, mock_k8s_client):
        """Test getting model information."""
        mock_client_class.return_value = mock_k8s_client

        # First deploy a model
        await adapter.deploy_model(
            model_name="test-model",
            model_uri="gs://bucket/model",
            framework="tensorflow"
        )

        model_info = await adapter.get_model_info("test-model")

        assert isinstance(model_info, ModelInfo)
        assert model_info.name == "test-model"
        assert model_info.framework == "tensorflow"

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    @patch("acb.adapters.mlmodel.kserve.httpx.AsyncClient")
    async def test_predict(self, mock_http_class, mock_client_class, adapter, mock_k8s_client, mock_http_client):
        """Test model prediction."""
        mock_client_class.return_value = mock_k8s_client
        mock_http_class.return_value = mock_http_client

        # Deploy model first
        await adapter.deploy_model(
            model_name="test-model",
            model_uri="gs://bucket/model",
            framework="tensorflow"
        )

        request = ModelPredictionRequest(
            model_name="test-model",
            inputs={"instances": [[1.0, 2.0, 3.0, 4.0]]},
        )

        response = await adapter.predict(request)

        assert isinstance(response, ModelPredictionResponse)
        assert "predictions" in response.outputs
        assert response.model_name == "test-model"

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    async def test_list_models(self, mock_client_class, adapter, mock_k8s_client):
        """Test listing models."""
        mock_client_class.return_value = mock_k8s_client

        # Deploy some models
        await adapter.deploy_model("model1", "gs://bucket/model1", "tensorflow")
        await adapter.deploy_model("model2", "gs://bucket/model2", "pytorch")

        models = await adapter.list_models()

        assert len(models) == 2
        assert all(isinstance(model, ModelInfo) for model in models)

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    async def test_update_traffic(self, mock_client_class, adapter, mock_k8s_client):
        """Test traffic splitting."""
        mock_client_class.return_value = mock_k8s_client

        # Deploy model first
        await adapter.deploy_model("test-model", "gs://bucket/model", "tensorflow")

        result = await adapter.update_traffic(
            model_name="test-model",
            traffic_config={"default": 90, "canary": 10}
        )

        assert result["status"] == "updated"
        # Verify traffic configuration was applied
        service = mock_k8s_client.inference_services["test-model"]
        assert "traffic" in service["spec"]

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    async def test_scale_model(self, mock_client_class, adapter, mock_k8s_client):
        """Test model scaling."""
        mock_client_class.return_value = mock_k8s_client

        # Deploy model first
        await adapter.deploy_model("test-model", "gs://bucket/model", "tensorflow")

        result = await adapter.scale_model(
            model_name="test-model",
            min_replicas=2,
            max_replicas=8
        )

        assert result["status"] == "scaled"
        # Verify scaling configuration
        service = mock_k8s_client.inference_services["test-model"]
        scaler = service["spec"]["predictor"]["scaleTarget"]
        assert scaler["minReplicas"] == 2
        assert scaler["maxReplicas"] == 8

    @patch("acb.adapters.mlmodel.kserve.httpx.AsyncClient")
    async def test_health_check(self, mock_http_class, adapter, mock_http_client):
        """Test health check."""
        mock_http_class.return_value = mock_http_client

        is_healthy = await adapter.health_check()

        assert is_healthy is True

    async def test_get_metrics(self, adapter):
        """Test getting metrics."""
        # Simulate some operations
        adapter._metrics["predictions_total"] = 150
        adapter._metrics["deployments_total"] = 5
        adapter._metrics["prediction_latency_ms"] = 25.0

        metrics = await adapter.get_metrics()

        assert "predictions_total" in metrics
        assert "deployments_total" in metrics
        assert "prediction_latency_ms" in metrics


class TestKServeAdapterIntegration:
    """Integration tests for KServe adapter."""

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    @patch("acb.adapters.mlmodel.kserve.httpx.AsyncClient")
    async def test_end_to_end_deployment_workflow(
        self, mock_http_class, mock_client_class, adapter, mock_k8s_client, mock_http_client
    ):
        """Test complete deployment and serving workflow."""
        mock_client_class.return_value = mock_k8s_client
        mock_http_class.return_value = mock_http_client

        # Deploy model
        deployment = await adapter.deploy_model(
            model_name="iris-classifier",
            model_uri="gs://kfserving-examples/models/tensorflow/iris",
            framework="tensorflow",
            runtime_version="2.11.0"
        )
        assert deployment["status"] == "deployed"

        # Get model info
        model_info = await adapter.get_model_info("iris-classifier")
        assert model_info.name == "iris-classifier"

        # Make prediction
        request = ModelPredictionRequest(
            model_name="iris-classifier",
            inputs={"instances": [[6.8, 2.8, 4.8, 1.4]]},
        )

        response = await adapter.predict(request)
        assert response.model_name == "iris-classifier"
        assert "predictions" in response.outputs

        # Check health
        is_healthy = await adapter.health_check()
        assert is_healthy is True

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    async def test_canary_deployment_workflow(self, mock_client_class, adapter, mock_k8s_client):
        """Test canary deployment workflow."""
        mock_client_class.return_value = mock_k8s_client

        # Deploy initial version
        await adapter.deploy_model(
            model_name="production-model",
            model_uri="gs://bucket/model/v1",
            framework="tensorflow"
        )

        # Deploy canary version
        await adapter.deploy_canary(
            model_name="production-model",
            canary_uri="gs://bucket/model/v2",
            traffic_percent=10
        )

        # Verify canary deployment
        service = mock_k8s_client.inference_services["production-model"]
        assert "canary" in service["spec"]

        # Update traffic split
        await adapter.update_traffic(
            model_name="production-model",
            traffic_config={"default": 50, "canary": 50}
        )

        # Promote canary to default
        await adapter.promote_canary("production-model")

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    async def test_auto_scaling_workflow(self, mock_client_class, adapter, mock_k8s_client):
        """Test auto-scaling configuration."""
        mock_client_class.return_value = mock_k8s_client

        # Deploy model with auto-scaling
        await adapter.deploy_model(
            model_name="scalable-model",
            model_uri="gs://bucket/model",
            framework="tensorflow",
            auto_scaling={
                "min_replicas": 1,
                "max_replicas": 20,
                "target_utilization": 80
            }
        )

        # Verify auto-scaling configuration
        service = mock_k8s_client.inference_services["scalable-model"]
        scaler = service["spec"]["predictor"]["scaleTarget"]
        assert scaler["minReplicas"] == 1
        assert scaler["maxReplicas"] == 20

        # Update scaling parameters
        await adapter.scale_model(
            model_name="scalable-model",
            min_replicas=2,
            max_replicas=15
        )

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    @patch("acb.adapters.mlmodel.kserve.httpx.AsyncClient")
    async def test_v2_inference_protocol(
        self, mock_http_class, mock_client_class, adapter, mock_k8s_client, mock_http_client
    ):
        """Test V2 inference protocol."""
        mock_client_class.return_value = mock_k8s_client
        mock_http_class.return_value = mock_http_client

        # Deploy model
        await adapter.deploy_model(
            model_name="v2-model",
            model_uri="gs://bucket/model",
            framework="triton",
            protocol_version="v2"
        )

        # Make V2 prediction
        request = ModelPredictionRequest(
            model_name="v2-model",
            inputs={
                "inputs": [{
                    "name": "input",
                    "shape": [1, 4],
                    "datatype": "FP32",
                    "data": [1.0, 2.0, 3.0, 4.0]
                }]
            },
        )

        response = await adapter.predict(request)
        assert "outputs" in response.outputs
        assert len(response.outputs["outputs"]) > 0

    async def test_error_handling(self, adapter):
        """Test error handling in various scenarios."""
        # Test predict without deployment
        request = ModelPredictionRequest(
            model_name="nonexistent",
            inputs={"instances": [[1.0]]},
        )

        with pytest.raises(Exception):
            await adapter.predict(request)

    @patch("acb.adapters.mlmodel.kserve.kubernetes.client.CustomObjectsApi")
    async def test_model_deletion(self, mock_client_class, adapter, mock_k8s_client):
        """Test model deletion."""
        mock_client_class.return_value = mock_k8s_client

        # Deploy model
        await adapter.deploy_model("temp-model", "gs://bucket/model", "tensorflow")
        assert "temp-model" in mock_k8s_client.inference_services

        # Delete model
        result = await adapter.delete_model("temp-model")
        assert result["status"] == "deleted"
        assert "temp-model" not in mock_k8s_client.inference_services
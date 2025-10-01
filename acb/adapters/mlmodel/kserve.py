"""KServe ML Model Adapter.

This adapter provides integration with KServe for Kubernetes-native
model serving with auto-scaling, canary deployments, and production-grade
features for cloud-native ML deployments.
"""

from __future__ import annotations

import time
from typing import Any

import aiohttp
import pandas as pd
from pydantic import Field
from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    generate_adapter_id,
)
from acb.adapters.mlmodel._base import (
    BaseMLModelAdapter,
    BatchPredictionRequest,
    BatchPredictionResponse,
    MLModelSettings,
    ModelHealth,
    ModelInfo,
    ModelPredictionRequest,
    ModelPredictionResponse,
)

try:
    from kubernetes import client, config

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False


class KServeSettings(MLModelSettings):
    """KServe specific settings."""

    # Kubernetes settings
    namespace: str = Field(default="default", description="Kubernetes namespace")
    kubeconfig_path: str | None = Field(
        default=None,
        description="Path to kubeconfig file",
    )
    in_cluster: bool = Field(
        default=False,
        description="Running inside Kubernetes cluster",
    )

    # KServe settings
    kserve_version: str = Field(default="v1beta1", description="KServe API version")
    inference_service_name: str = Field(
        default="mlmodel-service",
        description="InferenceService name",
    )

    # Model settings
    storage_uri: str | None = Field(
        default=None,
        description="Model storage URI (s3://, gs://, etc.)",
    )
    model_format: str = Field(
        default="tensorflow",
        description="Model format (tensorflow, pytorch, sklearn, etc.)",
    )
    runtime_version: str | None = Field(
        default=None,
        description="Runtime/framework version",
    )
    protocol_version: str = Field(
        default="v1",
        description="Serving protocol version (v1, v2)",
    )

    # Resource settings
    memory_request: str = Field(default="2Gi", description="Memory request")
    memory_limit: str = Field(default="4Gi", description="Memory limit")
    cpu_request: str = Field(default="1", description="CPU request")
    cpu_limit: str = Field(default="2", description="CPU limit")
    gpu_count: int = Field(default=0, description="Number of GPUs")
    gpu_type: str | None = Field(default=None, description="GPU type")

    # Auto-scaling settings
    min_replicas: int = Field(default=1, description="Minimum replicas")
    max_replicas: int = Field(default=5, description="Maximum replicas")
    target_cpu_utilization: int = Field(
        default=70,
        description="Target CPU utilization for auto-scaling",
    )
    scale_to_zero: bool = Field(default=False, description="Enable scale-to-zero")
    scale_to_zero_grace_period: str = Field(
        default="30s",
        description="Scale-to-zero grace period",
    )

    # Canary deployment settings
    enable_canary: bool = Field(default=False, description="Enable canary deployment")
    canary_traffic_percent: int = Field(
        default=10,
        description="Canary traffic percentage",
    )

    # Advanced settings
    enable_logging: bool = Field(default=True, description="Enable request logging")
    log_url: str | None = Field(default=None, description="Custom log URL")
    enable_explainer: bool = Field(default=False, description="Enable model explainer")
    explainer_type: str | None = Field(
        default=None,
        description="Explainer type (lime, shap, etc.)",
    )


class KServeAdapter(BaseMLModelAdapter):
    """KServe adapter for Kubernetes-native model serving.

    This adapter provides comprehensive integration with KServe for cloud-native
    ML model serving with auto-scaling, canary deployments, and production-grade
    features optimized for Kubernetes environments.
    """

    def __init__(self, settings: KServeSettings | None = None) -> None:
        """Initialize KServe adapter.

        Args:
            settings: KServe specific settings
        """
        self._kserve_settings = settings or KServeSettings()
        super().__init__(self._kserve_settings)
        self._k8s_client: client.ApiClient | None = None
        self._custom_api: client.CustomObjectsApi | None = None
        self._core_api: client.CoreV1Api | None = None
        self._http_session: aiohttp.ClientSession | None = None

    @property
    def kserve_settings(self) -> KServeSettings:
        """Get KServe specific settings."""
        return self._kserve_settings

    async def _create_client(self) -> dict[str, Any]:
        """Create Kubernetes and HTTP clients."""
        if not KUBERNETES_AVAILABLE:
            msg = (
                "Kubernetes client not available. Install with: pip install kubernetes"
            )
            raise RuntimeError(
                msg,
            )

        # Load Kubernetes configuration
        if self.kserve_settings.in_cluster:
            config.load_incluster_config()
        else:
            config.load_kube_config(config_file=self.kserve_settings.kubeconfig_path)

        # Create Kubernetes clients
        self._k8s_client = client.ApiClient()
        self._custom_api = client.CustomObjectsApi(self._k8s_client)
        self._core_api = client.CoreV1Api(self._k8s_client)

        # Create HTTP session for inference
        connector = aiohttp.TCPConnector(
            limit=self.kserve_settings.connection_pool_size,
        )
        timeout = aiohttp.ClientTimeout(total=self.kserve_settings.timeout)
        headers = {"Content-Type": "application/json"}
        headers.update(self.kserve_settings.custom_headers)

        self._http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
        )

        return {
            "k8s_client": self._k8s_client,
            "custom_api": self._custom_api,
            "core_api": self._core_api,
            "http_session": self._http_session,
        }

    def _get_inference_url(self, model_name: str, version: str | None = None) -> str:
        """Get inference URL for KServe service."""
        if self.kserve_settings.protocol_version == "v2":
            protocol = "https" if self.kserve_settings.use_tls else "http"
            return f"{protocol}://{self.kserve_settings.host}:{self.kserve_settings.port}/v2/models/{model_name}/infer"
        protocol = "https" if self.kserve_settings.use_tls else "http"
        return f"{protocol}://{self.kserve_settings.host}:{self.kserve_settings.port}/v1/models/{model_name}:predict"

    def _create_inference_service_spec(
        self,
        model_name: str,
        model_path: str,
        version: str | None = None,
    ) -> dict[str, Any]:
        """Create InferenceService specification."""
        service_name = f"{model_name}" if not version else f"{model_name}-{version}"

        # Base specification
        spec = {
            "apiVersion": f"serving.kserve.io/{self.kserve_settings.kserve_version}",
            "kind": "InferenceService",
            "metadata": {
                "name": service_name,
                "namespace": self.kserve_settings.namespace,
            },
            "spec": {
                "predictor": {
                    self.kserve_settings.model_format: {
                        "storageUri": model_path,
                        "resources": {
                            "requests": {
                                "memory": self.kserve_settings.memory_request,
                                "cpu": self.kserve_settings.cpu_request,
                            },
                            "limits": {
                                "memory": self.kserve_settings.memory_limit,
                                "cpu": self.kserve_settings.cpu_limit,
                            },
                        },
                    },
                },
            },
        }

        # Add runtime version if specified
        if self.kserve_settings.runtime_version:
            spec["spec"]["predictor"][self.kserve_settings.model_format][
                "runtimeVersion"
            ] = self.kserve_settings.runtime_version

        # Add protocol version
        if self.kserve_settings.protocol_version == "v2":
            spec["spec"]["predictor"][self.kserve_settings.model_format][
                "protocolVersion"
            ] = "v2"

        # Add GPU resources if specified
        if self.kserve_settings.gpu_count > 0:
            gpu_resource = "nvidia.com/gpu"
            if self.kserve_settings.gpu_type:
                gpu_resource = f"nvidia.com/{self.kserve_settings.gpu_type}"

            spec["spec"]["predictor"][self.kserve_settings.model_format]["resources"][
                "limits"
            ][gpu_resource] = str(self.kserve_settings.gpu_count)
            spec["spec"]["predictor"][self.kserve_settings.model_format]["resources"][
                "requests"
            ][gpu_resource] = str(self.kserve_settings.gpu_count)

        # Add auto-scaling configuration
        if self.kserve_settings.max_replicas > 1:
            spec["spec"]["predictor"]["minReplicas"] = self.kserve_settings.min_replicas
            spec["spec"]["predictor"]["maxReplicas"] = self.kserve_settings.max_replicas

            if self.kserve_settings.scale_to_zero:
                spec["spec"]["predictor"]["scaleTarget"] = 0
                spec["spec"]["predictor"]["scaleMetric"] = "concurrency"

        # Add canary configuration if enabled
        if self.kserve_settings.enable_canary:
            spec["spec"]["canaryTrafficPercent"] = (
                self.kserve_settings.canary_traffic_percent
            )

        # Add logging configuration
        if self.kserve_settings.enable_logging and self.kserve_settings.log_url:
            spec["spec"]["predictor"]["logger"] = {
                "url": self.kserve_settings.log_url,
            }

        # Add explainer if enabled
        if (
            self.kserve_settings.enable_explainer
            and self.kserve_settings.explainer_type
        ):
            spec["spec"]["explainer"] = {
                self.kserve_settings.explainer_type: {
                    "storageUri": model_path,
                },
            }

        return spec

    async def predict(self, request: ModelPredictionRequest) -> ModelPredictionResponse:
        """Perform real-time inference using KServe."""
        start_time = time.time()

        try:
            client = await self._ensure_client()
            http_session = client["http_session"]

            url = self._get_inference_url(request.model_name, request.model_version)

            # Format request based on protocol version
            if self.kserve_settings.protocol_version == "v2":
                # KServe v2 protocol format
                payload = {
                    "inputs": [
                        {
                            "name": key,
                            "shape": [1]
                            if not isinstance(value, list)
                            else [len(value)],
                            "datatype": "FP32",  # Default, should be inferred
                            "data": [value] if not isinstance(value, list) else value,
                        }
                        for key, value in request.inputs.items()
                    ],
                }
            else:
                # KServe v1 protocol format (TensorFlow Serving compatible)
                payload = {
                    "instances": [request.inputs]
                    if isinstance(request.inputs, dict)
                    else request.inputs,
                }

            async with http_session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    msg = f"KServe prediction error: {error_text}"
                    raise RuntimeError(msg)

                result = await response.json()

                # Parse response based on protocol version
                if self.kserve_settings.protocol_version == "v2":
                    predictions = {}
                    for output in result.get("outputs", []):
                        predictions[output["name"]] = output["data"]
                else:
                    predictions = result.get("predictions", result)

            latency_ms = (time.time() - start_time) * 1000

            # Update metrics
            self._metrics["predictions_total"] = (
                self._metrics.get("predictions_total", 0) + 1
            )
            self._metrics["avg_latency_ms"] = (
                self._metrics.get("avg_latency_ms", 0) * 0.9 + latency_ms * 0.1
            )

            return ModelPredictionResponse(
                predictions=predictions
                if isinstance(predictions, dict)
                else {"output": predictions},
                model_name=request.model_name,
                model_version=request.model_version or "v1",
                latency_ms=latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["errors_total"] = self._metrics.get("errors_total", 0) + 1
            msg = f"KServe prediction failed: {e}"
            raise RuntimeError(msg)

    async def batch_predict(
        self,
        request: BatchPredictionRequest,
    ) -> BatchPredictionResponse:
        """Perform batch inference using KServe."""
        start_time = time.time()

        try:
            client = await self._ensure_client()
            http_session = client["http_session"]

            url = self._get_inference_url(request.model_name, request.model_version)

            # Format batch request
            if self.kserve_settings.protocol_version == "v2":
                # Combine all inputs into batch format
                combined_inputs = {}
                for key in request.inputs[0]:
                    combined_inputs[key] = [item[key] for item in request.inputs]

                payload = {
                    "inputs": [
                        {
                            "name": key,
                            "shape": [len(values)]
                            + (
                                [1]
                                if not isinstance(values[0], list)
                                else [len(values[0])]
                            ),
                            "datatype": "FP32",
                            "data": values,
                        }
                        for key, values in combined_inputs.items()
                    ],
                }
            else:
                payload = {"instances": request.inputs}

            async with http_session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    msg = f"KServe batch prediction error: {error_text}"
                    raise RuntimeError(msg)

                result = await response.json()

                # Parse batch response
                if self.kserve_settings.protocol_version == "v2":
                    # Convert v2 batch response back to individual predictions
                    all_predictions = []
                    outputs = result.get("outputs", [])
                    if outputs:
                        batch_size = len(request.inputs)
                        for i in range(batch_size):
                            individual_pred = {}
                            for output in outputs:
                                output_data = output["data"]
                                if (
                                    isinstance(output_data, list)
                                    and len(output_data) > i
                                ):
                                    individual_pred[output["name"]] = output_data[i]
                                else:
                                    individual_pred[output["name"]] = output_data
                            all_predictions.append(individual_pred)
                else:
                    predictions_list = result.get("predictions", [])
                    all_predictions = []
                    for pred in predictions_list:
                        if isinstance(pred, dict):
                            all_predictions.append(pred)
                        else:
                            all_predictions.append({"output": pred})

            total_latency_ms = (time.time() - start_time) * 1000
            avg_latency_ms = total_latency_ms / len(request.inputs)

            return BatchPredictionResponse(
                predictions=all_predictions,
                model_name=request.model_name,
                model_version=request.model_version or "v1",
                batch_size=len(request.inputs),
                total_latency_ms=total_latency_ms,
                avg_latency_ms=avg_latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["batch_errors_total"] = (
                self._metrics.get("batch_errors_total", 0) + 1
            )
            msg = f"KServe batch prediction failed: {e}"
            raise RuntimeError(msg)

    async def list_models(self) -> list[ModelInfo]:
        """List InferenceServices from KServe."""
        try:
            client = await self._ensure_client()
            custom_api = client["custom_api"]

            # Get all InferenceServices
            response = custom_api.list_namespaced_custom_object(
                group="serving.kserve.io",
                version=self.kserve_settings.kserve_version,
                namespace=self.kserve_settings.namespace,
                plural="inferenceservices",
            )

            models = []
            for item in response.get("items", []):
                metadata = item.get("metadata", {})
                spec = item.get("spec", {})
                status = item.get("status", {})

                model_name = metadata.get("name", "")
                predictor = spec.get("predictor", {})

                # Determine model framework and version
                framework = "unknown"
                runtime_version = None
                storage_uri = None

                for framework_key in [
                    "tensorflow",
                    "pytorch",
                    "sklearn",
                    "xgboost",
                    "triton",
                ]:
                    if framework_key in predictor:
                        framework = framework_key
                        framework_spec = predictor[framework_key]
                        storage_uri = framework_spec.get("storageUri")
                        runtime_version = framework_spec.get("runtimeVersion")
                        break

                # Get status information
                conditions = status.get("conditions", [])
                ready_condition = next(
                    (c for c in conditions if c.get("type") == "Ready"),
                    {},
                )
                model_status = ready_condition.get("status", "Unknown").lower()

                models.append(
                    ModelInfo(
                        name=model_name,
                        version=runtime_version or "v1",
                        status="ready" if model_status == "true" else "not_ready",
                        framework=framework,
                        description="KServe InferenceService",
                        created_at=metadata.get("creationTimestamp"),
                        metadata={
                            "platform": "kserve",
                            "namespace": self.kserve_settings.namespace,
                            "storage_uri": storage_uri,
                            "protocol_version": spec.get("predictor", {})
                            .get(framework, {})
                            .get("protocolVersion", "v1"),
                            "conditions": conditions,
                            "url": status.get("url"),
                        },
                    ),
                )

            return models

        except Exception as e:
            msg = f"Failed to list KServe models: {e}"
            raise RuntimeError(msg)

    async def get_model_info(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelInfo:
        """Get detailed information about a specific InferenceService."""
        try:
            client = await self._ensure_client()
            custom_api = client["custom_api"]

            service_name = model_name if not version else f"{model_name}-{version}"

            # Get InferenceService
            response = custom_api.get_namespaced_custom_object(
                group="serving.kserve.io",
                version=self.kserve_settings.kserve_version,
                namespace=self.kserve_settings.namespace,
                plural="inferenceservices",
                name=service_name,
            )

            metadata = response.get("metadata", {})
            spec = response.get("spec", {})
            status = response.get("status", {})

            # Extract model information
            predictor = spec.get("predictor", {})
            framework = "unknown"
            runtime_version = None
            storage_uri = None

            for framework_key in [
                "tensorflow",
                "pytorch",
                "sklearn",
                "xgboost",
                "triton",
            ]:
                if framework_key in predictor:
                    framework = framework_key
                    framework_spec = predictor[framework_key]
                    storage_uri = framework_spec.get("storageUri")
                    runtime_version = framework_spec.get("runtimeVersion")
                    break

            # Get status
            conditions = status.get("conditions", [])
            ready_condition = next(
                (c for c in conditions if c.get("type") == "Ready"),
                {},
            )
            model_status = ready_condition.get("status", "Unknown").lower()

            return ModelInfo(
                name=model_name,
                version=version or runtime_version or "v1",
                status="ready" if model_status == "true" else "not_ready",
                framework=framework,
                description=f"KServe {framework} model",
                created_at=metadata.get("creationTimestamp"),
                metadata={
                    "platform": "kserve",
                    "namespace": self.kserve_settings.namespace,
                    "storage_uri": storage_uri,
                    "protocol_version": framework_spec.get("protocolVersion", "v1"),
                    "conditions": conditions,
                    "url": status.get("url"),
                    "resources": predictor.get(framework, {}).get("resources"),
                    "replicas": {
                        "min": spec.get("predictor", {}).get("minReplicas", 1),
                        "max": spec.get("predictor", {}).get("maxReplicas", 1),
                    },
                },
            )

        except Exception as e:
            msg = f"Failed to get KServe model info: {e}"
            raise RuntimeError(msg)

    async def get_model_health(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelHealth:
        """Get health status of a specific InferenceService."""
        try:
            model_info = await self.get_model_info(model_name, version)

            # Parse conditions for detailed health info
            conditions = model_info.metadata.get("conditions", [])

            health_status = "healthy" if model_info.status == "ready" else "unhealthy"

            # Get additional metrics if available
            latency_p95 = self._metrics.get("avg_latency_ms")
            error_rate = self._metrics.get("error_rate", 0.0)

            return ModelHealth(
                model_name=model_name,
                model_version=version or model_info.version,
                status=health_status,
                latency_p95=latency_p95,
                error_rate=error_rate,
                last_check=pd.Timestamp.now().isoformat(),
                metadata={
                    "platform": "kserve",
                    "namespace": self.kserve_settings.namespace,
                    "conditions": conditions,
                    "url": model_info.metadata.get("url"),
                },
            )

        except Exception as e:
            return ModelHealth(
                model_name=model_name,
                model_version=version or "v1",
                status="error",
                last_check=pd.Timestamp.now().isoformat(),
                metadata={"error": str(e)},
            )

    async def load_model(
        self,
        model_name: str,
        model_path: str,
        version: str | None = None,
    ) -> bool:
        """Create and deploy an InferenceService in KServe."""
        try:
            client = await self._ensure_client()
            custom_api = client["custom_api"]

            # Create InferenceService specification
            inference_service = self._create_inference_service_spec(
                model_name,
                model_path,
                version,
            )

            # Create the InferenceService
            custom_api.create_namespaced_custom_object(
                group="serving.kserve.io",
                version=self.kserve_settings.kserve_version,
                namespace=self.kserve_settings.namespace,
                plural="inferenceservices",
                body=inference_service,
            )

            return True

        except Exception as e:
            msg = f"KServe model deployment failed: {e}"
            raise RuntimeError(msg)

    async def unload_model(self, model_name: str, version: str | None = None) -> bool:
        """Delete an InferenceService from KServe."""
        try:
            client = await self._ensure_client()
            custom_api = client["custom_api"]

            service_name = model_name if not version else f"{model_name}-{version}"

            # Delete the InferenceService
            custom_api.delete_namespaced_custom_object(
                group="serving.kserve.io",
                version=self.kserve_settings.kserve_version,
                namespace=self.kserve_settings.namespace,
                plural="inferenceservices",
                name=service_name,
            )

            return True

        except Exception as e:
            msg = f"KServe model unloading failed: {e}"
            raise RuntimeError(msg)

    async def scale_model(
        self,
        model_name: str,
        replicas: int,
        version: str | None = None,
    ) -> bool:
        """Scale an InferenceService in KServe."""
        try:
            client = await self._ensure_client()
            custom_api = client["custom_api"]

            service_name = model_name if not version else f"{model_name}-{version}"

            # Update InferenceService with new replica count
            patch_body = {
                "spec": {
                    "predictor": {
                        "minReplicas": min(replicas, self.kserve_settings.min_replicas),
                        "maxReplicas": max(replicas, self.kserve_settings.max_replicas),
                    },
                },
            }

            custom_api.patch_namespaced_custom_object(
                group="serving.kserve.io",
                version=self.kserve_settings.kserve_version,
                namespace=self.kserve_settings.namespace,
                plural="inferenceservices",
                name=service_name,
                body=patch_body,
            )

            return True

        except Exception as e:
            msg = f"KServe model scaling failed: {e}"
            raise RuntimeError(msg)

    async def health_check(self) -> bool:
        """Perform KServe health check."""
        try:
            client = await self._ensure_client()
            custom_api = client["custom_api"]

            # Check if we can list InferenceServices
            custom_api.list_namespaced_custom_object(
                group="serving.kserve.io",
                version=self.kserve_settings.kserve_version,
                namespace=self.kserve_settings.namespace,
                plural="inferenceservices",
                limit=1,
            )

            return True

        except Exception:
            return False

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await super().cleanup()

        if self._http_session:
            await self._http_session.close()
            self._http_session = None

        if self._k8s_client:
            await self._k8s_client.close()
            self._k8s_client = None


# Create the main adapter class alias for consistency
MLModel = KServeAdapter

# Module metadata for the adapter
MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="KServe ML Model",
    category="mlmodel",
    provider="kserve",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="ACB Framework",
    created_date="2025-01-20",
    last_modified="2025-01-20",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.MODEL_SERVING,
        AdapterCapability.REAL_TIME_INFERENCE,
        AdapterCapability.BATCH_INFERENCE,
        AdapterCapability.MODEL_VERSIONING,
        AdapterCapability.MODEL_MONITORING,
        AdapterCapability.AUTO_SCALING,
        AdapterCapability.CANARY_DEPLOYMENT,
        AdapterCapability.KUBERNETES_NATIVE,
        AdapterCapability.HEALTH_CHECKS,
        AdapterCapability.REST_SERVING,
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.PERFORMANCE_MONITORING,
        AdapterCapability.METRICS,
        AdapterCapability.ARTIFACT_MANAGEMENT,
        AdapterCapability.DEPLOYMENT_TRACKING,
        AdapterCapability.RESOURCE_MANAGEMENT,
    ],
    required_packages=[
        "kserve>=0.10.0",
        "kubernetes>=25.0.0",
        "aiohttp>=3.9.0",
        "pandas>=2.0.0",
    ],
    description="Kubernetes-native KServe adapter for scalable ML model serving with auto-scaling and canary deployments",
    settings_class="KServeSettings",
    config_example={
        "namespace": "default",
        "in_cluster": False,
        "inference_service_name": "mlmodel-service",
        "model_format": "tensorflow",
        "protocol_version": "v1",
        "memory_request": "2Gi",
        "cpu_request": "1",
        "min_replicas": 1,
        "max_replicas": 5,
        "enable_canary": False,
        "enable_metrics": True,
        "enable_health_checks": True,
    },
)

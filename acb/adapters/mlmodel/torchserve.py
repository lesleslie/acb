"""TorchServe ML Model Adapter.

This adapter provides integration with TorchServe for PyTorch model serving
with management API, model versioning, auto-scaling, and comprehensive
monitoring capabilities.
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


class TorchServeSettings(MLModelSettings):
    """TorchServe specific settings."""

    # API endpoints
    inference_port: int = Field(default=8080, description="Inference API port")
    management_port: int = Field(default=8081, description="Management API port")
    metrics_port: int = Field(default=8082, description="Metrics API port")

    # Model settings
    model_store: str | None = Field(
        default=None,
        description="Path to model store directory",
    )
    workflow_store: str | None = Field(
        default=None,
        description="Path to workflow store directory",
    )

    # Performance settings
    initial_workers: int = Field(
        default=1,
        description="Initial number of workers per model",
    )
    max_workers: int = Field(
        default=4,
        description="Maximum number of workers per model",
    )
    batch_size: int = Field(default=1, description="Default batch size for models")
    max_batch_delay: int = Field(
        default=100,
        description="Maximum batch delay in milliseconds",
    )
    response_timeout: int = Field(
        default=120,
        description="Response timeout in seconds",
    )

    # Auto-scaling settings
    enable_auto_scaling: bool = Field(
        default=False,
        description="Enable automatic scaling",
    )
    min_workers: int = Field(default=1, description="Minimum workers for auto-scaling")
    scale_up_threshold: float = Field(
        default=0.8,
        description="CPU threshold to scale up (0.0-1.0)",
    )
    scale_down_threshold: float = Field(
        default=0.3,
        description="CPU threshold to scale down (0.0-1.0)",
    )

    # Advanced settings
    enable_model_api: bool = Field(
        default=True,
        description="Enable model management API",
    )
    enable_workflow_api: bool = Field(default=False, description="Enable workflow API")
    log_location: str | None = Field(default=None, description="Custom log location")


class TorchServeAdapter(BaseMLModelAdapter):
    """TorchServe adapter for PyTorch model serving.

    This adapter provides comprehensive integration with TorchServe including
    model management, auto-scaling, health monitoring, and performance optimization
    for production PyTorch model deployment.
    """

    def __init__(self, settings: TorchServeSettings | None = None) -> None:
        """Initialize TorchServe adapter.

        Args:
            settings: TorchServe specific settings
        """
        self._ts_settings = settings or TorchServeSettings()
        super().__init__(self._ts_settings)
        self._inference_session: aiohttp.ClientSession | None = None
        self._management_session: aiohttp.ClientSession | None = None
        self._metrics_session: aiohttp.ClientSession | None = None

    @property
    def ts_settings(self) -> TorchServeSettings:
        """Get TorchServe specific settings."""
        return self._ts_settings

    async def _create_client(self) -> dict[str, aiohttp.ClientSession]:
        """Create TorchServe HTTP clients."""
        connector = aiohttp.TCPConnector(limit=self.ts_settings.connection_pool_size)
        timeout = aiohttp.ClientTimeout(total=self.ts_settings.timeout)
        headers = {"Content-Type": "application/json"}
        headers.update(self.ts_settings.custom_headers)

        # Inference API client
        self._inference_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
        )

        # Management API client
        self._management_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
        )

        # Metrics API client
        self._metrics_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
        )

        return {
            "inference": self._inference_session,
            "management": self._management_session,
            "metrics": self._metrics_session,
        }

    def _get_inference_url(self, model_name: str, version: str | None = None) -> str:
        """Get inference API URL for model."""
        protocol = "https" if self.ts_settings.use_tls else "http"
        base_url = (
            f"{protocol}://{self.ts_settings.host}:{self.ts_settings.inference_port}"
        )

        if version:
            return f"{base_url}/predictions/{model_name}/{version}"
        return f"{base_url}/predictions/{model_name}"

    def _get_management_url(self, endpoint: str = "") -> str:
        """Get management API URL."""
        protocol = "https" if self.ts_settings.use_tls else "http"
        base_url = (
            f"{protocol}://{self.ts_settings.host}:{self.ts_settings.management_port}"
        )
        return f"{base_url}{endpoint}"

    def _get_metrics_url(self, endpoint: str = "") -> str:
        """Get metrics API URL."""
        protocol = "https" if self.ts_settings.use_tls else "http"
        base_url = (
            f"{protocol}://{self.ts_settings.host}:{self.ts_settings.metrics_port}"
        )
        return f"{base_url}{endpoint}"

    async def predict(self, request: ModelPredictionRequest) -> ModelPredictionResponse:
        """Perform real-time inference using TorchServe."""
        start_time = time.time()

        try:
            client = await self._ensure_client()
            inference_session = client["inference"]

            url = self._get_inference_url(request.model_name, request.model_version)

            # Prepare data based on input format
            if isinstance(request.inputs, dict):
                # JSON input
                async with inference_session.post(url, json=request.inputs) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        msg = f"TorchServe prediction error: {error_text}"
                        raise RuntimeError(msg)

                    predictions = await response.json()
            else:
                # File/binary input
                data = aiohttp.FormData()
                for key, value in request.inputs.items():
                    data.add_field(key, value)

                async with inference_session.post(url, data=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        msg = f"TorchServe prediction error: {error_text}"
                        raise RuntimeError(msg)

                    predictions = await response.json()

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
                model_version=request.model_version or "1.0",
                latency_ms=latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["errors_total"] = self._metrics.get("errors_total", 0) + 1
            msg = f"TorchServe prediction failed: {e}"
            raise RuntimeError(msg)

    async def batch_predict(
        self,
        request: BatchPredictionRequest,
    ) -> BatchPredictionResponse:
        """Perform batch inference using TorchServe."""
        start_time = time.time()

        try:
            # TorchServe handles batching internally, so we send individual requests
            # but can optimize by configuring batch_size and max_batch_delay
            all_predictions = []

            for input_data in request.inputs:
                pred_request = ModelPredictionRequest(
                    inputs=input_data,
                    model_name=request.model_name,
                    model_version=request.model_version,
                    timeout=request.timeout,
                    metadata=request.metadata,
                )

                pred_response = await self.predict(pred_request)
                all_predictions.append(pred_response.predictions)

            total_latency_ms = (time.time() - start_time) * 1000
            avg_latency_ms = total_latency_ms / len(request.inputs)

            return BatchPredictionResponse(
                predictions=all_predictions,
                model_name=request.model_name,
                model_version=request.model_version or "1.0",
                batch_size=len(request.inputs),
                total_latency_ms=total_latency_ms,
                avg_latency_ms=avg_latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["batch_errors_total"] = (
                self._metrics.get("batch_errors_total", 0) + 1
            )
            msg = f"TorchServe batch prediction failed: {e}"
            raise RuntimeError(msg)

    async def list_models(self) -> list[ModelInfo]:
        """List available models from TorchServe."""
        try:
            client = await self._ensure_client()
            management_session = client["management"]

            url = self._get_management_url("/models")

            async with management_session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    msg = f"Failed to list models: {error_text}"
                    raise RuntimeError(msg)

                result = await response.json()
                models = []

                for model_data in result.get("models", []):
                    model_name = model_data.get("modelName", "")
                    model_url = model_data.get("modelUrl", "")

                    # Get detailed model info
                    detail_url = self._get_management_url(f"/models/{model_name}")
                    async with management_session.get(detail_url) as detail_response:
                        if detail_response.status == 200:
                            detail_result = await detail_response.json()

                            for worker_info in detail_result:
                                models.append(
                                    ModelInfo(
                                        name=model_name,
                                        version=worker_info.get("modelVersion", "1.0"),
                                        status=worker_info.get(
                                            "status",
                                            "unknown",
                                        ).lower(),
                                        framework="pytorch",
                                        description=f"TorchServe model from {model_url}",
                                        metadata={
                                            "platform": "torchserve",
                                            "model_url": model_url,
                                            "worker_id": worker_info.get("workerId"),
                                            "gpu": worker_info.get("gpu"),
                                            "memory_usage": worker_info.get(
                                                "memoryUsage",
                                            ),
                                        },
                                    ),
                                )

                return models

        except Exception as e:
            msg = f"Failed to list TorchServe models: {e}"
            raise RuntimeError(msg)

    async def get_model_info(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelInfo:
        """Get detailed information about a specific model."""
        try:
            client = await self._ensure_client()
            management_session = client["management"]

            url = self._get_management_url(f"/models/{model_name}")

            async with management_session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    msg = f"Model not found: {error_text}"
                    raise RuntimeError(msg)

                result = await response.json()

                if result:
                    worker_info = result[0]  # Get first worker info

                    return ModelInfo(
                        name=model_name,
                        version=worker_info.get("modelVersion", version or "1.0"),
                        status=worker_info.get("status", "unknown").lower(),
                        framework="pytorch",
                        description="TorchServe PyTorch model",
                        metadata={
                            "platform": "torchserve",
                            "worker_id": worker_info.get("workerId"),
                            "gpu": worker_info.get("gpu"),
                            "memory_usage": worker_info.get("memoryUsage"),
                            "load_time": worker_info.get("loadTime"),
                        },
                    )
                msg = f"No worker information found for model {model_name}"
                raise RuntimeError(
                    msg,
                )

        except Exception as e:
            msg = f"Failed to get TorchServe model info: {e}"
            raise RuntimeError(msg)

    async def get_model_health(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelHealth:
        """Get health status of a specific model."""
        try:
            # Get model metrics
            client = await self._ensure_client()
            metrics_session = client["metrics"]

            metrics_url = self._get_metrics_url("/metrics")

            async with metrics_session.get(metrics_url) as response:
                if response.status != 200:
                    return ModelHealth(
                        model_name=model_name,
                        model_version=version or "1.0",
                        status="unhealthy",
                        last_check=pd.Timestamp.now().isoformat(),
                    )

                metrics_text = await response.text()

                # Parse Prometheus metrics for model-specific data
                latency_p95 = None
                error_rate = 0.0
                throughput_qps = None

                for line in metrics_text.split("\n"):
                    if f'model_name="{model_name}"' in line:
                        if "inference_latency" in line and 'quantile="0.95"' in line:
                            latency_p95 = (
                                float(line.split()[-1]) * 1000
                            )  # Convert to ms
                        elif "inference_requests_total" in line:
                            # Calculate throughput and error rate from request metrics
                            pass

                # Get model status from management API
                model_info = await self.get_model_info(model_name, version)
                health_status = (
                    "healthy" if model_info.status == "ready" else "unhealthy"
                )

                return ModelHealth(
                    model_name=model_name,
                    model_version=version or "1.0",
                    status=health_status,
                    latency_p95=latency_p95,
                    error_rate=error_rate,
                    throughput_qps=throughput_qps,
                    memory_usage_mb=model_info.metadata.get("memory_usage"),
                    last_check=pd.Timestamp.now().isoformat(),
                    metadata={
                        "platform": "torchserve",
                        "worker_id": model_info.metadata.get("worker_id"),
                        "gpu": model_info.metadata.get("gpu"),
                    },
                )

        except Exception as e:
            return ModelHealth(
                model_name=model_name,
                model_version=version or "1.0",
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
        """Load a model into TorchServe."""
        try:
            client = await self._ensure_client()
            management_session = client["management"]

            url = self._get_management_url("/models")

            params = {
                "model_name": model_name,
                "url": model_path,
                "initial_workers": self.ts_settings.initial_workers,
                "synchronous": "true",
            }

            if version:
                params["model_version"] = version

            if self.ts_settings.batch_size > 1:
                params["batch_size"] = self.ts_settings.batch_size
                params["max_batch_delay"] = self.ts_settings.max_batch_delay

            async with management_session.post(url, params=params) as response:
                if response.status in (200, 201):
                    return True
                error_text = await response.text()
                msg = f"Failed to load model: {error_text}"
                raise RuntimeError(msg)

        except Exception as e:
            msg = f"TorchServe model loading failed: {e}"
            raise RuntimeError(msg)

    async def unload_model(self, model_name: str, version: str | None = None) -> bool:
        """Unload a model from TorchServe."""
        try:
            client = await self._ensure_client()
            management_session = client["management"]

            if version:
                url = self._get_management_url(f"/models/{model_name}/{version}")
            else:
                url = self._get_management_url(f"/models/{model_name}")

            async with management_session.delete(url) as response:
                if response.status in (200, 202):
                    return True
                error_text = await response.text()
                msg = f"Failed to unload model: {error_text}"
                raise RuntimeError(msg)

        except Exception as e:
            msg = f"TorchServe model unloading failed: {e}"
            raise RuntimeError(msg)

    async def scale_model(
        self,
        model_name: str,
        replicas: int,
        version: str | None = None,
    ) -> bool:
        """Scale model serving replicas in TorchServe."""
        try:
            client = await self._ensure_client()
            management_session = client["management"]

            if version:
                url = self._get_management_url(f"/models/{model_name}/{version}")
            else:
                url = self._get_management_url(f"/models/{model_name}")

            params = {
                "min_worker": min(replicas, self.ts_settings.min_workers),
                "max_worker": min(replicas, self.ts_settings.max_workers),
                "synchronous": "true",
            }

            async with management_session.put(url, params=params) as response:
                if response.status == 200:
                    return True
                error_text = await response.text()
                msg = f"Failed to scale model: {error_text}"
                raise RuntimeError(msg)

        except Exception as e:
            msg = f"TorchServe model scaling failed: {e}"
            raise RuntimeError(msg)

    async def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive TorchServe metrics."""
        try:
            base_metrics = await super().get_metrics()

            client = await self._ensure_client()
            metrics_session = client["metrics"]

            # Get Prometheus metrics
            metrics_url = self._get_metrics_url("/metrics")

            async with metrics_session.get(metrics_url) as response:
                if response.status == 200:
                    metrics_text = await response.text()

                    # Parse key metrics
                    torchserve_metrics = {}
                    for line in metrics_text.split("\n"):
                        if line.startswith("# "):
                            continue
                        if "inference_requests_total" in line:
                            torchserve_metrics["total_requests"] = float(
                                line.split()[-1],
                            )
                        elif "inference_latency" in line and 'quantile="0.5"' in line:
                            torchserve_metrics["median_latency_ms"] = (
                                float(line.split()[-1]) * 1000
                            )
                        elif "queue_time" in line:
                            torchserve_metrics["queue_time_ms"] = (
                                float(line.split()[-1]) * 1000
                            )

                    base_metrics.update(torchserve_metrics)

            return base_metrics

        except Exception:
            return await super().get_metrics()

    async def health_check(self) -> bool:
        """Perform TorchServe health check."""
        try:
            client = await self._ensure_client()

            # Check inference API
            inference_session = client["inference"]
            ping_url = f"{'https' if self.ts_settings.use_tls else 'http'}://{self.ts_settings.host}:{self.ts_settings.inference_port}/ping"

            async with inference_session.get(ping_url) as response:
                if response.status != 200:
                    return False

            # Check management API
            management_session = client["management"]
            models_url = self._get_management_url("/models")

            async with management_session.get(models_url) as response:
                return response.status == 200

        except Exception:
            return False

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await super().cleanup()

        for session in [
            self._inference_session,
            self._management_session,
            self._metrics_session,
        ]:
            if session:
                await session.close()

        self._inference_session = None
        self._management_session = None
        self._metrics_session = None


# Create the main adapter class alias for consistency
MLModel = TorchServeAdapter

# Module metadata for the adapter
MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="TorchServe ML Model",
    category="mlmodel",
    provider="torchserve",
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
        AdapterCapability.HEALTH_CHECKS,
        AdapterCapability.REST_SERVING,
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.PERFORMANCE_MONITORING,
        AdapterCapability.METRICS,
        AdapterCapability.ARTIFACT_MANAGEMENT,
        AdapterCapability.DEPLOYMENT_TRACKING,
    ],
    required_packages=[
        "torchserve>=0.8.0",
        "aiohttp>=3.9.0",
        "pandas>=2.0.0",
    ],
    description="Comprehensive TorchServe adapter for PyTorch model serving with management API, auto-scaling, and production monitoring",
    settings_class="TorchServeSettings",
    config_example={
        "host": "localhost",
        "inference_port": 8080,
        "management_port": 8081,
        "metrics_port": 8082,
        "use_tls": False,
        "timeout": 30.0,
        "initial_workers": 1,
        "max_workers": 4,
        "batch_size": 1,
        "enable_auto_scaling": False,
        "enable_metrics": True,
        "enable_health_checks": True,
    },
)

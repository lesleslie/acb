"""BentoML ML Model Adapter.

This adapter provides integration with BentoML for packaging, serving,
and managing ML models with automatic API generation, containerization,
and cloud deployment capabilities.
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
    import bentoml
    from bentoml._internal.configuration import get_global_config

    BENTOML_AVAILABLE = True
except ImportError:
    BENTOML_AVAILABLE = False


class BentoMLSettings(MLModelSettings):
    """BentoML specific settings."""

    # BentoML server settings
    bento_store_uri: str | None = Field(default=None, description="BentoML store URI")
    model_store_uri: str | None = Field(default=None, description="Model store URI")

    # Service settings
    service_name: str | None = Field(default=None, description="BentoML service name")
    bento_tag: str | None = Field(default=None, description="Bento tag (name:version)")
    working_dir: str | None = Field(
        default=None, description="Working directory for service"
    )

    # API settings
    api_endpoint: str = Field(default="/predict", description="Prediction API endpoint")
    batch_endpoint: str = Field(
        default="/batch_predict", description="Batch prediction endpoint"
    )
    metrics_endpoint: str = Field(default="/metrics", description="Metrics endpoint")
    docs_endpoint: str = Field(
        default="/docs", description="API documentation endpoint"
    )

    # Runtime settings
    workers: int = Field(default=1, description="Number of workers")
    worker_timeout: int = Field(default=60, description="Worker timeout in seconds")
    backlog: int = Field(default=2048, description="Worker backlog")

    # Production settings
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    enable_tracing: bool = Field(default=False, description="Enable request tracing")
    enable_swagger: bool = Field(default=True, description="Enable Swagger UI")
    enable_access_log: bool = Field(default=True, description="Enable access logging")

    # Container settings
    containerize: bool = Field(default=False, description="Enable containerization")
    container_registry: str | None = Field(
        default=None, description="Container registry URL"
    )
    base_image: str | None = Field(default=None, description="Base container image")

    # Cloud deployment settings
    deployment_target: str | None = Field(
        default=None, description="Deployment target (aws, gcp, azure, etc.)"
    )
    deployment_config: dict[str, Any] = Field(
        default_factory=dict, description="Deployment-specific configuration"
    )

    # Model packaging settings
    include_dependencies: bool = Field(
        default=True, description="Include dependencies in Bento"
    )
    python_version: str | None = Field(
        default=None, description="Python version for Bento"
    )
    conda_channels: list[str] = Field(
        default_factory=list, description="Conda channels for dependencies"
    )


class BentoMLAdapter(BaseMLModelAdapter):
    """BentoML adapter for ML model packaging and serving.

    This adapter provides comprehensive integration with BentoML for packaging,
    serving, and managing ML models with automatic API generation, containerization,
    and cloud deployment capabilities.
    """

    def __init__(self, settings: BentoMLSettings | None = None) -> None:
        """Initialize BentoML adapter.

        Args:
            settings: BentoML specific settings
        """
        self._bentoml_settings = settings or BentoMLSettings()
        super().__init__(self._bentoml_settings)
        self._http_session: aiohttp.ClientSession | None = None
        self._bento_store = None
        self._model_store = None

    @property
    def bentoml_settings(self) -> BentoMLSettings:
        """Get BentoML specific settings."""
        return self._bentoml_settings

    async def _create_client(self) -> dict[str, Any]:
        """Create BentoML client and HTTP session."""
        if not BENTOML_AVAILABLE:
            raise RuntimeError(
                "BentoML not available. Install with: pip install bentoml"
            )

        # Configure BentoML stores
        if self.bentoml_settings.bento_store_uri:
            self._bento_store = bentoml.bento_store.BentoStore(
                self.bentoml_settings.bento_store_uri
            )
        else:
            self._bento_store = bentoml.bento_store.BentoStore()

        if self.bentoml_settings.model_store_uri:
            self._model_store = bentoml.models.ModelStore(
                self.bentoml_settings.model_store_uri
            )
        else:
            self._model_store = bentoml.models.ModelStore()

        # Create HTTP session for API calls
        connector = aiohttp.TCPConnector(
            limit=self.bentoml_settings.connection_pool_size
        )
        timeout = aiohttp.ClientTimeout(total=self.bentoml_settings.timeout)
        headers = {"Content-Type": "application/json"}
        headers.update(self.bentoml_settings.custom_headers)

        self._http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
        )

        return {
            "bento_store": self._bento_store,
            "model_store": self._model_store,
            "http_session": self._http_session,
        }

    def _get_api_url(self, endpoint: str) -> str:
        """Get API URL for BentoML service."""
        protocol = "https" if self.bentoml_settings.use_tls else "http"
        base_url = (
            f"{protocol}://{self.bentoml_settings.host}:{self.bentoml_settings.port}"
        )
        return f"{base_url}{endpoint}"

    async def predict(self, request: ModelPredictionRequest) -> ModelPredictionResponse:
        """Perform real-time inference using BentoML service."""
        start_time = time.time()

        try:
            client = await self._ensure_client()
            http_session = client["http_session"]

            # Use configured API endpoint or default
            endpoint = self.bentoml_settings.api_endpoint
            if request.model_name and request.model_name != "default":
                # Use model-specific endpoint if available
                endpoint = f"/{request.model_name}/predict"

            url = self._get_api_url(endpoint)

            # Prepare payload
            payload = request.inputs
            if request.model_version:
                payload["__model_version__"] = request.model_version
            if request.metadata:
                payload["__metadata__"] = request.metadata

            async with http_session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"BentoML prediction error: {error_text}")

                # Handle different response formats
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    predictions = await response.json()
                else:
                    # Handle non-JSON responses (images, files, etc.)
                    predictions = {"output": await response.text()}

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
                model_version=request.model_version or "latest",
                latency_ms=latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["errors_total"] = self._metrics.get("errors_total", 0) + 1
            raise RuntimeError(f"BentoML prediction failed: {e}")

    async def batch_predict(
        self, request: BatchPredictionRequest
    ) -> BatchPredictionResponse:
        """Perform batch inference using BentoML service."""
        start_time = time.time()

        try:
            client = await self._ensure_client()
            http_session = client["http_session"]

            # Use batch endpoint if available, otherwise process individually
            batch_endpoint = self.bentoml_settings.batch_endpoint
            if request.model_name and request.model_name != "default":
                batch_endpoint = f"/{request.model_name}/batch_predict"

            batch_url = self._get_api_url(batch_endpoint)

            # Try batch endpoint first
            payload = {
                "instances": request.inputs,
                "batch_size": request.batch_size,
            }
            if request.model_version:
                payload["__model_version__"] = request.model_version
            if request.metadata:
                payload["__metadata__"] = request.metadata

            try:
                async with http_session.post(batch_url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        all_predictions = result.get("predictions", result)
                    else:
                        # Fall back to individual predictions
                        raise RuntimeError("Batch endpoint not available")
            except:
                # Process individually if batch endpoint not available
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

            # Ensure predictions are in list format
            if not isinstance(all_predictions, list):
                all_predictions = [all_predictions]

            total_latency_ms = (time.time() - start_time) * 1000
            avg_latency_ms = total_latency_ms / len(request.inputs)

            return BatchPredictionResponse(
                predictions=all_predictions,
                model_name=request.model_name,
                model_version=request.model_version or "latest",
                batch_size=len(request.inputs),
                total_latency_ms=total_latency_ms,
                avg_latency_ms=avg_latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["batch_errors_total"] = (
                self._metrics.get("batch_errors_total", 0) + 1
            )
            raise RuntimeError(f"BentoML batch prediction failed: {e}")

    async def list_models(self) -> list[ModelInfo]:
        """List available models from BentoML model store."""
        try:
            client = await self._ensure_client()
            model_store = client["model_store"]

            models = []

            # List all models in store
            for model in model_store.list():
                # Get model metadata
                model_info = model_store.get(model.tag)

                models.append(
                    ModelInfo(
                        name=model.name,
                        version=model.version,
                        status="available",
                        framework="bentoml",
                        description=f"BentoML model: {model.name}",
                        created_at=pd.Timestamp.fromtimestamp(
                            model_info.creation_time
                        ).isoformat(),
                        metadata={
                            "platform": "bentoml",
                            "tag": str(model.tag),
                            "module": model_info.module,
                            "api_version": model_info.api_version,
                            "context": model_info.context,
                            "options": model_info.options,
                            "labels": model_info.labels,
                        },
                    )
                )

            return models

        except Exception as e:
            raise RuntimeError(f"Failed to list BentoML models: {e}")

    async def get_model_info(
        self, model_name: str, version: str | None = None
    ) -> ModelInfo:
        """Get detailed information about a specific model."""
        try:
            client = await self._ensure_client()
            model_store = client["model_store"]

            # Create model tag
            if version:
                model_tag = f"{model_name}:{version}"
            else:
                # Get latest version
                models = [m for m in model_store.list() if m.name == model_name]
                if not models:
                    raise RuntimeError(f"Model {model_name} not found")
                model_tag = str(models[-1].tag)  # Latest by creation time

            # Get model info
            model_info = model_store.get(model_tag)

            return ModelInfo(
                name=model_name,
                version=version or model_info.tag.version,
                status="available",
                framework="bentoml",
                description=f"BentoML model: {model_name}",
                created_at=pd.Timestamp.fromtimestamp(
                    model_info.creation_time
                ).isoformat(),
                metadata={
                    "platform": "bentoml",
                    "tag": str(model_info.tag),
                    "module": model_info.module,
                    "api_version": model_info.api_version,
                    "context": model_info.context,
                    "options": model_info.options,
                    "labels": model_info.labels,
                    "signatures": model_info.signatures,
                },
            )

        except Exception as e:
            raise RuntimeError(f"Failed to get BentoML model info: {e}")

    async def get_model_health(
        self, model_name: str, version: str | None = None
    ) -> ModelHealth:
        """Get health status of a specific model."""
        try:
            # Check if model exists in store
            model_info = await self.get_model_info(model_name, version)

            # Check if service is running by trying a health check
            health_url = self._get_api_url("/healthz")

            client = await self._ensure_client()
            http_session = client["http_session"]

            try:
                async with http_session.get(health_url) as response:
                    service_healthy = response.status == 200
            except:
                service_healthy = False

            return ModelHealth(
                model_name=model_name,
                model_version=version or model_info.version,
                status="healthy" if service_healthy else "unhealthy",
                latency_p95=self._metrics.get("avg_latency_ms"),
                error_rate=self._metrics.get("error_rate", 0.0),
                last_check=pd.Timestamp.now().isoformat(),
                metadata={
                    "platform": "bentoml",
                    "tag": model_info.metadata.get("tag"),
                    "service_healthy": service_healthy,
                },
            )

        except Exception as e:
            return ModelHealth(
                model_name=model_name,
                model_version=version or "latest",
                status="error",
                last_check=pd.Timestamp.now().isoformat(),
                metadata={"error": str(e)},
            )

    async def load_model(
        self, model_name: str, model_path: str, version: str | None = None
    ) -> bool:
        """Load/import a model into BentoML model store."""
        try:
            # BentoML models are typically saved during training
            # This method would import an external model
            raise NotImplementedError(
                "Model loading in BentoML requires model-specific implementation. "
                "Use bentoml.save_model() during training or bentoml.import_model() for external models."
            )

        except Exception as e:
            raise RuntimeError(f"BentoML model loading failed: {e}")

    async def unload_model(self, model_name: str, version: str | None = None) -> bool:
        """Remove a model from BentoML model store."""
        try:
            client = await self._ensure_client()
            model_store = client["model_store"]

            # Create model tag
            if version:
                model_tag = f"{model_name}:{version}"
            else:
                # Delete all versions
                models = [m for m in model_store.list() if m.name == model_name]
                for model in models:
                    model_store.delete(str(model.tag))
                return True

            # Delete specific version
            model_store.delete(model_tag)
            return True

        except Exception as e:
            raise RuntimeError(f"BentoML model unloading failed: {e}")

    async def get_metrics(self) -> dict[str, Any]:
        """Get BentoML service metrics."""
        try:
            base_metrics = await super().get_metrics()

            # Try to get Prometheus metrics if enabled
            if self.bentoml_settings.enable_metrics:
                client = await self._ensure_client()
                http_session = client["http_session"]

                metrics_url = self._get_api_url(self.bentoml_settings.metrics_endpoint)

                try:
                    async with http_session.get(metrics_url) as response:
                        if response.status == 200:
                            metrics_text = await response.text()

                            # Parse key metrics
                            bentoml_metrics = {}
                            for line in metrics_text.split("\n"):
                                if "bentoml_service_request_total" in line:
                                    bentoml_metrics["total_requests"] = float(
                                        line.split()[-1]
                                    )
                                elif (
                                    "bentoml_service_request_duration_seconds" in line
                                    and 'quantile="0.95"' in line
                                ):
                                    bentoml_metrics["p95_latency_ms"] = (
                                        float(line.split()[-1]) * 1000
                                    )

                            base_metrics.update(bentoml_metrics)
                except:
                    pass

            # Add BentoML specific metrics
            client = await self._ensure_client()
            model_store = client["model_store"]
            bento_store = client["bento_store"]

            base_metrics.update(
                {
                    "models_count": len(list(model_store.list())),
                    "bentos_count": len(list(bento_store.list())),
                    "bento_store_uri": self.bentoml_settings.bento_store_uri,
                    "model_store_uri": self.bentoml_settings.model_store_uri,
                }
            )

            return base_metrics

        except Exception:
            return await super().get_metrics()

    async def health_check(self) -> bool:
        """Perform BentoML service health check."""
        try:
            client = await self._ensure_client()
            http_session = client["http_session"]

            # Check service health endpoint
            health_url = self._get_api_url("/healthz")

            async with http_session.get(health_url) as response:
                return response.status == 200

        except Exception:
            return False

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await super().cleanup()

        if self._http_session:
            await self._http_session.close()
            self._http_session = None


# Create the main adapter class alias for consistency
MLModel = BentoMLAdapter

# Module metadata for the adapter
MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="BentoML ML Model",
    category="mlmodel",
    provider="bentoml",
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
        AdapterCapability.MODEL_REGISTRY,
        AdapterCapability.MODEL_MONITORING,
        AdapterCapability.ARTIFACT_MANAGEMENT,
        AdapterCapability.METADATA_TRACKING,
        AdapterCapability.DEPLOYMENT_TRACKING,
        AdapterCapability.HEALTH_CHECKS,
        AdapterCapability.REST_SERVING,
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.PERFORMANCE_MONITORING,
        AdapterCapability.METRICS,
    ],
    required_packages=[
        "bentoml>=1.0.0",
        "aiohttp>=3.9.0",
        "pandas>=2.0.0",
    ],
    description="Comprehensive BentoML adapter for ML model packaging, serving, and deployment with automatic API generation",
    settings_class="BentoMLSettings",
    config_example={
        "host": "localhost",
        "port": 3000,
        "use_tls": False,
        "timeout": 30.0,
        "service_name": "ml_service",
        "api_endpoint": "/predict",
        "batch_endpoint": "/batch_predict",
        "workers": 1,
        "enable_metrics": True,
        "enable_swagger": True,
        "enable_health_checks": True,
    },
)

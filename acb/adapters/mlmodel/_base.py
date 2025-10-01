"""Base ML Model Adapter Implementation.

This module provides the base classes and interfaces for ML model serving adapters
in the ACB framework. It defines common patterns for model serving, inference,
versioning, and monitoring across different ML serving platforms.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any, Self

import pandas as pd
from pydantic import BaseModel, Field
from acb.core.cleanup import CleanupMixin

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class ModelPredictionRequest(BaseModel):
    """Standard prediction request format."""

    inputs: dict[str, Any] = Field(description="Input data for prediction")
    model_name: str = Field(description="Name of the model to use for prediction")
    model_version: str | None = Field(
        default=None,
        description="Specific model version to use",
    )
    timeout: float | None = Field(
        default=30.0,
        description="Request timeout in seconds",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional request metadata",
    )


class ModelPredictionResponse(BaseModel):
    """Standard prediction response format."""

    predictions: dict[str, Any] = Field(description="Model predictions/outputs")
    model_name: str = Field(description="Name of the model that generated predictions")
    model_version: str = Field(
        description="Version of the model that generated predictions",
    )
    confidence_scores: dict[str, float] | None = Field(
        default=None,
        description="Confidence scores for predictions",
    )
    latency_ms: float | None = Field(
        default=None,
        description="Prediction latency in milliseconds",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata",
    )


class BatchPredictionRequest(BaseModel):
    """Batch prediction request format."""

    inputs: list[dict[str, Any]] = Field(
        description="List of input data for batch prediction",
    )
    model_name: str = Field(description="Name of the model to use for prediction")
    model_version: str | None = Field(
        default=None,
        description="Specific model version to use",
    )
    batch_size: int | None = Field(default=32, description="Batch size for processing")
    timeout: float | None = Field(
        default=300.0,
        description="Request timeout in seconds",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional request metadata",
    )


class BatchPredictionResponse(BaseModel):
    """Batch prediction response format."""

    predictions: list[dict[str, Any]] = Field(
        description="List of model predictions/outputs",
    )
    model_name: str = Field(description="Name of the model that generated predictions")
    model_version: str = Field(
        description="Version of the model that generated predictions",
    )
    batch_size: int = Field(description="Actual batch size used")
    total_latency_ms: float | None = Field(
        default=None,
        description="Total batch processing latency in milliseconds",
    )
    avg_latency_ms: float | None = Field(
        default=None,
        description="Average per-item latency in milliseconds",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata",
    )


class ModelInfo(BaseModel):
    """Model information and metadata."""

    name: str = Field(description="Model name")
    version: str = Field(description="Model version")
    status: str = Field(description="Model status (ready, loading, error)")
    description: str | None = Field(default=None, description="Model description")
    framework: str | None = Field(
        default=None,
        description="ML framework (tensorflow, pytorch, etc.)",
    )
    input_schema: dict[str, Any] | None = Field(
        default=None,
        description="Expected input schema",
    )
    output_schema: dict[str, Any] | None = Field(
        default=None,
        description="Expected output schema",
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Model performance metrics",
    )
    created_at: str | None = Field(default=None, description="Model creation timestamp")
    updated_at: str | None = Field(
        default=None,
        description="Model last update timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model metadata",
    )


class ModelHealth(BaseModel):
    """Model health status."""

    model_name: str = Field(description="Model name")
    model_version: str = Field(description="Model version")
    status: str = Field(description="Health status (healthy, unhealthy, unknown)")
    latency_p50: float | None = Field(
        default=None,
        description="50th percentile latency in ms",
    )
    latency_p95: float | None = Field(
        default=None,
        description="95th percentile latency in ms",
    )
    latency_p99: float | None = Field(
        default=None,
        description="99th percentile latency in ms",
    )
    error_rate: float | None = Field(default=None, description="Error rate (0.0-1.0)")
    throughput_qps: float | None = Field(
        default=None,
        description="Throughput in queries per second",
    )
    memory_usage_mb: float | None = Field(
        default=None,
        description="Memory usage in MB",
    )
    cpu_usage_percent: float | None = Field(
        default=None,
        description="CPU usage percentage",
    )
    last_check: str | None = Field(
        default=None,
        description="Last health check timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional health metadata",
    )


class MLModelSettings(BaseModel):
    """Base settings for ML model adapters."""

    # Connection settings
    host: str = Field(default="localhost", description="ML serving host")
    port: int = Field(default=8501, description="ML serving port")
    use_tls: bool = Field(default=False, description="Use TLS/SSL connection")
    timeout: float = Field(default=30.0, description="Default request timeout")

    # Authentication
    api_key: str | None = Field(default=None, description="API key for authentication")
    token: str | None = Field(default=None, description="Bearer token")
    username: str | None = Field(default=None, description="Username for auth")
    password: str | None = Field(default=None, description="Password for auth")

    # Model settings
    default_model_name: str | None = Field(
        default=None,
        description="Default model name",
    )
    default_model_version: str | None = Field(
        default=None,
        description="Default model version",
    )
    auto_reload: bool = Field(default=True, description="Auto-reload models on changes")

    # Performance settings
    max_batch_size: int = Field(
        default=32,
        description="Maximum batch size for batch inference",
    )
    max_concurrent_requests: int = Field(
        default=100,
        description="Maximum concurrent requests",
    )
    connection_pool_size: int = Field(default=10, description="Connection pool size")

    # Monitoring settings
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_health_checks: bool = Field(default=True, description="Enable health checks")
    health_check_interval: float = Field(
        default=30.0,
        description="Health check interval in seconds",
    )

    # Caching settings
    enable_caching: bool = Field(default=False, description="Enable prediction caching")
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds")

    # Advanced settings
    custom_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Custom HTTP headers",
    )
    extra_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific configuration",
    )


class BaseMLModelAdapter(CleanupMixin, ABC):
    """Base class for ML model serving adapters.

    This abstract base class defines the standard interface that all ML model
    serving adapters must implement. It provides common patterns for model
    serving, inference, versioning, and monitoring.
    """

    def __init__(self, settings: MLModelSettings | None = None) -> None:
        """Initialize the ML model adapter.

        Args:
            settings: Configuration settings for the adapter
        """
        super().__init__()
        self._settings = settings or MLModelSettings()
        self._client = None
        self._health_monitor_task: asyncio.Task[None] | None = None
        self._metrics: dict[str, Any] = {}

    @property
    def settings(self) -> MLModelSettings:
        """Get adapter settings."""
        return self._settings

    @abstractmethod
    async def _create_client(self) -> Any:
        """Create and configure the ML serving client.

        Returns:
            Configured client instance
        """

    async def _ensure_client(self) -> Any:
        """Ensure client is initialized using lazy loading pattern."""
        if self._client is None:
            self._client = await self._create_client()
            self.register_resource(self._client)
        return self._client

    @abstractmethod
    async def predict(self, request: ModelPredictionRequest) -> ModelPredictionResponse:
        """Perform real-time inference on a single request.

        Args:
            request: Prediction request

        Returns:
            Prediction response
        """

    async def _predict(
        self,
        request: ModelPredictionRequest,
    ) -> ModelPredictionResponse:
        """Internal prediction implementation."""
        return await self.predict(request)

    @abstractmethod
    async def batch_predict(
        self,
        request: BatchPredictionRequest,
    ) -> BatchPredictionResponse:
        """Perform batch inference on multiple requests.

        Args:
            request: Batch prediction request

        Returns:
            Batch prediction response
        """

    async def _batch_predict(
        self,
        request: BatchPredictionRequest,
    ) -> BatchPredictionResponse:
        """Internal batch prediction implementation."""
        return await self.batch_predict(request)

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """List available models.

        Returns:
            List of available models with their information
        """

    async def _list_models(self) -> list[ModelInfo]:
        """Internal list models implementation."""
        return await self.list_models()

    @abstractmethod
    async def get_model_info(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelInfo:
        """Get information about a specific model.

        Args:
            model_name: Name of the model
            version: Model version (optional)

        Returns:
            Model information
        """

    async def _get_model_info(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelInfo:
        """Internal get model info implementation."""
        return await self.get_model_info(model_name, version)

    @abstractmethod
    async def get_model_health(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelHealth:
        """Get health status of a specific model.

        Args:
            model_name: Name of the model
            version: Model version (optional)

        Returns:
            Model health status
        """

    async def _get_model_health(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelHealth:
        """Internal get model health implementation."""
        return await self.get_model_health(model_name, version)

    async def load_model(
        self,
        model_name: str,
        model_path: str,
        version: str | None = None,
    ) -> bool:
        """Load a model into the serving platform.

        Args:
            model_name: Name for the model
            model_path: Path to the model artifacts
            version: Model version (optional)

        Returns:
            True if model loaded successfully
        """
        # Default implementation - override in subclasses that support model loading
        msg = "Model loading not supported by this adapter"
        raise NotImplementedError(msg)

    async def _load_model(
        self,
        model_name: str,
        model_path: str,
        version: str | None = None,
    ) -> bool:
        """Internal load model implementation."""
        return await self.load_model(model_name, model_path, version)

    async def unload_model(self, model_name: str, version: str | None = None) -> bool:
        """Unload a model from the serving platform.

        Args:
            model_name: Name of the model
            version: Model version (optional)

        Returns:
            True if model unloaded successfully
        """
        # Default implementation - override in subclasses that support model unloading
        msg = "Model unloading not supported by this adapter"
        raise NotImplementedError(msg)

    async def _unload_model(self, model_name: str, version: str | None = None) -> bool:
        """Internal unload model implementation."""
        return await self.unload_model(model_name, version)

    async def scale_model(
        self,
        model_name: str,
        replicas: int,
        version: str | None = None,
    ) -> bool:
        """Scale model serving replicas.

        Args:
            model_name: Name of the model
            replicas: Number of replicas to scale to
            version: Model version (optional)

        Returns:
            True if scaling successful
        """
        # Default implementation - override in subclasses that support scaling
        msg = "Model scaling not supported by this adapter"
        raise NotImplementedError(msg)

    async def _scale_model(
        self,
        model_name: str,
        replicas: int,
        version: str | None = None,
    ) -> bool:
        """Internal scale model implementation."""
        return await self.scale_model(model_name, replicas, version)

    async def get_metrics(self) -> dict[str, Any]:
        """Get adapter and model metrics.

        Returns:
            Metrics dictionary
        """
        return self._metrics.copy()

    async def _get_metrics(self) -> dict[str, Any]:
        """Internal get metrics implementation."""
        return await self.get_metrics()

    async def health_check(self) -> bool:
        """Perform adapter health check.

        Returns:
            True if adapter is healthy
        """
        try:
            client = await self._ensure_client()
            # Basic connectivity check - override in subclasses for specific checks
            return client is not None
        except Exception:
            return False

    async def _health_check(self) -> bool:
        """Internal health check implementation."""
        return await self.health_check()

    async def start_health_monitoring(self) -> None:
        """Start background health monitoring."""
        if not self._settings.enable_health_checks:
            return

        if self._health_monitor_task is not None:
            return

        async def monitor_health() -> None:
            while True:
                try:
                    healthy = await self.health_check()
                    self._metrics["health_status"] = (
                        "healthy" if healthy else "unhealthy"
                    )
                    self._metrics["last_health_check"] = pd.Timestamp.now().isoformat()
                except Exception as e:
                    self._metrics["health_status"] = "error"
                    self._metrics["health_error"] = str(e)

                await asyncio.sleep(self._settings.health_check_interval)

        self._health_monitor_task = asyncio.create_task(monitor_health())
        self.register_resource(self._health_monitor_task)

    async def stop_health_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._health_monitor_task is not None:
            self._health_monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._health_monitor_task
            self._health_monitor_task = None

    @asynccontextmanager
    async def _connection_context(self) -> AsyncGenerator[Any]:
        """Context manager for client connections."""
        client = await self._ensure_client()
        try:
            yield client
        finally:
            # Connection cleanup is handled by CleanupMixin
            pass

    async def init(self) -> None:
        """Initialize the adapter."""
        await self._ensure_client()
        if self._settings.enable_health_checks:
            await self.start_health_monitoring()

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.init()
        return self

    async def  __aexit__((self: Any, exc_type: Any, exc_val: Any, exc_tb: Any)) -> None:
        """Async context manager exit with cleanup."""
        await self.stop_health_monitoring()
        await self.cleanup()


# Export base types for use by concrete adapters
__all__ = [
    "BaseMLModelAdapter",
    "BatchPredictionRequest",
    "BatchPredictionResponse",
    "MLModelSettings",
    "ModelHealth",
    "ModelInfo",
    "ModelPredictionRequest",
    "ModelPredictionResponse",
]

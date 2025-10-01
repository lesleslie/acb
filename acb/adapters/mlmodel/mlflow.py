"""MLflow ML Model Adapter.

This adapter provides integration with MLflow for model registry, serving,
and lifecycle management. It supports model versioning, experiment tracking,
and deployment workflows with comprehensive monitoring.
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
    import mlflow
    import mlflow.pyfunc
    from mlflow.exceptions import MlflowException
    from mlflow.tracking import MlflowClient

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


class MLflowSettings(MLModelSettings):
    """MLflow specific settings."""

    # MLflow server settings
    tracking_uri: str = Field(
        default="http://localhost:5000",
        description="MLflow tracking server URI",
    )
    model_registry_uri: str | None = Field(
        default=None,
        description="MLflow model registry URI (defaults to tracking_uri)",
    )
    artifact_uri: str | None = Field(
        default=None,
        description="MLflow artifact store URI",
    )

    # Model serving settings
    serving_uri: str | None = Field(
        default=None,
        description="MLflow model serving endpoint",
    )
    serving_port: int = Field(default=5001, description="MLflow model serving port")

    # Model registry settings
    registered_model_name: str | None = Field(
        default=None,
        description="Default registered model name",
    )
    model_stage: str = Field(
        default="Production",
        description="Model stage (Production, Staging, Archived)",
    )
    model_version: str | None = Field(
        default=None,
        description="Specific model version",
    )

    # Experiment settings
    experiment_name: str | None = Field(
        default=None,
        description="MLflow experiment name",
    )
    experiment_id: str | None = Field(default=None, description="MLflow experiment ID")

    # Serving settings
    enable_model_serving: bool = Field(
        default=True,
        description="Enable MLflow model serving",
    )
    workers: int = Field(default=1, description="Number of serving workers")
    worker_timeout: int = Field(default=60, description="Worker timeout in seconds")

    # Registry settings
    enable_model_versioning: bool = Field(
        default=True,
        description="Enable automatic model versioning",
    )
    enable_model_signature: bool = Field(
        default=True,
        description="Enable model signature validation",
    )
    enable_input_example: bool = Field(
        default=True,
        description="Store input examples with models",
    )

    # Authentication
    mlflow_username: str | None = Field(default=None, description="MLflow username")
    mlflow_password: str | None = Field(default=None, description="MLflow password")


class MLflowAdapter(BaseMLModelAdapter):
    """MLflow adapter for model registry and serving.

    This adapter provides comprehensive integration with MLflow including
    model registry management, experiment tracking, model serving, and
    lifecycle management for production ML workflows.
    """

    def __init__(self, settings: MLflowSettings | None = None) -> None:
        """Initialize MLflow adapter.

        Args:
            settings: MLflow specific settings
        """
        self._mlflow_settings = settings or MLflowSettings()
        super().__init__(self._mlflow_settings)
        self._client: MlflowClient | None = None
        self._http_session: aiohttp.ClientSession | None = None

    @property
    def mlflow_settings(self) -> MLflowSettings:
        """Get MLflow specific settings."""
        return self._mlflow_settings

    async def _create_client(self) -> dict[str, Any]:
        """Create MLflow client and HTTP session."""
        if not MLFLOW_AVAILABLE:
            msg = "MLflow not available. Install with: pip install mlflow"
            raise RuntimeError(msg)

        # Set MLflow tracking URI
        mlflow.set_tracking_uri(self.mlflow_settings.tracking_uri)

        # Create MLflow client
        registry_uri = (
            self.mlflow_settings.model_registry_uri or self.mlflow_settings.tracking_uri
        )
        self._client = MlflowClient(
            tracking_uri=self.mlflow_settings.tracking_uri,
            registry_uri=registry_uri,
        )

        # Create HTTP session for serving API
        connector = aiohttp.TCPConnector(
            limit=self.mlflow_settings.connection_pool_size,
        )
        timeout = aiohttp.ClientTimeout(total=self.mlflow_settings.timeout)
        headers = {"Content-Type": "application/json"}
        headers.update(self.mlflow_settings.custom_headers)

        # Add authentication if configured
        if (
            self.mlflow_settings.mlflow_username
            and self.mlflow_settings.mlflow_password
        ):
            import base64

            auth_string = f"{self.mlflow_settings.mlflow_username}:{self.mlflow_settings.mlflow_password}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            headers["Authorization"] = f"Basic {auth_bytes}"

        self._http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
        )

        return {
            "mlflow_client": self._client,
            "http_session": self._http_session,
        }

    def _get_serving_url(
        self,
        model_name: str | None = None,
        version: str | None = None,
    ) -> str:
        """Get model serving URL."""
        if self.mlflow_settings.serving_uri:
            base_url = self.mlflow_settings.serving_uri
        else:
            protocol = "https" if self.mlflow_settings.use_tls else "http"
            base_url = f"{protocol}://{self.mlflow_settings.host}:{self.mlflow_settings.serving_port}"

        if model_name:
            if version:
                return f"{base_url}/invocations"
            return f"{base_url}/invocations"
        return f"{base_url}/invocations"

    def _get_model_uri(
        self,
        model_name: str,
        version: str | None = None,
        stage: str | None = None,
    ) -> str:
        """Get MLflow model URI."""
        if stage:
            return f"models:/{model_name}/{stage}"
        if version:
            return f"models:/{model_name}/{version}"
        return f"models:/{model_name}/{self.mlflow_settings.model_stage}"

    async def predict(self, request: ModelPredictionRequest) -> ModelPredictionResponse:
        """Perform real-time inference using MLflow model serving."""
        start_time = time.time()

        try:
            client = await self._ensure_client()
            http_session = client["http_session"]

            # Prepare prediction request
            self._get_model_uri(request.model_name, request.model_version)
            serving_url = self._get_serving_url(
                request.model_name,
                request.model_version,
            )

            # Format input data for MLflow serving
            if isinstance(request.inputs, dict):
                # Convert to dataframe format expected by MLflow
                if "instances" in request.inputs:
                    # Already in correct format
                    payload = request.inputs
                else:
                    # Convert to instances format
                    payload = {"instances": [request.inputs]}
            else:
                payload = {"instances": request.inputs}

            async with http_session.post(serving_url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    msg = f"MLflow serving error: {error_text}"
                    raise RuntimeError(msg)

                result = await response.json()
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
                model_version=request.model_version or self.mlflow_settings.model_stage,
                latency_ms=latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["errors_total"] = self._metrics.get("errors_total", 0) + 1
            msg = f"MLflow prediction failed: {e}"
            raise RuntimeError(msg)

    async def batch_predict(
        self,
        request: BatchPredictionRequest,
    ) -> BatchPredictionResponse:
        """Perform batch inference using MLflow."""
        start_time = time.time()

        try:
            client = await self._ensure_client()
            http_session = client["http_session"]

            serving_url = self._get_serving_url(
                request.model_name,
                request.model_version,
            )

            # Format batch data for MLflow serving
            payload = {"instances": request.inputs}

            async with http_session.post(serving_url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    msg = f"MLflow batch serving error: {error_text}"
                    raise RuntimeError(msg)

                result = await response.json()
                predictions_list = result.get("predictions", [])

            # Ensure predictions are in list format
            if not isinstance(predictions_list, list):
                predictions_list = [predictions_list]

            # Convert to expected format
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
                model_version=request.model_version or self.mlflow_settings.model_stage,
                batch_size=len(request.inputs),
                total_latency_ms=total_latency_ms,
                avg_latency_ms=avg_latency_ms,
                metadata=request.metadata,
            )

        except Exception as e:
            self._metrics["batch_errors_total"] = (
                self._metrics.get("batch_errors_total", 0) + 1
            )
            msg = f"MLflow batch prediction failed: {e}"
            raise RuntimeError(msg)

    async def list_models(self) -> list[ModelInfo]:
        """List registered models from MLflow."""
        try:
            client = await self._ensure_client()
            mlflow_client = client["mlflow_client"]

            models = []

            # Get all registered models
            for registered_model in mlflow_client.search_registered_models():
                model_name = registered_model.name

                # Get all versions for this model
                for model_version in mlflow_client.search_model_versions(
                    f"name='{model_name}'",
                ):
                    run_id = model_version.run_id

                    # Get run information
                    try:
                        run = mlflow_client.get_run(run_id)
                        metrics = run.data.metrics
                        params = run.data.params
                    except:
                        metrics = {}
                        params = {}

                    models.append(
                        ModelInfo(
                            name=model_name,
                            version=model_version.version,
                            status=model_version.current_stage.lower(),
                            description=model_version.description,
                            framework="mlflow",
                            created_at=pd.Timestamp.fromtimestamp(
                                model_version.creation_timestamp / 1000,
                            ).isoformat(),
                            updated_at=pd.Timestamp.fromtimestamp(
                                model_version.last_updated_timestamp / 1000,
                            ).isoformat(),
                            metrics=metrics,
                            metadata={
                                "platform": "mlflow",
                                "run_id": run_id,
                                "source": model_version.source,
                                "stage": model_version.current_stage,
                                "params": params,
                                "tags": model_version.tags,
                            },
                        ),
                    )

            return models

        except Exception as e:
            msg = f"Failed to list MLflow models: {e}"
            raise RuntimeError(msg)

    async def get_model_info(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelInfo:
        """Get detailed information about a specific model."""
        try:
            client = await self._ensure_client()
            mlflow_client = client["mlflow_client"]

            # Get model version info
            if version:
                model_version = mlflow_client.get_model_version(model_name, version)
            else:
                # Get latest version in specified stage
                versions = mlflow_client.get_latest_versions(
                    model_name,
                    stages=[self.mlflow_settings.model_stage],
                )
                if not versions:
                    msg = f"No model found in stage {self.mlflow_settings.model_stage}"
                    raise RuntimeError(
                        msg,
                    )
                model_version = versions[0]

            run_id = model_version.run_id

            # Get run information
            try:
                run = mlflow_client.get_run(run_id)
                metrics = run.data.metrics
                params = run.data.params
                artifacts = mlflow_client.list_artifacts(run_id)
            except:
                metrics = {}
                params = {}
                artifacts = []

            # Try to get model signature
            try:
                model_uri = self._get_model_uri(model_name, model_version.version)
                model = mlflow.pyfunc.load_model(model_uri)
                input_schema = (
                    model.metadata.signature.inputs.to_dict()
                    if model.metadata.signature
                    else None
                )
                output_schema = (
                    model.metadata.signature.outputs.to_dict()
                    if model.metadata.signature
                    else None
                )
            except:
                input_schema = None
                output_schema = None

            return ModelInfo(
                name=model_name,
                version=model_version.version,
                status=model_version.current_stage.lower(),
                description=model_version.description,
                framework="mlflow",
                input_schema=input_schema,
                output_schema=output_schema,
                created_at=pd.Timestamp.fromtimestamp(
                    model_version.creation_timestamp / 1000,
                ).isoformat(),
                updated_at=pd.Timestamp.fromtimestamp(
                    model_version.last_updated_timestamp / 1000,
                ).isoformat(),
                metrics=metrics,
                metadata={
                    "platform": "mlflow",
                    "run_id": run_id,
                    "source": model_version.source,
                    "stage": model_version.current_stage,
                    "params": params,
                    "tags": model_version.tags,
                    "artifacts": [artifact.path for artifact in artifacts],
                },
            )

        except Exception as e:
            msg = f"Failed to get MLflow model info: {e}"
            raise RuntimeError(msg)

    async def get_model_health(
        self,
        model_name: str,
        version: str | None = None,
    ) -> ModelHealth:
        """Get health status of a specific model."""
        try:
            # Get model info to check if it exists and is accessible
            model_info = await self.get_model_info(model_name, version)

            # Check if model is in production stage
            health_status = (
                "healthy" if model_info.status == "production" else "unhealthy"
            )

            # Try to load model to verify it's working
            try:
                model_uri = self._get_model_uri(model_name, version)
                mlflow.pyfunc.load_model(model_uri)
                health_status = "healthy"
            except Exception:
                health_status = "unhealthy"

            return ModelHealth(
                model_name=model_name,
                model_version=version or model_info.version,
                status=health_status,
                latency_p95=self._metrics.get("avg_latency_ms"),
                error_rate=self._metrics.get("error_rate", 0.0),
                last_check=pd.Timestamp.now().isoformat(),
                metadata={
                    "platform": "mlflow",
                    "stage": model_info.status,
                    "run_id": model_info.metadata.get("run_id"),
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
        self,
        model_name: str,
        model_path: str,
        version: str | None = None,
    ) -> bool:
        """Register a model in MLflow registry."""
        try:
            client = await self._ensure_client()
            mlflow_client = client["mlflow_client"]

            # Create registered model if it doesn't exist
            try:
                mlflow_client.create_registered_model(model_name)
            except MlflowException:
                # Model already exists
                pass

            # Create model version
            mlflow_client.create_model_version(
                name=model_name,
                source=model_path,
                run_id=None,  # Can be set if model is from a specific run
            )

            return True

        except Exception as e:
            msg = f"MLflow model registration failed: {e}"
            raise RuntimeError(msg)

    async def scale_model(
        self,
        model_name: str,
        replicas: int,
        version: str | None = None,
    ) -> bool:
        """MLflow doesn't support direct scaling - this would be handled by deployment platform."""
        # MLflow model serving typically runs as a single process
        # Scaling would be handled by the deployment platform (Kubernetes, Docker, etc.)
        msg = "Model scaling should be handled by deployment platform"
        raise NotImplementedError(
            msg,
        )

    async def get_metrics(self) -> dict[str, Any]:
        """Get MLflow specific metrics."""
        try:
            base_metrics = await super().get_metrics()

            client = await self._ensure_client()
            mlflow_client = client["mlflow_client"]

            # Add MLflow specific metrics
            mlflow_metrics = {
                "registered_models_count": len(
                    mlflow_client.search_registered_models(),
                ),
                "tracking_uri": self.mlflow_settings.tracking_uri,
                "model_registry_uri": self.mlflow_settings.model_registry_uri
                or self.mlflow_settings.tracking_uri,
            }

            # Get experiment metrics if experiment is configured
            if self.mlflow_settings.experiment_name:
                try:
                    experiment = mlflow_client.get_experiment_by_name(
                        self.mlflow_settings.experiment_name,
                    )
                    if experiment:
                        runs = mlflow_client.search_runs(
                            experiment_ids=[experiment.experiment_id],
                        )
                        mlflow_metrics["experiment_runs_count"] = len(runs)
                except:
                    pass

            base_metrics.update(mlflow_metrics)
            return base_metrics

        except Exception:
            return await super().get_metrics()

    async def health_check(self) -> bool:
        """Perform MLflow health check."""
        try:
            client = await self._ensure_client()
            mlflow_client = client["mlflow_client"]

            # Check if we can connect to MLflow tracking server
            mlflow_client.search_experiments()

            return True

        except Exception:
            return False

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await super().cleanup()

        if self._http_session:
            await self._http_session.close()
            self._http_session = None


# Create the main adapter class alias for consistency
MLModel = MLflowAdapter

# Module metadata for the adapter
MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="MLflow ML Model",
    category="mlmodel",
    provider="mlflow",
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
        "mlflow>=2.0.0",
        "aiohttp>=3.9.0",
        "pandas>=2.0.0",
    ],
    description="Comprehensive MLflow adapter for model registry, serving, and lifecycle management with experiment tracking",
    settings_class="MLflowSettings",
    config_example={
        "tracking_uri": "http://localhost:5000",
        "serving_port": 5001,
        "use_tls": False,
        "timeout": 30.0,
        "registered_model_name": "my_model",
        "model_stage": "Production",
        "enable_model_serving": True,
        "enable_model_versioning": True,
        "enable_metrics": True,
        "enable_health_checks": True,
    },
)

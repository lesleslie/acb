"""MLflow Experiment Tracking Adapter.

This adapter provides integration with MLflow for experiment tracking, including
metrics logging, parameter tracking, artifact management, and experiment lifecycle
management with comprehensive MLflow Tracking Server support.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiohttp
from pydantic import Field

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus, generate_adapter_id
from acb.adapters.experiment._base import (
    ArtifactInfo,
    ArtifactType,
    BaseExperimentAdapter,
    ExperimentInfo,
    ExperimentSettings,
    ExperimentStatus,
    MetricEntry,
    MetricType,
)

try:
    import mlflow
    from mlflow import MlflowClient
    from mlflow.entities import Experiment, Run
    from mlflow.exceptions import MlflowException

    _mlflow_available = True
except ImportError:
    mlflow = None
    MlflowClient = None
    Experiment = None
    Run = None
    MlflowException = Exception
    _mlflow_available = False


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="MLflow Experiment Tracking",
    category="experiment",
    provider="mlflow",
    version="1.0.0",
    acb_min_version="0.19.0",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.METADATA_TRACKING,
        AdapterCapability.ARTIFACT_MANAGEMENT,
        AdapterCapability.BATCH_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
    ],
    required_packages=["mlflow>=2.0.0"],
    description="High-performance MLflow experiment tracking with async operations",
)


class MLflowExperimentSettings(ExperimentSettings):
    """MLflow-specific experiment tracking settings."""

    # MLflow-specific settings
    mlflow_tracking_uri: Optional[str] = Field(
        default=None,
        description="MLflow tracking server URI",
    )
    registry_uri: Optional[str] = Field(
        default=None,
        description="MLflow model registry URI",
    )
    s3_endpoint_url: Optional[str] = Field(
        default=None,
        description="S3 endpoint URL for artifact storage",
    )
    aws_access_key_id: Optional[str] = Field(
        default=None,
        description="AWS access key ID",
    )
    aws_secret_access_key: Optional[str] = Field(
        default=None,
        description="AWS secret access key",
    )

    # Authentication
    mlflow_username: Optional[str] = Field(
        default=None,
        description="MLflow server username",
    )
    mlflow_password: Optional[str] = Field(
        default=None,
        description="MLflow server password",
    )
    mlflow_token: Optional[str] = Field(
        default=None,
        description="MLflow authentication token",
    )

    # Advanced settings
    create_experiments_on_init: bool = Field(
        default=True,
        description="Create default experiment on initialization",
    )
    default_artifact_root: Optional[str] = Field(
        default=None,
        description="Default artifact storage location",
    )


class MLflowExperiment(BaseExperimentAdapter):
    """MLflow experiment tracking adapter."""

    def __init__(self, settings: Optional[MLflowExperimentSettings] = None) -> None:
        """Initialize MLflow experiment adapter.

        Args:
            settings: MLflow-specific adapter settings
        """
        if not _mlflow_available:
            raise ImportError(
                "MLflow is required for MLflowExperiment adapter. "
                "Install with: pip install mlflow>=2.0.0"
            )

        super().__init__(settings)
        self._settings: MLflowExperimentSettings = settings or MLflowExperimentSettings()
        self._client: Optional[MlflowClient] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> None:
        """Connect to MLflow tracking server."""
        await self._ensure_client()

    async def disconnect(self) -> None:
        """Disconnect from MLflow tracking server."""
        if self._session:
            await self._session.close()
            self._session = None
        self._client = None

    async def _ensure_client(self) -> MlflowClient:
        """Ensure MLflow client is available."""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> MlflowClient:
        """Create MLflow client with configuration."""
        # Set environment variables for MLflow configuration
        if self._settings.mlflow_tracking_uri:
            os.environ["MLFLOW_TRACKING_URI"] = self._settings.mlflow_tracking_uri

        if self._settings.registry_uri:
            os.environ["MLFLOW_REGISTRY_URI"] = self._settings.registry_uri

        if self._settings.s3_endpoint_url:
            os.environ["MLFLOW_S3_ENDPOINT_URL"] = self._settings.s3_endpoint_url

        if self._settings.aws_access_key_id:
            os.environ["AWS_ACCESS_KEY_ID"] = self._settings.aws_access_key_id

        if self._settings.aws_secret_access_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = self._settings.aws_secret_access_key

        if self._settings.mlflow_username:
            os.environ["MLFLOW_TRACKING_USERNAME"] = self._settings.mlflow_username

        if self._settings.mlflow_password:
            os.environ["MLFLOW_TRACKING_PASSWORD"] = self._settings.mlflow_password

        if self._settings.mlflow_token:
            os.environ["MLFLOW_TRACKING_TOKEN"] = self._settings.mlflow_token

        # Create MLflow client
        tracking_uri = self._settings.mlflow_tracking_uri or self._settings.tracking_uri
        client = MlflowClient(tracking_uri=tracking_uri, registry_uri=self._settings.registry_uri)

        # Create aiohttp session for async operations
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._settings.timeout)
        )

        # Create default experiment if configured
        if self._settings.create_experiments_on_init:
            try:
                await self._run_sync(
                    client.create_experiment,
                    self._settings.default_experiment_name,
                    artifact_location=self._settings.default_artifact_root,
                )
            except MlflowException:
                # Experiment might already exist
                pass

        return client

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous function in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    async def health_check(self) -> bool:
        """Check MLflow tracking server health."""
        try:
            client = await self._ensure_client()
            await self._run_sync(client.search_experiments, max_results=1)
            return True
        except Exception:
            return False

    # Experiment Management
    async def create_experiment(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> str:
        """Create a new experiment."""
        client = await self._ensure_client()

        experiment_tags = tags or {}
        if description:
            experiment_tags["description"] = description

        experiment_id = await self._run_sync(
            client.create_experiment,
            name,
            artifact_location=self._settings.default_artifact_root,
            tags=experiment_tags,
        )
        return experiment_id

    async def get_experiment(self, experiment_id: str) -> ExperimentInfo:
        """Get experiment information."""
        client = await self._ensure_client()
        experiment = await self._run_sync(client.get_experiment, experiment_id)

        return ExperimentInfo(
            experiment_id=experiment.experiment_id,
            experiment_name=experiment.name,
            status=ExperimentStatus.RUNNING if experiment.lifecycle_stage == "active" else ExperimentStatus.FINISHED,
            created_at=datetime.fromtimestamp(experiment.creation_time / 1000),
            updated_at=datetime.fromtimestamp(experiment.last_update_time / 1000) if experiment.last_update_time else None,
            tags=experiment.tags or {},
        )

    async def list_experiments(
        self,
        max_results: int = 100,
        view_type: str = "ACTIVE_ONLY",
    ) -> List[ExperimentInfo]:
        """List experiments."""
        client = await self._ensure_client()
        experiments = await self._run_sync(
            client.search_experiments,
            view_type=view_type,
            max_results=max_results,
        )

        return [
            ExperimentInfo(
                experiment_id=exp.experiment_id,
                experiment_name=exp.name,
                status=ExperimentStatus.RUNNING if exp.lifecycle_stage == "active" else ExperimentStatus.FINISHED,
                created_at=datetime.fromtimestamp(exp.creation_time / 1000),
                updated_at=datetime.fromtimestamp(exp.last_update_time / 1000) if exp.last_update_time else None,
                tags=exp.tags or {},
            )
            for exp in experiments
        ]

    async def delete_experiment(self, experiment_id: str) -> None:
        """Delete an experiment."""
        client = await self._ensure_client()
        await self._run_sync(client.delete_experiment, experiment_id)

    # Run Management
    async def start_run(
        self,
        experiment_id: Optional[str] = None,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> str:
        """Start a new experiment run."""
        client = await self._ensure_client()

        # Use current experiment if not specified
        if experiment_id is None:
            experiment_id = self._current_experiment_id
            if experiment_id is None:
                # Get or create default experiment
                experiment_id = await self.get_or_create_experiment(
                    self._settings.default_experiment_name
                )

        run = await self._run_sync(
            client.create_run,
            experiment_id=experiment_id,
            run_name=run_name,
            tags=tags,
        )
        return run.info.run_id

    async def end_run(self, run_id: str, status: ExperimentStatus = ExperimentStatus.FINISHED) -> None:
        """End an experiment run."""
        client = await self._ensure_client()

        # Map status to MLflow status
        mlflow_status = "FINISHED"
        if status == ExperimentStatus.FAILED:
            mlflow_status = "FAILED"
        elif status == ExperimentStatus.KILLED:
            mlflow_status = "KILLED"

        await self._run_sync(client.set_terminated, run_id, status=mlflow_status)

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        """Get run information."""
        client = await self._ensure_client()
        run = await self._run_sync(client.get_run, run_id)

        return {
            "run_id": run.info.run_id,
            "experiment_id": run.info.experiment_id,
            "status": run.info.status,
            "start_time": datetime.fromtimestamp(run.info.start_time / 1000),
            "end_time": datetime.fromtimestamp(run.info.end_time / 1000) if run.info.end_time else None,
            "params": dict(run.data.params),
            "metrics": dict(run.data.metrics),
            "tags": dict(run.data.tags),
            "artifact_uri": run.info.artifact_uri,
        }

    # Parameter and Metric Logging
    async def log_param(self, run_id: str, key: str, value: Any) -> None:
        """Log a parameter."""
        client = await self._ensure_client()
        await self._run_sync(client.log_param, run_id, key, str(value))

    async def log_params(self, run_id: str, params: Dict[str, Any]) -> None:
        """Log multiple parameters."""
        client = await self._ensure_client()
        params_str = {k: str(v) for k, v in params.items()}
        await self._run_sync(client.log_batch, run_id, params=list(params_str.items()))

    async def log_metric(
        self,
        run_id: str,
        key: str,
        value: Union[float, int],
        step: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Log a metric."""
        client = await self._ensure_client()

        timestamp_ms = None
        if timestamp:
            timestamp_ms = int(timestamp.timestamp() * 1000)

        await self._run_sync(
            client.log_metric,
            run_id,
            key,
            float(value),
            timestamp=timestamp_ms,
            step=step,
        )

    async def log_metrics(
        self,
        run_id: str,
        metrics: Dict[str, Union[float, int]],
        step: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Log multiple metrics."""
        client = await self._ensure_client()

        timestamp_ms = None
        if timestamp:
            timestamp_ms = int(timestamp.timestamp() * 1000)

        metrics_list = [
            (key, float(value), timestamp_ms, step)
            for key, value in metrics.items()
        ]
        await self._run_sync(client.log_batch, run_id, metrics=metrics_list)

    # Artifact Management
    async def log_artifact(
        self,
        run_id: str,
        local_path: Union[str, Path],
        artifact_path: Optional[str] = None,
        artifact_type: ArtifactType = ArtifactType.OTHER,
    ) -> None:
        """Log an artifact."""
        client = await self._ensure_client()
        await self._run_sync(
            client.log_artifact,
            run_id,
            str(local_path),
            artifact_path,
        )

    async def log_artifacts(
        self,
        run_id: str,
        local_dir: Union[str, Path],
        artifact_path: Optional[str] = None,
    ) -> None:
        """Log multiple artifacts from directory."""
        client = await self._ensure_client()
        await self._run_sync(
            client.log_artifacts,
            run_id,
            str(local_dir),
            artifact_path,
        )

    async def download_artifact(
        self,
        run_id: str,
        artifact_path: str,
        local_path: Union[str, Path],
    ) -> None:
        """Download an artifact."""
        client = await self._ensure_client()
        await self._run_sync(
            client.download_artifacts,
            run_id,
            artifact_path,
            str(local_path),
        )

    async def list_artifacts(self, run_id: str, path: Optional[str] = None) -> List[ArtifactInfo]:
        """List artifacts for a run."""
        client = await self._ensure_client()
        artifacts = await self._run_sync(client.list_artifacts, run_id, path)

        return [
            ArtifactInfo(
                name=artifact.path.split("/")[-1],
                path=artifact.path,
                artifact_type=ArtifactType.OTHER,
                size_bytes=artifact.file_size if hasattr(artifact, 'file_size') else None,
            )
            for artifact in artifacts
        ]

    # Search and Query
    async def search_runs(
        self,
        experiment_ids: Optional[List[str]] = None,
        filter_string: Optional[str] = None,
        order_by: Optional[List[str]] = None,
        max_results: int = 1000,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search experiment runs."""
        client = await self._ensure_client()

        runs = await self._run_sync(
            client.search_runs,
            experiment_ids=experiment_ids,
            filter_string=filter_string,
            order_by=order_by,
            max_results=max_results,
            page_token=page_token,
        )

        return [
            {
                "run_id": run.info.run_id,
                "experiment_id": run.info.experiment_id,
                "status": run.info.status,
                "start_time": datetime.fromtimestamp(run.info.start_time / 1000),
                "end_time": datetime.fromtimestamp(run.info.end_time / 1000) if run.info.end_time else None,
                "params": dict(run.data.params),
                "metrics": dict(run.data.metrics),
                "tags": dict(run.data.tags),
                "artifact_uri": run.info.artifact_uri,
            }
            for run in runs
        ]


# Create type alias for backward compatibility
Experiment = MLflowExperiment
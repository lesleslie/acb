"""Base Experiment Tracking Adapter.

This module provides the foundation for experiment tracking adapters, including
interfaces for logging metrics, parameters, artifacts, and managing experiment
lifecycle across different platforms like MLflow, W&B, and TensorBoard.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path


class ExperimentStatus(str, Enum):
    """Experiment status enum."""

    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    KILLED = "killed"


class MetricType(str, Enum):
    """Metric type enum."""

    SCALAR = "scalar"
    HISTOGRAM = "histogram"
    IMAGE = "image"
    TEXT = "text"


class ArtifactType(str, Enum):
    """Artifact type enum."""

    MODEL = "model"
    DATASET = "dataset"
    IMAGE = "image"
    TEXT = "text"
    CODE = "code"
    OTHER = "other"


class ExperimentInfo(BaseModel):
    """Experiment information model."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    experiment_id: str
    experiment_name: str
    status: ExperimentStatus
    created_at: datetime
    updated_at: datetime | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)


class MetricEntry(BaseModel):
    """Metric entry model."""

    model_config = ConfigDict(extra="allow")

    name: str
    value: float | int | str
    step: int | None = None
    timestamp: datetime | None = None
    metric_type: MetricType = MetricType.SCALAR


class ArtifactInfo(BaseModel):
    """Artifact information model."""

    model_config = ConfigDict(extra="allow")

    name: str
    path: str
    artifact_type: ArtifactType
    size_bytes: int | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentSettings(BaseModel):
    """Base experiment tracking adapter settings."""

    model_config = ConfigDict(extra="allow")

    # Connection settings
    tracking_uri: str | None = None
    registry_uri: str | None = None

    # Authentication
    username: str | None = None
    password: str | None = None
    token: str | None = None

    # Default experiment settings
    default_experiment_name: str = "default"
    auto_create_experiments: bool = True

    # Logging settings
    log_models: bool = True
    log_artifacts: bool = True
    log_system_metrics: bool = False

    # Performance settings
    batch_size: int = 100
    flush_interval: int = 10  # seconds
    max_retries: int = 3
    timeout: int = 30  # seconds


class BaseExperimentAdapter(ABC):
    """Base class for experiment tracking adapters."""

    def __init__(self, settings: ExperimentSettings | None = None) -> None:
        """Initialize the experiment adapter.

        Args:
            settings: Adapter configuration settings
        """
        self._settings = settings or ExperimentSettings()
        self._client = None
        self._current_experiment_id: str | None = None

    @property
    def settings(self) -> ExperimentSettings:
        """Get adapter settings."""
        return self._settings

    async def __aenter__(self) -> None:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    # Connection Management
    @abstractmethod
    async def connect(self) -> None:
        """Connect to experiment tracking service."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from experiment tracking service."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the experiment tracking service is healthy."""

    # Experiment Management
    @abstractmethod
    async def create_experiment(
        self,
        name: str,
        tags: dict[str, str] | None = None,
        description: str | None = None,
    ) -> str:
        """Create a new experiment.

        Args:
            name: Experiment name
            tags: Optional experiment tags
            description: Optional experiment description

        Returns:
            Experiment ID
        """

    @abstractmethod
    async def get_experiment(self, experiment_id: str) -> ExperimentInfo:
        """Get experiment information.

        Args:
            experiment_id: Experiment ID

        Returns:
            Experiment information
        """

    @abstractmethod
    async def list_experiments(
        self,
        max_results: int = 100,
        view_type: str = "ACTIVE_ONLY",
    ) -> list[ExperimentInfo]:
        """List experiments.

        Args:
            max_results: Maximum number of experiments to return
            view_type: View type (ACTIVE_ONLY, DELETED_ONLY, ALL)

        Returns:
            List of experiment information
        """

    @abstractmethod
    async def delete_experiment(self, experiment_id: str) -> None:
        """Delete an experiment.

        Args:
            experiment_id: Experiment ID
        """

    # Run Management
    @abstractmethod
    async def start_run(
        self,
        experiment_id: str | None = None,
        run_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> str:
        """Start a new experiment run.

        Args:
            experiment_id: Experiment ID (uses current if None)
            run_name: Optional run name
            tags: Optional run tags

        Returns:
            Run ID
        """

    @abstractmethod
    async def end_run(
        self,
        run_id: str,
        status: ExperimentStatus = ExperimentStatus.FINISHED,
    ) -> None:
        """End an experiment run.

        Args:
            run_id: Run ID
            status: Final run status
        """

    @abstractmethod
    async def get_run(self, run_id: str) -> dict[str, Any]:
        """Get run information.

        Args:
            run_id: Run ID

        Returns:
            Run information
        """

    # Parameter and Metric Logging
    @abstractmethod
    async def log_param(self, run_id: str, key: str, value: Any) -> None:
        """Log a parameter.

        Args:
            run_id: Run ID
            key: Parameter name
            value: Parameter value
        """

    @abstractmethod
    async def log_params(self, run_id: str, params: dict[str, Any]) -> None:
        """Log multiple parameters.

        Args:
            run_id: Run ID
            params: Parameters dictionary
        """

    @abstractmethod
    async def log_metric(
        self,
        run_id: str,
        key: str,
        value: float,
        step: int | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Log a metric.

        Args:
            run_id: Run ID
            key: Metric name
            value: Metric value
            step: Optional step number
            timestamp: Optional timestamp
        """

    @abstractmethod
    async def log_metrics(
        self,
        run_id: str,
        metrics: dict[str, float | int],
        step: int | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Log multiple metrics.

        Args:
            run_id: Run ID
            metrics: Metrics dictionary
            step: Optional step number
            timestamp: Optional timestamp
        """

    # Artifact Management
    @abstractmethod
    async def log_artifact(
        self,
        run_id: str,
        local_path: str | Path,
        artifact_path: str | None = None,
        artifact_type: ArtifactType = ArtifactType.OTHER,
    ) -> None:
        """Log an artifact.

        Args:
            run_id: Run ID
            local_path: Local path to artifact
            artifact_path: Remote artifact path
            artifact_type: Artifact type
        """

    @abstractmethod
    async def log_artifacts(
        self,
        run_id: str,
        local_dir: str | Path,
        artifact_path: str | None = None,
    ) -> None:
        """Log multiple artifacts from directory.

        Args:
            run_id: Run ID
            local_dir: Local directory path
            artifact_path: Remote artifact path prefix
        """

    @abstractmethod
    async def download_artifact(
        self,
        run_id: str,
        artifact_path: str,
        local_path: str | Path,
    ) -> None:
        """Download an artifact.

        Args:
            run_id: Run ID
            artifact_path: Remote artifact path
            local_path: Local download path
        """

    @abstractmethod
    async def list_artifacts(
        self,
        run_id: str,
        path: str | None = None,
    ) -> list[ArtifactInfo]:
        """List artifacts for a run.

        Args:
            run_id: Run ID
            path: Optional artifact path filter

        Returns:
            List of artifact information
        """

    # Search and Query
    @abstractmethod
    async def search_runs(
        self,
        experiment_ids: list[str] | None = None,
        filter_string: str | None = None,
        order_by: list[str] | None = None,
        max_results: int = 1000,
        page_token: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search experiment runs.

        Args:
            experiment_ids: Optional experiment ID filter
            filter_string: Optional filter expression
            order_by: Optional ordering
            max_results: Maximum results to return
            page_token: Optional pagination token

        Returns:
            List of run information
        """

    # Convenience Methods
    async def set_experiment(self, experiment_id: str) -> None:
        """Set the current experiment.

        Args:
            experiment_id: Experiment ID
        """
        self._current_experiment_id = experiment_id

    async def get_or_create_experiment(self, name: str) -> str:
        """Get or create an experiment by name.

        Args:
            name: Experiment name

        Returns:
            Experiment ID
        """
        experiments = await self.list_experiments()
        for exp in experiments:
            if exp.experiment_name == name:
                return exp.experiment_id

        return await self.create_experiment(name)

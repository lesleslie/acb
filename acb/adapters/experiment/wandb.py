"""Weights & Biases Experiment Tracking Adapter.

This adapter provides integration with Weights & Biases for experiment tracking,
including metrics logging, parameter tracking, artifact management, and experiment
lifecycle management with comprehensive W&B API support.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
from pydantic import Field
from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    generate_adapter_id,
)
from acb.adapters.experiment._base import (
    ArtifactInfo,
    ArtifactType,
    BaseExperimentAdapter,
    ExperimentInfo,
    ExperimentSettings,
    ExperimentStatus,
)

try:
    import wandb
    from wandb.apis.public import Api as WandbApi
    from wandb.apis.public import Project, Run

    _wandb_available = True
except ImportError:
    wandb = None
    WandbApi = None
    Project = None
    Run = None
    _wandb_available = False


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Weights & Biases Experiment Tracking",
    category="experiment",
    provider="wandb",
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
    required_packages=["wandb>=0.16.0"],
    description="High-performance W&B experiment tracking with async operations",
)


class WandbExperimentSettings(ExperimentSettings):
    """W&B-specific experiment tracking settings."""

    # W&B-specific settings
    project: str = Field(
        default="default-project",
        description="W&B project name",
    )
    entity: str | None = Field(
        default=None,
        description="W&B entity (team/user)",
    )
    api_key: str | None = Field(
        default=None,
        description="W&B API key",
    )
    base_url: str | None = Field(
        default=None,
        description="W&B server base URL (for private instances)",
    )

    # Run settings
    job_type: str = Field(
        default="experiment",
        description="W&B job type",
    )
    save_code: bool = Field(
        default=True,
        description="Save code snapshots",
    )
    resume: str | None = Field(
        default=None,
        description="Resume strategy (allow, must, never, auto)",
    )
    reinit: bool = Field(
        default=False,
        description="Allow reinitializing runs",
    )

    # Sync settings
    sync_tensorboard: bool = Field(
        default=False,
        description="Sync TensorBoard logs",
    )
    monitor_gym: bool = Field(
        default=False,
        description="Monitor Gym environments",
    )


class WandbExperiment(BaseExperimentAdapter):
    """Weights & Biases experiment tracking adapter."""

    def __init__(self, settings: WandbExperimentSettings | None = None) -> None:
        """Initialize W&B experiment adapter.

        Args:
            settings: W&B-specific adapter settings
        """
        if not _wandb_available:
            raise ImportError(
                "Weights & Biases is required for WandbExperiment adapter. "
                "Install with: pip install wandb>=0.16.0"
            )

        super().__init__(settings)
        self._settings: WandbExperimentSettings = settings or WandbExperimentSettings()
        self._api: WandbApi | None = None
        self._current_run: Any | None = None
        self._session: aiohttp.ClientSession | None = None

    async def connect(self) -> None:
        """Connect to W&B service."""
        await self._ensure_api()

    async def disconnect(self) -> None:
        """Disconnect from W&B service."""
        if self._current_run:
            await self._run_sync(self._current_run.finish)
            self._current_run = None

        if self._session:
            await self._session.close()
            self._session = None
        self._api = None

    async def _ensure_api(self) -> WandbApi:
        """Ensure W&B API is available."""
        if self._api is None:
            self._api = await self._create_api()
        return self._api

    async def _create_api(self) -> WandbApi:
        """Create W&B API client with configuration."""
        # Set environment variables for W&B configuration
        if self._settings.api_key:
            os.environ["WANDB_API_KEY"] = self._settings.api_key

        if self._settings.base_url:
            os.environ["WANDB_BASE_URL"] = self._settings.base_url

        # Initialize W&B
        await self._run_sync(
            wandb.login,
            key=self._settings.api_key,
            relogin=True,
            force=True,
        )

        # Create API client
        api = WandbApi()

        # Create aiohttp session for async operations
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._settings.timeout)
        )

        return api

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous function in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    async def health_check(self) -> bool:
        """Check W&B service health."""
        try:
            api = await self._ensure_api()
            await self._run_sync(
                api.projects,
                entity=self._settings.entity,
            )
            return True
        except Exception:
            return False

    # Experiment Management
    async def create_experiment(
        self,
        name: str,
        tags: dict[str, str] | None = None,
        description: str | None = None,
    ) -> str:
        """Create a new experiment (project in W&B)."""
        # W&B projects are created automatically when first run is created
        # Return the project name as experiment ID
        return name

    async def get_experiment(self, experiment_id: str) -> ExperimentInfo:
        """Get experiment information."""
        api = await self._ensure_api()

        try:
            project = await self._run_sync(
                api.project,
                name=experiment_id,
                entity=self._settings.entity,
            )

            return ExperimentInfo(
                experiment_id=experiment_id,
                experiment_name=project.name,
                status=ExperimentStatus.RUNNING,  # W&B projects don't have status
                created_at=project.created_at,
                updated_at=project.updated_at,
                tags={},  # W&B projects don't have tags at project level
            )
        except Exception:
            # Project might not exist, return minimal info
            return ExperimentInfo(
                experiment_id=experiment_id,
                experiment_name=experiment_id,
                status=ExperimentStatus.RUNNING,
                created_at=datetime.now(),
            )

    async def list_experiments(
        self,
        max_results: int = 100,
        view_type: str = "ACTIVE_ONLY",
    ) -> list[ExperimentInfo]:
        """List experiments (projects in W&B)."""
        api = await self._ensure_api()

        projects = await self._run_sync(
            api.projects,
            entity=self._settings.entity,
        )

        # Convert projects to experiment info
        results = []
        for project in projects[:max_results]:
            results.append(
                ExperimentInfo(
                    experiment_id=project.name,
                    experiment_name=project.name,
                    status=ExperimentStatus.RUNNING,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    tags={},
                )
            )

        return results

    async def delete_experiment(self, experiment_id: str) -> None:
        """Delete an experiment."""
        # W&B doesn't support deleting projects via API
        # This would need to be done through the web interface
        raise NotImplementedError("W&B doesn't support deleting projects via API")

    # Run Management
    async def start_run(
        self,
        experiment_id: str | None = None,
        run_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> str:
        """Start a new experiment run."""
        project = experiment_id or self._settings.project

        # Initialize W&B run
        run = await self._run_sync(
            wandb.init,
            project=project,
            entity=self._settings.entity,
            name=run_name,
            job_type=self._settings.job_type,
            tags=list(tags.keys()) if tags else None,
            config=tags or {},
            save_code=self._settings.save_code,
            resume=self._settings.resume,
            reinit=self._settings.reinit,
            sync_tensorboard=self._settings.sync_tensorboard,
            monitor_gym=self._settings.monitor_gym,
        )

        self._current_run = run
        return run.id

    async def end_run(
        self, run_id: str, status: ExperimentStatus = ExperimentStatus.FINISHED
    ) -> None:
        """End an experiment run."""
        if self._current_run and self._current_run.id == run_id:
            exit_code = 0
            if status == ExperimentStatus.FAILED:
                exit_code = 1

            await self._run_sync(self._current_run.finish, exit_code=exit_code)
            self._current_run = None
        else:
            # Can't end runs that aren't current in W&B
            pass

    async def get_run(self, run_id: str) -> dict[str, Any]:
        """Get run information."""
        api = await self._ensure_api()

        run = await self._run_sync(
            api.run,
            f"{self._settings.entity}/{self._settings.project}/{run_id}",
        )

        return {
            "run_id": run.id,
            "experiment_id": run.project,
            "status": run.state,
            "start_time": run.created_at,
            "end_time": run.updated_at,
            "params": dict(run.config),
            "metrics": {
                k: v for k, v in run.summary.items() if isinstance(v, int | float)
            },
            "tags": run.tags or [],
            "artifact_uri": f"wandb://{run.entity}/{run.project}/{run.id}",
        }

    # Parameter and Metric Logging
    async def log_param(self, run_id: str, key: str, value: Any) -> None:
        """Log a parameter."""
        if self._current_run and self._current_run.id == run_id:
            await self._run_sync(wandb.config.update, {key: value})
        else:
            # Can't log to non-current runs
            pass

    async def log_params(self, run_id: str, params: dict[str, Any]) -> None:
        """Log multiple parameters."""
        if self._current_run and self._current_run.id == run_id:
            await self._run_sync(wandb.config.update, params)
        else:
            # Can't log to non-current runs
            pass

    async def log_metric(
        self,
        run_id: str,
        key: str,
        value: float | int,
        step: int | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Log a metric."""
        if self._current_run and self._current_run.id == run_id:
            log_data = {key: value}
            if step is not None:
                log_data["_step"] = step

            await self._run_sync(wandb.log, log_data)
        else:
            # Can't log to non-current runs
            pass

    async def log_metrics(
        self,
        run_id: str,
        metrics: dict[str, float | int],
        step: int | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Log multiple metrics."""
        if self._current_run and self._current_run.id == run_id:
            log_data = dict(metrics)
            if step is not None:
                log_data["_step"] = step

            await self._run_sync(wandb.log, log_data)
        else:
            # Can't log to non-current runs
            pass

    # Artifact Management
    async def log_artifact(
        self,
        run_id: str,
        local_path: str | Path,
        artifact_path: str | None = None,
        artifact_type: ArtifactType = ArtifactType.OTHER,
    ) -> None:
        """Log an artifact."""
        if self._current_run and self._current_run.id == run_id:
            # Create W&B artifact
            artifact_name = artifact_path or Path(local_path).name
            artifact = await self._run_sync(
                wandb.Artifact,
                artifact_name,
                type=artifact_type.value,
            )
            await self._run_sync(artifact.add_file, str(local_path))
            await self._run_sync(self._current_run.log_artifact, artifact)
        else:
            # Can't log to non-current runs
            pass

    async def log_artifacts(
        self,
        run_id: str,
        local_dir: str | Path,
        artifact_path: str | None = None,
    ) -> None:
        """Log multiple artifacts from directory."""
        if self._current_run and self._current_run.id == run_id:
            # Create W&B artifact
            artifact_name = artifact_path or Path(local_dir).name
            artifact = await self._run_sync(
                wandb.Artifact,
                artifact_name,
                type="dataset",
            )
            await self._run_sync(artifact.add_dir, str(local_dir))
            await self._run_sync(self._current_run.log_artifact, artifact)
        else:
            # Can't log to non-current runs
            pass

    async def download_artifact(
        self,
        run_id: str,
        artifact_path: str,
        local_path: str | Path,
    ) -> None:
        """Download an artifact."""
        api = await self._ensure_api()

        run = await self._run_sync(
            api.run,
            f"{self._settings.entity}/{self._settings.project}/{run_id}",
        )

        # Find artifact by name
        for artifact in run.logged_artifacts():
            if artifact.name == artifact_path:
                await self._run_sync(artifact.download, str(local_path))
                break

    async def list_artifacts(
        self, run_id: str, path: str | None = None
    ) -> list[ArtifactInfo]:
        """List artifacts for a run."""
        api = await self._ensure_api()

        run = await self._run_sync(
            api.run,
            f"{self._settings.entity}/{self._settings.project}/{run_id}",
        )

        artifacts = []
        for artifact in run.logged_artifacts():
            artifacts.append(
                ArtifactInfo(
                    name=artifact.name,
                    path=artifact.name,
                    artifact_type=ArtifactType(artifact.type),
                    size_bytes=artifact.size,
                    created_at=artifact.created_at,
                    metadata=artifact.metadata or {},
                )
            )

        return artifacts

    # Search and Query
    async def search_runs(
        self,
        experiment_ids: list[str] | None = None,
        filter_string: str | None = None,
        order_by: list[str] | None = None,
        max_results: int = 1000,
        page_token: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search experiment runs."""
        api = await self._ensure_api()

        # Use first experiment ID or default project
        project = (
            experiment_ids[0] if experiment_ids else None
        ) or self._settings.project

        runs = await self._run_sync(
            api.runs,
            path=f"{self._settings.entity}/{project}",
            filters={"$and": [filter_string]} if filter_string else None,
            order=order_by[0] if order_by else None,
            per_page=min(max_results, 1000),
        )

        return [
            {
                "run_id": run.id,
                "experiment_id": run.project,
                "status": run.state,
                "start_time": run.created_at,
                "end_time": run.updated_at,
                "params": dict(run.config),
                "metrics": {
                    k: v for k, v in run.summary.items() if isinstance(v, int | float)
                },
                "tags": run.tags or [],
                "artifact_uri": f"wandb://{run.entity}/{run.project}/{run.id}",
            }
            for run in runs
        ]


# Create type alias for backward compatibility
Experiment = WandbExperiment

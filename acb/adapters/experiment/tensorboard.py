"""TensorBoard Experiment Tracking Adapter.

This adapter provides integration with TensorBoard for experiment tracking,
including metrics logging, histogram tracking, image logging, and basic
experiment management with TensorBoard SummaryWriter support.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

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
    import numpy as np
    import torch
    from torch.utils.tensorboard import SummaryWriter

    _tensorboard_available = True
except ImportError:
    SummaryWriter = None
    torch = None
    np = None
    _tensorboard_available = False


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="TensorBoard Experiment Tracking",
    category="experiment",
    provider="tensorboard",
    version="1.0.0",
    acb_min_version="0.19.0",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.METADATA_TRACKING,
        AdapterCapability.BATCH_OPERATIONS,
    ],
    required_packages=["torch>=2.0.0", "tensorboard>=2.14.0", "numpy>=1.24.0"],
    description="TensorBoard experiment tracking with async operations",
)


class TensorBoardExperimentSettings(ExperimentSettings):
    """TensorBoard-specific experiment tracking settings."""

    # TensorBoard-specific settings
    log_dir: str = Field(
        default="./runs",
        description="TensorBoard log directory",
    )
    purge_step: int | None = Field(
        default=None,
        description="Purge events older than this step",
    )
    max_queue: int = Field(
        default=10,
        description="Maximum queue size for async writing",
    )
    flush_secs: int = Field(
        default=120,
        description="Flush interval in seconds",
    )
    filename_suffix: str = Field(
        default="",
        description="Filename suffix for log files",
    )

    # Histogram settings
    histogram_freq: int = Field(
        default=1,
        description="Frequency for histogram logging",
    )
    write_graph: bool = Field(
        default=False,
        description="Write computation graph",
    )
    write_images: bool = Field(
        default=True,
        description="Write images",
    )


class TensorBoardExperiment(BaseExperimentAdapter):
    """TensorBoard experiment tracking adapter."""

    def __init__(self, settings: TensorBoardExperimentSettings | None = None) -> None:
        """Initialize TensorBoard experiment adapter.

        Args:
            settings: TensorBoard-specific adapter settings
        """
        if not _tensorboard_available:
            raise ImportError(
                "TensorBoard is required for TensorBoardExperiment adapter. "
                "Install with: pip install torch tensorboard numpy"
            )

        super().__init__(settings)
        self._settings: TensorBoardExperimentSettings = (
            settings or TensorBoardExperimentSettings()
        )
        self._writers: dict[str, SummaryWriter] = {}
        self._experiments: dict[str, ExperimentInfo] = {}
        self._runs: dict[str, dict[str, Any]] = {}

    async def connect(self) -> None:
        """Connect to TensorBoard (initialize log directory)."""
        # Create log directory if it doesn't exist
        log_dir = Path(self._settings.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

    async def disconnect(self) -> None:
        """Disconnect from TensorBoard (close all writers)."""
        for writer in self._writers.values():
            await self._run_sync(writer.close)
        self._writers.clear()

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous function in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    async def health_check(self) -> bool:
        """Check TensorBoard health (log directory accessibility)."""
        try:
            log_dir = Path(self._settings.log_dir)
            return log_dir.exists() and log_dir.is_dir()
        except Exception:
            return False

    # Experiment Management
    async def create_experiment(
        self,
        name: str,
        tags: dict[str, str] | None = None,
        description: str | None = None,
    ) -> str:
        """Create a new experiment (subdirectory in TensorBoard)."""
        experiment_id = name
        experiment_dir = Path(self._settings.log_dir) / name
        experiment_dir.mkdir(parents=True, exist_ok=True)

        # Store experiment info
        self._experiments[experiment_id] = ExperimentInfo(
            experiment_id=experiment_id,
            experiment_name=name,
            status=ExperimentStatus.RUNNING,
            created_at=datetime.now(),
            tags=tags or {},
        )

        return experiment_id

    async def get_experiment(self, experiment_id: str) -> ExperimentInfo:
        """Get experiment information."""
        if experiment_id in self._experiments:
            return self._experiments[experiment_id]

        # Try to find experiment directory
        experiment_dir = Path(self._settings.log_dir) / experiment_id
        if experiment_dir.exists():
            return ExperimentInfo(
                experiment_id=experiment_id,
                experiment_name=experiment_id,
                status=ExperimentStatus.RUNNING,
                created_at=datetime.fromtimestamp(experiment_dir.stat().st_ctime),
                tags={},
            )

        raise ValueError(f"Experiment {experiment_id} not found")

    async def list_experiments(
        self,
        max_results: int = 100,
        view_type: str = "ACTIVE_ONLY",
    ) -> list[ExperimentInfo]:
        """List experiments (subdirectories in log directory)."""
        log_dir = Path(self._settings.log_dir)
        if not log_dir.exists():
            return []

        experiments = []
        for exp_dir in log_dir.iterdir():
            if exp_dir.is_dir():
                exp_id = exp_dir.name
                if exp_id in self._experiments:
                    experiments.append(self._experiments[exp_id])
                else:
                    experiments.append(
                        ExperimentInfo(
                            experiment_id=exp_id,
                            experiment_name=exp_id,
                            status=ExperimentStatus.RUNNING,
                            created_at=datetime.fromtimestamp(exp_dir.stat().st_ctime),
                            tags={},
                        )
                    )

        return experiments[:max_results]

    async def delete_experiment(self, experiment_id: str) -> None:
        """Delete an experiment (remove directory)."""
        experiment_dir = Path(self._settings.log_dir) / experiment_id
        if experiment_dir.exists():
            import shutil

            await self._run_sync(shutil.rmtree, str(experiment_dir))

        if experiment_id in self._experiments:
            del self._experiments[experiment_id]

        # Close associated writers
        writers_to_close = [
            run_id
            for run_id, writer in self._writers.items()
            if run_id.startswith(f"{experiment_id}_")
        ]
        for run_id in writers_to_close:
            await self._run_sync(self._writers[run_id].close)
            del self._writers[run_id]

    # Run Management
    async def start_run(
        self,
        experiment_id: str | None = None,
        run_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> str:
        """Start a new experiment run."""
        # Use current experiment or default
        if experiment_id is None:
            experiment_id = (
                self._current_experiment_id or self._settings.default_experiment_name
            )

        # Generate run ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{experiment_id}_{run_name or 'run'}_{timestamp}"

        # Create log directory for this run
        run_dir = (
            Path(self._settings.log_dir)
            / experiment_id
            / (run_name or f"run_{timestamp}")
        )
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create TensorBoard writer
        writer = SummaryWriter(
            log_dir=str(run_dir),
            purge_step=self._settings.purge_step,
            max_queue=self._settings.max_queue,
            flush_secs=self._settings.flush_secs,
            filename_suffix=self._settings.filename_suffix,
        )

        self._writers[run_id] = writer

        # Store run info
        self._runs[run_id] = {
            "run_id": run_id,
            "experiment_id": experiment_id,
            "run_name": run_name,
            "status": "RUNNING",
            "start_time": datetime.now(),
            "params": {},
            "metrics": {},
            "tags": tags or {},
            "log_dir": str(run_dir),
        }

        return run_id

    async def end_run(
        self, run_id: str, status: ExperimentStatus = ExperimentStatus.FINISHED
    ) -> None:
        """End an experiment run."""
        if run_id in self._writers:
            await self._run_sync(self._writers[run_id].close)
            del self._writers[run_id]

        if run_id in self._runs:
            self._runs[run_id]["status"] = status.value.upper()
            self._runs[run_id]["end_time"] = datetime.now()

    async def get_run(self, run_id: str) -> dict[str, Any]:
        """Get run information."""
        if run_id not in self._runs:
            raise ValueError(f"Run {run_id} not found")

        return self._runs[run_id].copy()

    # Parameter and Metric Logging
    async def log_param(self, run_id: str, key: str, value: Any) -> None:
        """Log a parameter."""
        if run_id in self._runs:
            self._runs[run_id]["params"][key] = value

        # TensorBoard doesn't have native parameter logging, use text summary
        if run_id in self._writers:
            writer = self._writers[run_id]
            await self._run_sync(
                writer.add_text,
                f"params/{key}",
                str(value),
                0,
            )

    async def log_params(self, run_id: str, params: dict[str, Any]) -> None:
        """Log multiple parameters."""
        for key, value in params.items():
            await self.log_param(run_id, key, value)

    async def log_metric(
        self,
        run_id: str,
        key: str,
        value: float | int,
        step: int | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Log a metric."""
        if run_id not in self._writers:
            return

        writer = self._writers[run_id]
        step = step or 0

        await self._run_sync(
            writer.add_scalar,
            key,
            float(value),
            step,
        )

        # Update run metrics
        if run_id in self._runs:
            self._runs[run_id]["metrics"][key] = float(value)

    async def log_metrics(
        self,
        run_id: str,
        metrics: dict[str, float | int],
        step: int | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Log multiple metrics."""
        if run_id not in self._writers:
            return

        writer = self._writers[run_id]
        step = step or 0

        # Log scalars
        scalars_dict = {k: float(v) for k, v in metrics.items()}
        await self._run_sync(
            writer.add_scalars,
            "metrics",
            scalars_dict,
            step,
        )

        # Update run metrics
        if run_id in self._runs:
            self._runs[run_id]["metrics"].update(scalars_dict)

    # Artifact Management (Limited TensorBoard support)
    async def log_artifact(
        self,
        run_id: str,
        local_path: str | Path,
        artifact_path: str | None = None,
        artifact_type: ArtifactType = ArtifactType.OTHER,
    ) -> None:
        """Log an artifact (copy to log directory)."""
        if run_id not in self._runs:
            return

        run_info = self._runs[run_id]
        run_dir = Path(run_info["log_dir"])
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        # Copy file to artifacts directory
        local_file = Path(local_path)
        dest_name = artifact_path or local_file.name
        dest_path = artifacts_dir / dest_name

        import shutil

        await self._run_sync(shutil.copy2, str(local_file), str(dest_path))

    async def log_artifacts(
        self,
        run_id: str,
        local_dir: str | Path,
        artifact_path: str | None = None,
    ) -> None:
        """Log multiple artifacts from directory."""
        if run_id not in self._runs:
            return

        run_info = self._runs[run_id]
        run_dir = Path(run_info["log_dir"])
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        # Copy directory contents
        source_dir = Path(local_dir)
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(source_dir)
                dest_path = artifacts_dir / (artifact_path or "") / relative_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                import shutil

                await self._run_sync(shutil.copy2, str(file_path), str(dest_path))

    async def download_artifact(
        self,
        run_id: str,
        artifact_path: str,
        local_path: str | Path,
    ) -> None:
        """Download an artifact."""
        if run_id not in self._runs:
            return

        run_info = self._runs[run_id]
        run_dir = Path(run_info["log_dir"])
        artifact_file = run_dir / "artifacts" / artifact_path

        if artifact_file.exists():
            import shutil

            await self._run_sync(shutil.copy2, str(artifact_file), str(local_path))

    async def list_artifacts(
        self, run_id: str, path: str | None = None
    ) -> list[ArtifactInfo]:
        """List artifacts for a run."""
        if run_id not in self._runs:
            return []

        run_info = self._runs[run_id]
        run_dir = Path(run_info["log_dir"])
        artifacts_dir = run_dir / "artifacts"

        if not artifacts_dir.exists():
            return []

        artifacts = []
        search_dir = artifacts_dir / (path or "")

        for file_path in search_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(artifacts_dir)
                artifacts.append(
                    ArtifactInfo(
                        name=file_path.name,
                        path=str(relative_path),
                        artifact_type=ArtifactType.OTHER,
                        size_bytes=file_path.stat().st_size,
                        created_at=datetime.fromtimestamp(file_path.stat().st_ctime),
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
        # Filter runs by experiment IDs if provided
        runs = []
        for run_id, run_info in self._runs.items():
            if experiment_ids:
                if run_info["experiment_id"] not in experiment_ids:
                    continue
            runs.append(run_info.copy())

        # Simple filtering by run name if filter_string provided
        if filter_string:
            runs = [
                run
                for run in runs
                if filter_string.lower() in (run.get("run_name", "") or "").lower()
            ]

        # Sort if order_by provided
        if order_by and order_by[0] in ["start_time", "run_name"]:
            reverse = order_by[0].startswith("-")
            sort_key = order_by[0].lstrip("-")
            runs.sort(key=lambda x: x.get(sort_key, ""), reverse=reverse)

        return runs[:max_results]


# Create type alias for backward compatibility
Experiment = TensorBoardExperiment

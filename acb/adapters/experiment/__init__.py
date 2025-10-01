"""Experiment Tracking Adapters.

This package provides experiment tracking adapters for various platforms including
MLflow, Weights & Biases (W&B), and TensorBoard. All adapters follow the ACB
adapter pattern with standardized interfaces for experiment management, metrics
logging, parameter tracking, and artifact management.

Supported Platforms:
    - MLflow: Full-featured experiment tracking with MLflow Tracking Server
    - Weights & Biases: Cloud-based experiment tracking with collaboration features
    - TensorBoard: Local experiment tracking with rich visualizations

Usage:
    from acb.adapters import import_adapter

    # Import experiment adapter (dynamic selection based on settings)
    Experiment = import_adapter("experiment")

    # Or import specific implementation
    from acb.adapters.experiment.mlflow import MLflowExperiment
    from acb.adapters.experiment.wandb import WandbExperiment
    from acb.adapters.experiment.tensorboard import TensorBoardExperiment

Configuration:
    Configure experiment tracking in settings/adapters.yml:

    experiment: mlflow     # or wandb, tensorboard

    Adapter-specific settings go in adapter settings files.

Features:
    - Async-first design with connection pooling
    - Standardized experiment lifecycle management
    - Unified metrics and parameter logging interface
    - Artifact management with upload/download support
    - Search and query capabilities across experiments
    - Health checking and error handling
    - Comprehensive metadata tracking

All adapters implement the BaseExperimentAdapter interface providing:
    - Experiment creation, listing, and deletion
    - Run lifecycle management (start, end, get)
    - Parameter and metric logging (single and batch)
    - Artifact management (upload, download, list)
    - Search and query functionality
    - Health checking and connection management
"""

from __future__ import annotations

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

# Import implementations with error handling
try:
    from acb.adapters.experiment.mlflow import (
        MLflowExperiment,
        MLflowExperimentSettings,
    )
except ImportError:
    MLflowExperiment = None
    MLflowExperimentSettings = None

try:
    from acb.adapters.experiment.wandb import WandbExperiment, WandbExperimentSettings
except ImportError:
    WandbExperiment = None
    WandbExperimentSettings = None

try:
    from acb.adapters.experiment.tensorboard import (
        TensorBoardExperiment,
        TensorBoardExperimentSettings,
    )
except ImportError:
    TensorBoardExperiment = None
    TensorBoardExperimentSettings = None

# Export all available classes
__all__ = [
    "ArtifactInfo",
    "ArtifactType",
    # Base classes
    "BaseExperimentAdapter",
    "ExperimentInfo",
    "ExperimentSettings",
    "ExperimentStatus",
    # MLflow
    "MLflowExperiment",
    "MLflowExperimentSettings",
    "MetricEntry",
    "MetricType",
    # TensorBoard
    "TensorBoardExperiment",
    "TensorBoardExperimentSettings",
    # Weights & Biases
    "WandbExperiment",
    "WandbExperimentSettings",
]

# Create mapping for dynamic adapter loading
EXPERIMENT_ADAPTERS = {}

if MLflowExperiment:
    EXPERIMENT_ADAPTERS["mlflow"] = MLflowExperiment

if WandbExperiment:
    EXPERIMENT_ADAPTERS["wandb"] = WandbExperiment

if TensorBoardExperiment:
    EXPERIMENT_ADAPTERS["tensorboard"] = TensorBoardExperiment


def get_experiment_adapter(provider: str) -> type[BaseExperimentAdapter] | None:
    """Get experiment adapter class by provider name.

    Args:
        provider: Provider name (mlflow, wandb, tensorboard)

    Returns:
        Adapter class or None if not available
    """
    return EXPERIMENT_ADAPTERS.get(provider.lower())


def list_available_providers() -> list[str]:
    """List available experiment tracking providers.

    Returns:
        List of available provider names
    """
    return list(EXPERIMENT_ADAPTERS.keys())

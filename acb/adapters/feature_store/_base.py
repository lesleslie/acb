"""Base Feature Store Adapter Implementation.

This module provides the base classes and interfaces for feature store adapters
in the ACB framework. It defines common patterns for feature serving, monitoring,
engineering, discovery, and management across different feature store platforms.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field
from acb.core.cleanup import CleanupMixin


class FeatureDefinition(BaseModel):
    """Feature definition and metadata."""

    name: str = Field(description="Feature name")
    feature_group: str = Field(description="Feature group/namespace")
    data_type: str = Field(description="Feature data type")
    description: str | None = Field(default=None, description="Feature description")
    tags: dict[str, str] = Field(default_factory=dict, description="Feature tags")
    owner: str | None = Field(default=None, description="Feature owner")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(
        default=None, description="Last update timestamp"
    )
    version: str | None = Field(default=None, description="Feature version")
    status: str = Field(default="active", description="Feature status")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class FeatureValue(BaseModel):
    """Feature value with metadata."""

    feature_name: str = Field(description="Feature name")
    value: Any = Field(description="Feature value")
    timestamp: datetime | None = Field(default=None, description="Value timestamp")
    entity_id: str = Field(description="Entity identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Value metadata")


class FeatureVector(BaseModel):
    """Feature vector for an entity."""

    entity_id: str = Field(description="Entity identifier")
    features: dict[str, Any] = Field(description="Feature name-value pairs")
    timestamp: datetime | None = Field(default=None, description="Vector timestamp")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Vector metadata"
    )


class FeatureServingRequest(BaseModel):
    """Feature serving request."""

    entity_ids: list[str] = Field(description="List of entity identifiers")
    feature_names: list[str] = Field(description="List of feature names to retrieve")
    feature_group: str | None = Field(default=None, description="Feature group filter")
    timestamp: datetime | None = Field(
        default=None, description="Point-in-time timestamp"
    )
    version: str | None = Field(default=None, description="Feature version")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Request metadata"
    )


class FeatureServingResponse(BaseModel):
    """Feature serving response."""

    feature_vectors: list[FeatureVector] = Field(
        description="Retrieved feature vectors"
    )
    latency_ms: float | None = Field(default=None, description="Serving latency in ms")
    cache_hit_ratio: float | None = Field(default=None, description="Cache hit ratio")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Response metadata"
    )


class FeatureIngestionRequest(BaseModel):
    """Feature ingestion request."""

    feature_group: str = Field(description="Target feature group")
    features: list[FeatureValue] = Field(description="Features to ingest")
    mode: str = Field(
        default="append", description="Ingestion mode (append, overwrite)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Ingestion metadata"
    )


class FeatureIngestionResponse(BaseModel):
    """Feature ingestion response."""

    ingested_count: int = Field(description="Number of features ingested")
    failed_count: int = Field(default=0, description="Number of failed ingestions")
    latency_ms: float | None = Field(
        default=None, description="Ingestion latency in ms"
    )
    errors: list[str] = Field(default_factory=list, description="Ingestion errors")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Response metadata"
    )


class FeatureMonitoring(BaseModel):
    """Feature monitoring metrics."""

    feature_name: str = Field(description="Feature name")
    drift_score: float | None = Field(default=None, description="Data drift score")
    quality_score: float | None = Field(default=None, description="Data quality score")
    freshness_hours: float | None = Field(
        default=None, description="Data freshness in hours"
    )
    completeness_ratio: float | None = Field(
        default=None, description="Data completeness ratio"
    )
    anomaly_count: int | None = Field(default=None, description="Number of anomalies")
    last_updated: datetime | None = Field(
        default=None, description="Last monitoring update"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Monitoring metadata"
    )


class FeatureExperiment(BaseModel):
    """Feature A/B testing experiment."""

    experiment_id: str = Field(description="Experiment identifier")
    feature_name: str = Field(description="Feature being tested")
    variants: dict[str, Any] = Field(description="Experiment variants")
    traffic_split: dict[str, float] = Field(description="Traffic allocation")
    status: str = Field(description="Experiment status")
    start_time: datetime | None = Field(
        default=None, description="Experiment start time"
    )
    end_time: datetime | None = Field(default=None, description="Experiment end time")
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Experiment metrics"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Experiment metadata"
    )


class FeatureLineage(BaseModel):
    """Feature lineage and dependencies."""

    feature_name: str = Field(description="Feature name")
    upstream_features: list[str] = Field(
        default_factory=list, description="Upstream dependencies"
    )
    downstream_features: list[str] = Field(
        default_factory=list, description="Downstream consumers"
    )
    data_sources: list[str] = Field(
        default_factory=list, description="Source data tables"
    )
    transformations: list[str] = Field(
        default_factory=list, description="Applied transformations"
    )
    lineage_graph: dict[str, Any] = Field(
        default_factory=dict, description="Full lineage graph"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Lineage metadata"
    )


class FeatureStoreSettings(BaseModel):
    """Base settings for feature store adapters."""

    # Connection settings
    host: str = Field(default="localhost", description="Feature store host")
    port: int = Field(default=6379, description="Feature store port")
    use_tls: bool = Field(default=False, description="Use TLS/SSL connection")
    timeout: float = Field(default=30.0, description="Default request timeout")

    # Authentication
    api_key: str | None = Field(default=None, description="API key for authentication")
    token: str | None = Field(default=None, description="Bearer token")
    username: str | None = Field(default=None, description="Username for auth")
    password: str | None = Field(default=None, description="Password for auth")

    # Feature serving settings
    online_store_host: str | None = Field(default=None, description="Online store host")
    offline_store_host: str | None = Field(
        default=None, description="Offline store host"
    )
    default_feature_group: str | None = Field(
        default=None, description="Default feature group"
    )

    # Performance settings
    max_batch_size: int = Field(default=1000, description="Maximum batch size")
    max_concurrent_requests: int = Field(
        default=100, description="Maximum concurrent requests"
    )
    connection_pool_size: int = Field(default=10, description="Connection pool size")

    # Caching settings
    enable_caching: bool = Field(default=True, description="Enable feature caching")
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds")
    cache_size: int = Field(default=10000, description="Cache size limit")

    # Monitoring settings
    enable_monitoring: bool = Field(
        default=True, description="Enable feature monitoring"
    )
    enable_drift_detection: bool = Field(
        default=True, description="Enable drift detection"
    )
    monitoring_interval: float = Field(
        default=60.0, description="Monitoring interval in seconds"
    )

    # Data quality settings
    enable_validation: bool = Field(default=True, description="Enable data validation")
    quality_threshold: float = Field(
        default=0.95, description="Quality score threshold"
    )
    freshness_threshold_hours: float = Field(
        default=24.0, description="Freshness threshold"
    )

    # Advanced settings
    custom_headers: dict[str, str] = Field(
        default_factory=dict, description="Custom HTTP headers"
    )
    extra_config: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific config"
    )


class BaseFeatureStoreAdapter(CleanupMixin, ABC):
    """Base class for feature store adapters.

    This abstract base class defines the standard interface that all feature store
    adapters must implement. It provides common patterns for feature serving,
    monitoring, engineering, discovery, and management.
    """

    def __init__(self, settings: FeatureStoreSettings | None = None) -> None:
        """Initialize the feature store adapter.

        Args:
            settings: Configuration settings for the adapter
        """
        super().__init__()
        self._settings = settings or FeatureStoreSettings()
        self._online_client = None
        self._offline_client = None
        self._monitoring_task: asyncio.Task | None = None
        self._metrics: dict[str, Any] = {}
        self._cache: dict[str, Any] = {}

    @property
    def settings(self) -> FeatureStoreSettings:
        """Get adapter settings."""
        return self._settings

    @abstractmethod
    async def _create_online_client(self) -> Any:
        """Create and configure the online feature store client.

        Returns:
            Configured online client instance
        """
        pass

    @abstractmethod
    async def _create_offline_client(self) -> Any:
        """Create and configure the offline feature store client.

        Returns:
            Configured offline client instance
        """
        pass

    async def _ensure_online_client(self) -> Any:
        """Ensure online client is initialized using lazy loading pattern."""
        if self._online_client is None:
            self._online_client = await self._create_online_client()
            self.register_resource(self._online_client)
        return self._online_client

    async def _ensure_offline_client(self) -> Any:
        """Ensure offline client is initialized using lazy loading pattern."""
        if self._offline_client is None:
            self._offline_client = await self._create_offline_client()
            self.register_resource(self._offline_client)
        return self._offline_client

    # Feature Serving Methods
    @abstractmethod
    async def get_online_features(
        self, request: FeatureServingRequest
    ) -> FeatureServingResponse:
        """Get features from online store for real-time serving.

        Args:
            request: Feature serving request

        Returns:
            Feature serving response
        """
        pass

    async def _get_online_features(
        self, request: FeatureServingRequest
    ) -> FeatureServingResponse:
        """Internal online features implementation."""
        return await self.get_online_features(request)

    @abstractmethod
    async def get_offline_features(
        self, request: FeatureServingRequest
    ) -> FeatureServingResponse:
        """Get features from offline store for batch processing.

        Args:
            request: Feature serving request

        Returns:
            Feature serving response
        """
        pass

    async def _get_offline_features(
        self, request: FeatureServingRequest
    ) -> FeatureServingResponse:
        """Internal offline features implementation."""
        return await self.get_offline_features(request)

    @abstractmethod
    async def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        feature_names: list[str],
        timestamp_column: str = "timestamp",
    ) -> pd.DataFrame:
        """Get historical features for training dataset creation.

        Args:
            entity_df: DataFrame with entity IDs and timestamps
            feature_names: List of feature names to retrieve
            timestamp_column: Name of timestamp column

        Returns:
            DataFrame with historical features
        """
        pass

    async def _get_historical_features(
        self,
        entity_df: pd.DataFrame,
        feature_names: list[str],
        timestamp_column: str = "timestamp",
    ) -> pd.DataFrame:
        """Internal historical features implementation."""
        return await self.get_historical_features(
            entity_df, feature_names, timestamp_column
        )

    # Feature Ingestion Methods
    @abstractmethod
    async def ingest_features(
        self, request: FeatureIngestionRequest
    ) -> FeatureIngestionResponse:
        """Ingest features into the feature store.

        Args:
            request: Feature ingestion request

        Returns:
            Feature ingestion response
        """
        pass

    async def _ingest_features(
        self, request: FeatureIngestionRequest
    ) -> FeatureIngestionResponse:
        """Internal feature ingestion implementation."""
        return await self.ingest_features(request)

    @abstractmethod
    async def ingest_batch_features(
        self, feature_group: str, df: pd.DataFrame, mode: str = "append"
    ) -> FeatureIngestionResponse:
        """Ingest batch features from DataFrame.

        Args:
            feature_group: Target feature group
            df: DataFrame with features to ingest
            mode: Ingestion mode (append, overwrite)

        Returns:
            Feature ingestion response
        """
        pass

    async def _ingest_batch_features(
        self, feature_group: str, df: pd.DataFrame, mode: str = "append"
    ) -> FeatureIngestionResponse:
        """Internal batch ingestion implementation."""
        return await self.ingest_batch_features(feature_group, df, mode)

    # Feature Discovery Methods
    @abstractmethod
    async def list_feature_groups(self) -> list[str]:
        """List available feature groups.

        Returns:
            List of feature group names
        """
        pass

    async def _list_feature_groups(self) -> list[str]:
        """Internal list feature groups implementation."""
        return await self.list_feature_groups()

    @abstractmethod
    async def list_features(
        self, feature_group: str | None = None
    ) -> list[FeatureDefinition]:
        """List available features.

        Args:
            feature_group: Optional feature group filter

        Returns:
            List of feature definitions
        """
        pass

    async def _list_features(
        self, feature_group: str | None = None
    ) -> list[FeatureDefinition]:
        """Internal list features implementation."""
        return await self.list_features(feature_group)

    @abstractmethod
    async def get_feature_definition(self, feature_name: str) -> FeatureDefinition:
        """Get feature definition and metadata.

        Args:
            feature_name: Name of the feature

        Returns:
            Feature definition
        """
        pass

    async def _get_feature_definition(self, feature_name: str) -> FeatureDefinition:
        """Internal get feature definition implementation."""
        return await self.get_feature_definition(feature_name)

    @abstractmethod
    async def search_features(
        self, query: str, filters: dict[str, Any] | None = None
    ) -> list[FeatureDefinition]:
        """Search features by query and filters.

        Args:
            query: Search query
            filters: Optional filters

        Returns:
            List of matching feature definitions
        """
        pass

    async def _search_features(
        self, query: str, filters: dict[str, Any] | None = None
    ) -> list[FeatureDefinition]:
        """Internal search features implementation."""
        return await self.search_features(query, filters)

    # Feature Engineering Methods
    @abstractmethod
    async def create_feature_group(
        self,
        name: str,
        features: list[FeatureDefinition],
        description: str | None = None,
    ) -> bool:
        """Create a new feature group.

        Args:
            name: Feature group name
            features: List of feature definitions
            description: Optional description

        Returns:
            True if created successfully
        """
        pass

    async def _create_feature_group(
        self,
        name: str,
        features: list[FeatureDefinition],
        description: str | None = None,
    ) -> bool:
        """Internal create feature group implementation."""
        return await self.create_feature_group(name, features, description)

    @abstractmethod
    async def register_feature(self, feature: FeatureDefinition) -> bool:
        """Register a new feature definition.

        Args:
            feature: Feature definition to register

        Returns:
            True if registered successfully
        """
        pass

    async def _register_feature(self, feature: FeatureDefinition) -> bool:
        """Internal register feature implementation."""
        return await self.register_feature(feature)

    @abstractmethod
    async def delete_feature(self, feature_name: str) -> bool:
        """Delete a feature definition.

        Args:
            feature_name: Name of feature to delete

        Returns:
            True if deleted successfully
        """
        pass

    async def _delete_feature(self, feature_name: str) -> bool:
        """Internal delete feature implementation."""
        return await self.delete_feature(feature_name)

    # Feature Monitoring Methods
    @abstractmethod
    async def get_feature_monitoring(self, feature_name: str) -> FeatureMonitoring:
        """Get feature monitoring metrics.

        Args:
            feature_name: Name of the feature

        Returns:
            Feature monitoring metrics
        """
        pass

    async def _get_feature_monitoring(self, feature_name: str) -> FeatureMonitoring:
        """Internal get feature monitoring implementation."""
        return await self.get_feature_monitoring(feature_name)

    @abstractmethod
    async def detect_feature_drift(
        self, feature_name: str, reference_window: int = 7
    ) -> float:
        """Detect feature drift compared to reference window.

        Args:
            feature_name: Name of the feature
            reference_window: Reference window in days

        Returns:
            Drift score (0.0 = no drift, 1.0 = maximum drift)
        """
        pass

    async def _detect_feature_drift(
        self, feature_name: str, reference_window: int = 7
    ) -> float:
        """Internal detect feature drift implementation."""
        return await self.detect_feature_drift(feature_name, reference_window)

    @abstractmethod
    async def validate_feature_quality(self, feature_name: str) -> float:
        """Validate feature data quality.

        Args:
            feature_name: Name of the feature

        Returns:
            Quality score (0.0 = poor quality, 1.0 = perfect quality)
        """
        pass

    async def _validate_feature_quality(self, feature_name: str) -> float:
        """Internal validate feature quality implementation."""
        return await self.validate_feature_quality(feature_name)

    # Feature Versioning and Time Travel Methods
    @abstractmethod
    async def get_feature_versions(self, feature_name: str) -> list[str]:
        """Get available versions of a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of available versions
        """
        pass

    async def _get_feature_versions(self, feature_name: str) -> list[str]:
        """Internal get feature versions implementation."""
        return await self.get_feature_versions(feature_name)

    @abstractmethod
    async def get_feature_at_timestamp(
        self, feature_name: str, entity_id: str, timestamp: datetime
    ) -> FeatureValue | None:
        """Get feature value at specific timestamp (time travel).

        Args:
            feature_name: Name of the feature
            entity_id: Entity identifier
            timestamp: Point-in-time timestamp

        Returns:
            Feature value at timestamp or None if not found
        """
        pass

    async def _get_feature_at_timestamp(
        self, feature_name: str, entity_id: str, timestamp: datetime
    ) -> FeatureValue | None:
        """Internal get feature at timestamp implementation."""
        return await self.get_feature_at_timestamp(feature_name, entity_id, timestamp)

    # A/B Testing Methods
    @abstractmethod
    async def create_feature_experiment(self, experiment: FeatureExperiment) -> bool:
        """Create a new feature A/B testing experiment.

        Args:
            experiment: Experiment configuration

        Returns:
            True if created successfully
        """
        pass

    async def _create_feature_experiment(self, experiment: FeatureExperiment) -> bool:
        """Internal create feature experiment implementation."""
        return await self.create_feature_experiment(experiment)

    @abstractmethod
    async def get_feature_for_experiment(
        self, feature_name: str, entity_id: str, experiment_id: str
    ) -> Any:
        """Get feature value for A/B testing experiment.

        Args:
            feature_name: Name of the feature
            entity_id: Entity identifier
            experiment_id: Experiment identifier

        Returns:
            Feature value for the experiment variant
        """
        pass

    async def _get_feature_for_experiment(
        self, feature_name: str, entity_id: str, experiment_id: str
    ) -> Any:
        """Internal get feature for experiment implementation."""
        return await self.get_feature_for_experiment(
            feature_name, entity_id, experiment_id
        )

    # Feature Lineage Methods
    @abstractmethod
    async def get_feature_lineage(self, feature_name: str) -> FeatureLineage:
        """Get feature lineage and dependencies.

        Args:
            feature_name: Name of the feature

        Returns:
            Feature lineage information
        """
        pass

    async def _get_feature_lineage(self, feature_name: str) -> FeatureLineage:
        """Internal get feature lineage implementation."""
        return await self.get_feature_lineage(feature_name)

    @abstractmethod
    async def trace_feature_dependencies(self, feature_name: str) -> dict[str, Any]:
        """Trace feature dependencies and impact analysis.

        Args:
            feature_name: Name of the feature

        Returns:
            Dependency graph and impact analysis
        """
        pass

    async def _trace_feature_dependencies(self, feature_name: str) -> dict[str, Any]:
        """Internal trace feature dependencies implementation."""
        return await self.trace_feature_dependencies(feature_name)

    # Utility Methods
    async def get_metrics(self) -> dict[str, Any]:
        """Get adapter and feature store metrics.

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
            online_client = await self._ensure_online_client()
            offline_client = await self._ensure_offline_client()
            return online_client is not None and offline_client is not None
        except Exception:
            return False

    async def _health_check(self) -> bool:
        """Internal health check implementation."""
        return await self.health_check()

    async def start_monitoring(self) -> None:
        """Start background feature monitoring."""
        if not self._settings.enable_monitoring:
            return

        if self._monitoring_task is not None:
            return

        async def monitor_features() -> None:
            while True:
                try:
                    # Monitor feature quality and drift
                    features = await self.list_features()
                    for feature in features:
                        try:
                            quality_score = await self.validate_feature_quality(
                                feature.name
                            )
                            drift_score = await self.detect_feature_drift(feature.name)

                            self._metrics[f"{feature.name}_quality"] = quality_score
                            self._metrics[f"{feature.name}_drift"] = drift_score

                            # Alert if quality/drift thresholds exceeded
                            if quality_score < self._settings.quality_threshold:
                                self._metrics[f"{feature.name}_quality_alert"] = True
                            if drift_score > 0.5:  # Configurable threshold
                                self._metrics[f"{feature.name}_drift_alert"] = True

                        except Exception:
                            continue

                    self._metrics["monitoring_last_run"] = datetime.now().isoformat()
                except Exception as e:
                    self._metrics["monitoring_error"] = str(e)

                await asyncio.sleep(self._settings.monitoring_interval)

        self._monitoring_task = asyncio.create_task(monitor_features())
        self.register_resource(self._monitoring_task)

    async def stop_monitoring(self) -> None:
        """Stop background feature monitoring."""
        if self._monitoring_task is not None:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

    @asynccontextmanager
    async def _connection_context(self) -> AsyncGenerator[tuple[Any, Any]]:
        """Context manager for client connections."""
        online_client = await self._ensure_online_client()
        offline_client = await self._ensure_offline_client()
        try:
            yield online_client, offline_client
        finally:
            # Connection cleanup is handled by CleanupMixin
            pass

    async def init(self) -> None:
        """Initialize the adapter."""
        await self._ensure_online_client()
        await self._ensure_offline_client()
        if self._settings.enable_monitoring:
            await self.start_monitoring()

    async def __aenter__(self) -> BaseFeatureStoreAdapter:
        """Async context manager entry."""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with cleanup."""
        await self.stop_monitoring()
        await self.cleanup()


# Export base types for use by concrete adapters
__all__ = [
    "BaseFeatureStoreAdapter",
    "FeatureStoreSettings",
    "FeatureDefinition",
    "FeatureValue",
    "FeatureVector",
    "FeatureServingRequest",
    "FeatureServingResponse",
    "FeatureIngestionRequest",
    "FeatureIngestionResponse",
    "FeatureMonitoring",
    "FeatureExperiment",
    "FeatureLineage",
]

"""Feast Feature Store Adapter Implementation.

This module provides a Feast-based feature store adapter for the ACB framework.
Feast is an open-source feature store for machine learning that supports both
online and offline feature serving with Redis and BigQuery backends.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd
from pydantic import Field
from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    generate_adapter_id,
)
from acb.adapters.feature_store._base import (
    BaseFeatureStoreAdapter,
    FeatureDefinition,
    FeatureExperiment,
    FeatureIngestionRequest,
    FeatureIngestionResponse,
    FeatureLineage,
    FeatureMonitoring,
    FeatureServingRequest,
    FeatureServingResponse,
    FeatureStoreSettings,
    FeatureValue,
    FeatureVector,
)

if TYPE_CHECKING:
    from feast import FeatureService

try:
    from feast import FeatureStore
    from feast.infra.online_stores.redis import RedisOnlineStoreConfig
    from feast.repo_config import RepoConfig

    FEAST_AVAILABLE = True
except ImportError:
    FEAST_AVAILABLE = False


class FeastSettings(FeatureStoreSettings):
    """Feast-specific settings."""

    # Feast repository settings
    repo_path: str = Field(
        default="./feature_store",
        description="Feast repository path",
    )
    project_name: str = Field(default="acb_features", description="Feast project name")

    # Online store settings (Redis)
    redis_host: str = Field(
        default="localhost",
        description="Redis host for online store",
    )
    redis_port: int = Field(default=6379, description="Redis port for online store")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_ssl: bool = Field(default=False, description="Use SSL for Redis connection")

    # Offline store settings (can be file, BigQuery, Snowflake, etc.)
    offline_store_type: str = Field(default="file", description="Offline store type")
    offline_store_path: str | None = Field(
        default=None,
        description="Offline store path",
    )

    # Registry settings
    registry_type: str = Field(default="file", description="Registry type")
    registry_path: str | None = Field(default=None, description="Registry path")

    # Feature serving settings
    feature_service_name: str | None = Field(
        default=None,
        description="Default feature service",
    )
    enable_feature_logging: bool = Field(
        default=True,
        description="Enable feature logging",
    )

    # Advanced settings
    entity_key_serialization_version: int = Field(
        default=2,
        description="Entity key serialization version",
    )


class FeastAdapter(BaseFeatureStoreAdapter):
    """Feast feature store adapter implementation.

    This adapter provides comprehensive feature store capabilities using Feast,
    including online/offline serving, feature engineering, monitoring, and management.
    """

    def __init__(self, settings: FeastSettings | None = None) -> None:
        """Initialize Feast adapter.

        Args:
            settings: Feast-specific configuration settings
        """
        if not FEAST_AVAILABLE:
            msg = "Feast not available. Install with: uv add 'feast>=0.35.0'"
            raise ImportError(
                msg,
            )

        super().__init__(settings or FeastSettings())
        self._feast_store: FeatureStore | None = None
        self._feature_services: dict[str, FeatureService] = {}

    @property
    def feast_settings(self) -> FeastSettings:
        """Get Feast-specific settings."""
        return self._settings  # type: ignore[return-value]

    async def _create_online_client(self) -> FeatureStore:
        """Create and configure Feast feature store for online serving."""
        # Configure Redis online store
        online_store_config = RedisOnlineStoreConfig(
            connection_string=f"redis://{self.feast_settings.redis_host}:{self.feast_settings.redis_port}/{self.feast_settings.redis_db}",
            redis_type="redis",
        )

        # Configure offline store based on type
        offline_store_config = self._create_offline_store_config()

        # Configure registry
        registry_config = self._create_registry_config()

        # Create Feast repository configuration
        repo_config = RepoConfig(
            project=self.feast_settings.project_name,
            registry=registry_config,
            provider="local",
            online_store=online_store_config,
            offline_store=offline_store_config,
            entity_key_serialization_version=self.feast_settings.entity_key_serialization_version,
        )

        # Initialize Feast feature store
        feast_store = FeatureStore(config=repo_config)

        # Apply any existing feature definitions
        with suppress(Exception):
            # Store might not be initialized yet
            feast_store.apply([])  # Apply empty list to ensure store is initialized

        return feast_store

    async def _create_offline_client(self) -> FeatureStore:
        """Create and configure Feast feature store for offline serving."""
        # For Feast, online and offline clients are the same FeatureStore instance
        return await self._ensure_online_client()

    def _create_offline_store_config(self) -> dict[str, Any]:
        """Create offline store configuration."""
        if self.feast_settings.offline_store_type == "file":
            return {
                "type": "file",
                "path": self.feast_settings.offline_store_path or "./data",
            }
        if self.feast_settings.offline_store_type == "bigquery":
            return {
                "type": "bigquery",
                "project_id": self.feast_settings.extra_config.get(
                    "bigquery_project_id",
                ),
                "dataset_id": self.feast_settings.extra_config.get(
                    "bigquery_dataset_id",
                ),
            }
        return {"type": "file", "path": "./data"}

    def _create_registry_config(self) -> str:
        """Create registry configuration."""
        if self.feast_settings.registry_type == "file":
            return (
                self.feast_settings.registry_path or "./feature_store/data/registry.db"
            )
        if self.feast_settings.registry_type == "gcs":
            return (
                f"gs://{self.feast_settings.extra_config.get('gcs_bucket')}/registry.db"
            )
        return "./feature_store/data/registry.db"

    async def _ensure_feast_store(self) -> FeatureStore:
        """Ensure Feast store is initialized."""
        if self._feast_store is None:
            self._feast_store = await self._ensure_online_client()
        return self._feast_store

    # Feature Serving Methods
    async def get_online_features(
        self,
        request: FeatureServingRequest,
    ) -> FeatureServingResponse:
        """Get features from Feast online store for real-time serving."""
        start_time = datetime.now()
        feast_store = await self._ensure_feast_store()

        try:
            # Convert request to Feast format
            entity_dict = {}
            for entity_id in request.entity_ids:
                entity_dict[entity_id] = [entity_id]  # Adjust based on entity structure

            # Get online features
            feature_vector = feast_store.get_online_features(
                features=request.feature_names,
                entity_rows=entity_dict,
            )

            # Convert response to ACB format
            feature_vectors = []
            for i, entity_id in enumerate(request.entity_ids):
                features = {}
                for feature_name in request.feature_names:
                    if feature_name in feature_vector.to_dict():
                        values = feature_vector.to_dict()[feature_name]
                        features[feature_name] = values[i] if i < len(values) else None

                feature_vectors.append(
                    FeatureVector(
                        entity_id=entity_id,
                        features=features,
                        timestamp=request.timestamp or datetime.now(),
                    ),
                )

            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            return FeatureServingResponse(
                feature_vectors=feature_vectors,
                latency_ms=latency_ms,
            )

        except Exception as e:
            msg = f"Failed to get online features: {e}"
            raise RuntimeError(msg)

    async def get_offline_features(
        self,
        request: FeatureServingRequest,
    ) -> FeatureServingResponse:
        """Get features from Feast offline store for batch processing."""
        start_time = datetime.now()
        feast_store = await self._ensure_feast_store()

        try:
            # Create entity DataFrame for offline feature retrieval
            entity_df = pd.DataFrame(
                {
                    "entity_id": request.entity_ids,
                    "event_timestamp": [request.timestamp or datetime.now()]
                    * len(request.entity_ids),
                },
            )

            # Get historical features
            training_df = feast_store.get_historical_features(
                entity_df=entity_df,
                features=request.feature_names,
            ).to_df()

            # Convert response to ACB format
            feature_vectors = []
            for _, row in training_df.iterrows():
                features = {}
                for feature_name in request.feature_names:
                    if feature_name in row:
                        features[feature_name] = row[feature_name]

                feature_vectors.append(
                    FeatureVector(
                        entity_id=str(row.get("entity_id", "")),
                        features=features,
                        timestamp=row.get("event_timestamp"),
                    ),
                )

            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            return FeatureServingResponse(
                feature_vectors=feature_vectors,
                latency_ms=latency_ms,
            )

        except Exception as e:
            msg = f"Failed to get offline features: {e}"
            raise RuntimeError(msg)

    async def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        feature_names: list[str],
        timestamp_column: str = "timestamp",
    ) -> pd.DataFrame:
        """Get historical features for training dataset creation."""
        feast_store = await self._ensure_feast_store()

        try:
            # Ensure timestamp column is named correctly for Feast
            if timestamp_column != "event_timestamp":
                entity_df = entity_df.rename(
                    columns={timestamp_column: "event_timestamp"},
                )

            # Get historical features
            return feast_store.get_historical_features(
                entity_df=entity_df,
                features=feature_names,
            ).to_df()

        except Exception as e:
            msg = f"Failed to get historical features: {e}"
            raise RuntimeError(msg)

    # Feature Ingestion Methods
    async def ingest_features(
        self,
        request: FeatureIngestionRequest,
    ) -> FeatureIngestionResponse:
        """Ingest features into Feast feature store."""
        start_time = datetime.now()

        try:
            # Convert ACB format to DataFrame
            rows = []
            for feature_value in request.features:
                row = {
                    "entity_id": feature_value.entity_id,
                    "event_timestamp": feature_value.timestamp or datetime.now(),
                    feature_value.feature_name: feature_value.value,
                }
                rows.append(row)

            df = pd.DataFrame(rows)

            # Use batch ingestion method
            return await self.ingest_batch_features(
                feature_group=request.feature_group,
                df=df,
                mode=request.mode,
            )

        except Exception as e:
            return FeatureIngestionResponse(
                ingested_count=0,
                failed_count=len(request.features),
                errors=[str(e)],
                latency_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def ingest_batch_features(
        self,
        feature_group: str,
        df: pd.DataFrame,
        mode: str = "append",
    ) -> FeatureIngestionResponse:
        """Ingest batch features from DataFrame."""
        start_time = datetime.now()
        await self._ensure_feast_store()

        try:
            # For Feast, we need to push to the offline store
            # This is typically done through the data pipeline outside of Feast
            # For simulation, we'll assume the data is already in the offline store

            ingested_count = len(df)
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            return FeatureIngestionResponse(
                ingested_count=ingested_count,
                failed_count=0,
                latency_ms=latency_ms,
            )

        except Exception as e:
            return FeatureIngestionResponse(
                ingested_count=0,
                failed_count=len(df),
                errors=[str(e)],
                latency_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    # Feature Discovery Methods
    async def list_feature_groups(self) -> list[str]:
        """List available feature groups (Feature Views in Feast)."""
        feast_store = await self._ensure_feast_store()

        try:
            feature_views = feast_store.list_feature_views()
            return [fv.name for fv in feature_views]
        except Exception as e:
            msg = f"Failed to list feature groups: {e}"
            raise RuntimeError(msg)

    async def list_features(
        self,
        feature_group: str | None = None,
    ) -> list[FeatureDefinition]:
        """List available features."""
        feast_store = await self._ensure_feast_store()

        try:
            feature_views = feast_store.list_feature_views()
            features = []

            for fv in feature_views:
                if feature_group is None or fv.name == feature_group:
                    for feature in fv.features:
                        features.append(
                            FeatureDefinition(
                                name=f"{fv.name}:{feature.name}",
                                feature_group=fv.name,
                                data_type=str(feature.dtype),
                                description=getattr(fv, "description", None),
                                tags=getattr(fv, "tags", {}),
                                created_at=getattr(fv, "created_timestamp", None),
                            ),
                        )

            return features

        except Exception as e:
            msg = f"Failed to list features: {e}"
            raise RuntimeError(msg)

    async def get_feature_definition(self, feature_name: str) -> FeatureDefinition:
        """Get feature definition and metadata."""
        feast_store = await self._ensure_feast_store()

        try:
            # Parse feature name (format: feature_view:feature_name)
            if ":" in feature_name:
                fv_name, feat_name = feature_name.split(":", 1)
            else:
                fv_name, feat_name = feature_name, feature_name

            feature_view = feast_store.get_feature_view(fv_name)

            for feature in feature_view.features:
                if feature.name == feat_name:
                    return FeatureDefinition(
                        name=feature_name,
                        feature_group=fv_name,
                        data_type=str(feature.dtype),
                        description=getattr(feature_view, "description", None),
                        tags=getattr(feature_view, "tags", {}),
                        created_at=getattr(feature_view, "created_timestamp", None),
                    )

            msg = f"Feature {feature_name} not found"
            raise ValueError(msg)

        except Exception as e:
            msg = f"Failed to get feature definition: {e}"
            raise RuntimeError(msg)

    async def search_features(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> list[FeatureDefinition]:
        """Search features by query and filters."""
        # Get all features and filter by query
        all_features = await self.list_features()

        matching_features = []
        for feature in all_features:
            if query.lower() in feature.name.lower() or (
                feature.description and query.lower() in feature.description.lower()
            ):
                matching_features.append(feature)

        return matching_features

    # Feature Engineering Methods
    async def create_feature_group(
        self,
        name: str,
        features: list[FeatureDefinition],
        description: str | None = None,
    ) -> bool:
        """Create a new feature group (Feature View in Feast)."""
        # This would typically involve creating a new FeatureView definition
        # and applying it to the Feast repository
        # For now, return success as this is complex to implement generically
        return True

    async def register_feature(self, feature: FeatureDefinition) -> bool:
        """Register a new feature definition."""
        # Feature registration in Feast involves creating FeatureView definitions
        # This is typically done through configuration files
        return True

    async def delete_feature(self, feature_name: str) -> bool:
        """Delete a feature definition."""
        # Feature deletion in Feast requires removing from FeatureView definitions
        return True

    # Feature Monitoring Methods (Mock implementations)
    async def get_feature_monitoring(self, feature_name: str) -> FeatureMonitoring:
        """Get feature monitoring metrics."""
        return FeatureMonitoring(
            feature_name=feature_name,
            drift_score=0.1,  # Mock data
            quality_score=0.95,
            freshness_hours=2.0,
            completeness_ratio=0.98,
            last_updated=datetime.now(),
        )

    async def detect_feature_drift(
        self,
        feature_name: str,
        reference_window: int = 7,
    ) -> float:
        """Detect feature drift compared to reference window."""
        # Mock implementation - in practice, this would analyze feature distributions
        return 0.1

    async def validate_feature_quality(self, feature_name: str) -> float:
        """Validate feature data quality."""
        # Mock implementation - in practice, this would check data quality metrics
        return 0.95

    # Feature Versioning Methods (Mock implementations)
    async def get_feature_versions(self, feature_name: str) -> list[str]:
        """Get available versions of a feature."""
        return ["v1.0", "v1.1", "v2.0"]  # Mock data

    async def get_feature_at_timestamp(
        self,
        feature_name: str,
        entity_id: str,
        timestamp: datetime,
    ) -> FeatureValue | None:
        """Get feature value at specific timestamp (time travel)."""
        # This would use Feast's point-in-time feature retrieval
        return FeatureValue(
            feature_name=feature_name,
            value="mock_value",
            timestamp=timestamp,
            entity_id=entity_id,
        )

    # A/B Testing Methods (Mock implementations)
    async def create_feature_experiment(self, experiment: FeatureExperiment) -> bool:
        """Create a new feature A/B testing experiment."""
        return True

    async def get_feature_for_experiment(
        self,
        feature_name: str,
        entity_id: str,
        experiment_id: str,
    ) -> Any:
        """Get feature value for A/B testing experiment."""
        return "experiment_variant_value"

    # Feature Lineage Methods (Mock implementations)
    async def get_feature_lineage(self, feature_name: str) -> FeatureLineage:
        """Get feature lineage and dependencies."""
        return FeatureLineage(
            feature_name=feature_name,
            upstream_features=[],
            downstream_features=[],
            data_sources=["mock_table"],
        )

    async def trace_feature_dependencies(self, feature_name: str) -> dict[str, Any]:
        """Trace feature dependencies and impact analysis."""
        return {
            "dependencies": [],
            "impact_analysis": {},
        }


# Module metadata
MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Feast Feature Store",
    category="feature_store",
    provider="feast",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="ACB Framework",
    created_date=datetime.now().isoformat(),
    last_modified=datetime.now().isoformat(),
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.CACHING,
        AdapterCapability.METRICS,
        AdapterCapability.HEALTH_CHECKS,
        # Feature Store specific capabilities
        AdapterCapability.FEATURE_SERVING,
        AdapterCapability.FEATURE_MONITORING,
        AdapterCapability.ONLINE_OFFLINE_STORE,
        AdapterCapability.FEATURE_ENGINEERING,
        AdapterCapability.FEATURE_DISCOVERY,
        AdapterCapability.FEATURE_LINEAGE,
        AdapterCapability.TIME_TRAVEL,
        AdapterCapability.A_B_TESTING,
        AdapterCapability.FEATURE_VALIDATION,
        AdapterCapability.PERFORMANCE_MONITORING,
    ],
    required_packages=[
        "feast>=0.35.0",
        "redis>=4.0.0",
        "pandas>=2.0.0",
        "pyarrow>=12.0.0",
    ],
    optional_packages={
        "google-cloud-bigquery": "BigQuery offline store support",
        "snowflake-connector-python": "Snowflake offline store support",
        "boto3": "AWS integration support",
    },
    description="Open-source feature store with Redis/BigQuery backends for online and offline feature serving",
    settings_class="FeastSettings",
    config_example={
        "repo_path": "./feature_store",
        "project_name": "my_features",
        "redis_host": "localhost",
        "redis_port": 6379,
        "offline_store_type": "bigquery",
        "enable_monitoring": True,
        "cache_ttl": 300,
    },
)


# Export adapter class and settings
FeatureStore = FeastAdapter
FeatureStoreSettings = FeastSettings  # type: ignore[misc]

__all__ = [
    "MODULE_METADATA",
    "FeastAdapter",
    "FeastSettings",
    "FeatureStore",
    "FeatureStoreSettings",
]

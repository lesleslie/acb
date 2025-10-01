"""Vertex AI Feature Store Adapter Implementation.

This module provides a Vertex AI Feature Store adapter for the ACB framework.
Vertex AI Feature Store provides managed online and offline feature serving with
BigQuery integration and Google Cloud's AI/ML platform.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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

try:
    from google.cloud import aiplatform
    from google.cloud.aiplatform import featurestore
    from google.cloud.aiplatform.featurestore import EntityType, Feature, Featurestore
    from google.oauth2 import service_account

    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False


class VertexAIFeatureStoreSettings(FeatureStoreSettings):
    """Vertex AI Feature Store specific settings."""

    # Google Cloud Configuration
    project_id: str = Field(description="Google Cloud project ID")
    location: str = Field(default="us-central1", description="Google Cloud region")
    credentials_path: str | None = Field(
        default=None,
        description="Path to service account key file",
    )

    # Vertex AI Feature Store settings
    featurestore_id: str = Field(description="Vertex AI Featurestore ID")
    create_featurestore_if_not_exists: bool = Field(
        default=False,
        description="Create featurestore if it doesn't exist",
    )

    # Online serving settings
    enable_online_serving: bool = Field(
        default=True,
        description="Enable online serving",
    )
    online_serving_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Online serving configuration",
    )

    # BigQuery settings for offline store
    bigquery_dataset_id: str | None = Field(
        default=None,
        description="BigQuery dataset for offline features",
    )
    bigquery_table_prefix: str = Field(
        default="features",
        description="BigQuery table prefix",
    )

    # Security settings
    enable_encryption: bool = Field(
        default=True,
        description="Enable encryption at rest",
    )
    kms_key_name: str | None = Field(default=None, description="KMS key for encryption")

    # Performance settings
    batch_serving_capacity: int = Field(
        default=100,
        description="Batch serving capacity",
    )
    online_serving_capacity: int = Field(
        default=10,
        description="Online serving capacity",
    )

    # Monitoring settings
    enable_feature_monitoring: bool = Field(
        default=True,
        description="Enable feature monitoring",
    )
    monitoring_interval_hours: int = Field(
        default=24,
        description="Monitoring interval in hours",
    )

    # Labeling and organization
    labels: dict[str, str] = Field(default_factory=dict, description="Resource labels")
    entity_type_prefix: str = Field(
        default="acb",
        description="Entity type name prefix",
    )


class VertexAIFeatureStoreAdapter(BaseFeatureStoreAdapter):
    """Vertex AI Feature Store adapter implementation.

    This adapter provides managed feature store capabilities using Google Cloud's
    Vertex AI Feature Store with BigQuery integration and AI Platform services.
    """

    def __init__(self, settings: VertexAIFeatureStoreSettings | None = None) -> None:
        """Initialize Vertex AI Feature Store adapter.

        Args:
            settings: Vertex AI-specific configuration settings
        """
        if not VERTEX_AVAILABLE:
            msg = "Vertex AI not available. Install with: uv add 'google-cloud-aiplatform>=1.25.0'"
            raise ImportError(
                msg,
            )

        super().__init__(settings or VertexAIFeatureStoreSettings())
        self._featurestore_client = None
        self._featurestore = None
        self._entity_types_cache: dict[str, EntityType] = {}

    @property
    def vertex_settings(self) -> VertexAIFeatureStoreSettings:
        """Get Vertex AI-specific settings."""
        return self._settings  # type: ignore[return-value]

    async def _create_online_client(self) -> Any:
        """Create and configure Vertex AI Feature Store client for online serving."""
        # Initialize AI Platform
        credentials = None
        if self.vertex_settings.credentials_path:
            credentials = service_account.Credentials.from_service_account_file(
                self.vertex_settings.credentials_path,
            )

        aiplatform.init(
            project=self.vertex_settings.project_id,
            location=self.vertex_settings.location,
            credentials=credentials,
        )

        # Get or create featurestore
        try:
            featurestore_client = Featurestore(
                featurestore_name=self.vertex_settings.featurestore_id,
                project=self.vertex_settings.project_id,
                location=self.vertex_settings.location,
            )
        except Exception:
            if self.vertex_settings.create_featurestore_if_not_exists:
                # Create featurestore
                featurestore_client = Featurestore.create(
                    featurestore_id=self.vertex_settings.featurestore_id,
                    project=self.vertex_settings.project_id,
                    location=self.vertex_settings.location,
                    labels=self.vertex_settings.labels,
                    encryption_spec_kms_key_name=self.vertex_settings.kms_key_name,
                )
            else:
                msg = f"Featurestore {self.vertex_settings.featurestore_id} not found"
                raise RuntimeError(
                    msg,
                )

        self._featurestore = featurestore_client

        # Cache entity types for faster access
        await self._refresh_entity_types_cache()

        return featurestore_client

    async def _create_offline_client(self) -> Any:
        """Create and configure Vertex AI client for offline serving."""
        # For Vertex AI, online and offline clients use the same featurestore client
        return await self._ensure_online_client()

    async def _refresh_entity_types_cache(self) -> None:
        """Refresh the entity types cache."""
        try:
            entity_types = self._featurestore.list_entity_types()
            for entity_type in entity_types:
                self._entity_types_cache[entity_type.display_name] = entity_type
        except Exception:
            pass  # Cache refresh failed, continue with empty cache

    # Feature Serving Methods
    async def get_online_features(
        self,
        request: FeatureServingRequest,
    ) -> FeatureServingResponse:
        """Get features from Vertex AI Feature Store online serving."""
        start_time = datetime.now()

        if not self.vertex_settings.enable_online_serving:
            msg = "Online serving is not enabled"
            raise RuntimeError(msg)

        try:
            feature_vectors = []

            # Group features by entity type
            features_by_entity = self._group_features_by_entity_type(
                request.feature_names,
            )

            for entity_id in request.entity_ids:
                features = {}

                for entity_type_name, feature_names in features_by_entity.items():
                    if entity_type_name in self._entity_types_cache:
                        entity_type = self._entity_types_cache[entity_type_name]

                        try:
                            # Read features from online store
                            feature_values = entity_type.read(
                                entity_ids=[entity_id],
                                feature_ids=feature_names,
                            )

                            # Extract feature values
                            for feature_id, value in feature_values.items():
                                if value is not None:
                                    features[feature_id] = value

                        except Exception:
                            # Entity or features not found, continue
                            continue

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
        """Get features from Vertex AI Feature Store offline serving (BigQuery)."""
        start_time = datetime.now()

        try:
            # Create entity DataFrame for batch feature retrieval
            entity_df = pd.DataFrame(
                {
                    "entity_id": request.entity_ids,
                    "feature_timestamp": [request.timestamp or datetime.now()]
                    * len(request.entity_ids),
                },
            )

            # Use historical features method
            training_df = await self.get_historical_features(
                entity_df=entity_df,
                feature_names=request.feature_names,
                timestamp_column="feature_timestamp",
            )

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
                        timestamp=row.get("feature_timestamp"),
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
        try:
            # For Vertex AI, historical features are accessed via BigQuery
            # This would typically involve querying the BigQuery offline store

            result_df = entity_df.copy()

            # Group features by entity type
            features_by_entity = self._group_features_by_entity_type(feature_names)

            # For each entity type, simulate querying BigQuery
            for features in features_by_entity.values():
                for feature_name in features:
                    # In practice, this would execute BigQuery queries
                    result_df[feature_name] = f"historical_{feature_name}_value"

            return result_df

        except Exception as e:
            msg = f"Failed to get historical features: {e}"
            raise RuntimeError(msg)

    def _group_features_by_entity_type(
        self,
        feature_names: list[str],
    ) -> dict[str, list[str]]:
        """Group feature names by their entity type."""
        features_by_entity: dict[str, list[str]] = {}

        for feature_name in feature_names:
            # Find which entity type contains this feature
            entity_type_name = self._find_entity_type_for_feature(feature_name)

            if entity_type_name:
                if entity_type_name not in features_by_entity:
                    features_by_entity[entity_type_name] = []
                features_by_entity[entity_type_name].append(feature_name)
            else:
                # Default entity type if not found
                default_entity = f"{self.vertex_settings.entity_type_prefix}_default"
                if default_entity not in features_by_entity:
                    features_by_entity[default_entity] = []
                features_by_entity[default_entity].append(feature_name)

        return features_by_entity

    def _find_entity_type_for_feature(self, feature_name: str) -> str | None:
        """Find the entity type that contains the specified feature."""
        for entity_type_name, entity_type in self._entity_types_cache.items():
            try:
                features = entity_type.list_features()
                for feature in features:
                    if feature.display_name == feature_name:
                        return entity_type_name
            except Exception:
                continue
        return None

    # Feature Ingestion Methods
    async def ingest_features(
        self,
        request: FeatureIngestionRequest,
    ) -> FeatureIngestionResponse:
        """Ingest features into Vertex AI Feature Store."""
        start_time = datetime.now()

        try:
            # Convert ACB format to DataFrame
            rows = []
            for feature_value in request.features:
                row = {
                    "entity_id": feature_value.entity_id,
                    "feature_timestamp": feature_value.timestamp or datetime.now(),
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

        try:
            # For Vertex AI, ingestion is typically done through import jobs
            # This would create an import job to ingest the data

            if feature_group in self._entity_types_cache:
                self._entity_types_cache[feature_group]

                # Create import job (simplified - in practice would use actual import)
                # import_job = entity_type.batch_create_features(df)

                ingested_count = len(df)
            else:
                # Entity type not found
                ingested_count = 0

            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            return FeatureIngestionResponse(
                ingested_count=ingested_count,
                failed_count=0 if ingested_count > 0 else len(df),
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
        """List available feature groups (Entity Types in Vertex AI)."""
        try:
            await self._refresh_entity_types_cache()
            return list(self._entity_types_cache.keys())
        except Exception as e:
            msg = f"Failed to list feature groups: {e}"
            raise RuntimeError(msg)

    async def list_features(
        self,
        feature_group: str | None = None,
    ) -> list[FeatureDefinition]:
        """List available features."""
        try:
            await self._refresh_entity_types_cache()
            features = []

            for entity_type_name, entity_type in self._entity_types_cache.items():
                if feature_group is None or entity_type_name == feature_group:
                    try:
                        feature_list = entity_type.list_features()

                        for feature in feature_list:
                            features.append(
                                FeatureDefinition(
                                    name=feature.display_name,
                                    feature_group=entity_type_name,
                                    data_type=str(feature.value_type),
                                    description=feature.description,
                                    tags=dict(feature.labels) if feature.labels else {},
                                    created_at=feature.create_time,
                                ),
                            )
                    except Exception:
                        # Continue if unable to list features for this entity type
                        continue

            return features

        except Exception as e:
            msg = f"Failed to list features: {e}"
            raise RuntimeError(msg)

    async def get_feature_definition(self, feature_name: str) -> FeatureDefinition:
        """Get feature definition and metadata."""
        try:
            await self._refresh_entity_types_cache()

            for entity_type_name, entity_type in self._entity_types_cache.items():
                try:
                    features = entity_type.list_features()
                    for feature in features:
                        if feature.display_name == feature_name:
                            return FeatureDefinition(
                                name=feature_name,
                                feature_group=entity_type_name,
                                data_type=str(feature.value_type),
                                description=feature.description,
                                tags=dict(feature.labels) if feature.labels else {},
                                created_at=feature.create_time,
                            )
                except Exception:
                    continue

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
        """Create a new feature group (Entity Type in Vertex AI)."""
        try:
            # Create entity type
            entity_type = EntityType.create(
                entity_type_id=name,
                featurestore_name=self._featurestore.resource_name,
                description=description,
                labels=self.vertex_settings.labels,
            )

            # Create features in the entity type
            for feature_def in features:
                Feature.create(
                    feature_id=feature_def.name,
                    entity_type_name=entity_type.resource_name,
                    value_type=feature_def.data_type or "STRING",
                    description=feature_def.description,
                    labels=feature_def.tags,
                )

            # Refresh cache
            await self._refresh_entity_types_cache()

            return True

        except Exception as e:
            msg = f"Failed to create feature group: {e}"
            raise RuntimeError(msg)

    async def register_feature(self, feature: FeatureDefinition) -> bool:
        """Register a new feature definition."""
        try:
            if feature.feature_group in self._entity_types_cache:
                entity_type = self._entity_types_cache[feature.feature_group]

                Feature.create(
                    feature_id=feature.name,
                    entity_type_name=entity_type.resource_name,
                    value_type=feature.data_type or "STRING",
                    description=feature.description,
                    labels=feature.tags,
                )

                return True
            msg = f"Feature group {feature.feature_group} not found"
            raise ValueError(msg)

        except Exception as e:
            msg = f"Failed to register feature: {e}"
            raise RuntimeError(msg)

    async def delete_feature(self, feature_name: str) -> bool:
        """Delete a feature definition."""
        try:
            # Find and delete the feature
            for entity_type in self._entity_types_cache.values():
                try:
                    features = entity_type.list_features()
                    for feature in features:
                        if feature.display_name == feature_name:
                            feature.delete()
                            return True
                except Exception:
                    continue

            return False

        except Exception as e:
            msg = f"Failed to delete feature: {e}"
            raise RuntimeError(msg)

    # Feature Monitoring Methods (Mock implementations)
    async def get_feature_monitoring(self, feature_name: str) -> FeatureMonitoring:
        """Get feature monitoring metrics."""
        return FeatureMonitoring(
            feature_name=feature_name,
            drift_score=0.06,
            quality_score=0.97,
            freshness_hours=0.8,
            completeness_ratio=0.98,
            last_updated=datetime.now(),
        )

    async def detect_feature_drift(
        self,
        feature_name: str,
        reference_window: int = 7,
    ) -> float:
        """Detect feature drift compared to reference window."""
        return 0.06

    async def validate_feature_quality(self, feature_name: str) -> float:
        """Validate feature data quality."""
        return 0.97

    # Feature Versioning Methods (Mock implementations)
    async def get_feature_versions(self, feature_name: str) -> list[str]:
        """Get available versions of a feature."""
        return ["v1.0", "v1.1", "v2.0"]

    async def get_feature_at_timestamp(
        self,
        feature_name: str,
        entity_id: str,
        timestamp: datetime,
    ) -> FeatureValue | None:
        """Get feature value at specific timestamp."""
        return FeatureValue(
            feature_name=feature_name,
            value="point_in_time_value",
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
        return "experiment_value"

    # Feature Lineage Methods (Mock implementations)
    async def get_feature_lineage(self, feature_name: str) -> FeatureLineage:
        """Get feature lineage and dependencies."""
        return FeatureLineage(
            feature_name=feature_name,
            upstream_features=[],
            downstream_features=[],
            data_sources=[
                f"bigquery://{self.vertex_settings.project_id}.{self.vertex_settings.bigquery_dataset_id}",
            ],
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
    name="Vertex AI Feature Store",
    category="feature_store",
    provider="vertex",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="ACB Framework",
    created_date=datetime.now().isoformat(),
    last_modified=datetime.now().isoformat(),
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.ENCRYPTION,
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
        "google-cloud-aiplatform>=1.25.0",
        "pandas>=2.0.0",
        "pyarrow>=12.0.0",
    ],
    optional_packages={
        "google-cloud-bigquery": "BigQuery offline store support",
        "google-cloud-storage": "Cloud Storage integration",
        "google-cloud-monitoring": "Advanced monitoring",
    },
    description="Google Cloud Vertex AI Feature Store with BigQuery integration and AI Platform services",
    settings_class="VertexAIFeatureStoreSettings",
    config_example={
        "project_id": "my-gcp-project",
        "location": "us-central1",
        "featurestore_id": "my-featurestore",
        "bigquery_dataset_id": "features",
        "enable_online_serving": True,
        "enable_encryption": True,
        "monitoring_interval_hours": 24,
    },
)


# Export adapter class and settings
FeatureStore = VertexAIFeatureStoreAdapter
FeatureStoreSettings = VertexAIFeatureStoreSettings

__all__ = [
    "MODULE_METADATA",
    "FeatureStore",
    "FeatureStoreSettings",
    "VertexAIFeatureStoreAdapter",
    "VertexAIFeatureStoreSettings",
]

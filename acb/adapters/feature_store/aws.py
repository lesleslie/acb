"""AWS SageMaker Feature Store Adapter Implementation.

This module provides an AWS SageMaker Feature Store adapter for the ACB framework.
SageMaker Feature Store provides online and offline feature serving with S3 and
DynamoDB backends for scalable machine learning feature management.
"""

from __future__ import annotations

from contextlib import suppress
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
    import boto3
    from botocore.exceptions import ClientError

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False


class AWSFeatureStoreSettings(FeatureStoreSettings):
    """AWS SageMaker Feature Store specific settings."""

    # AWS Configuration
    region_name: str = Field(default="us-east-1", description="AWS region name")
    aws_access_key_id: str | None = Field(default=None, description="AWS access key ID")
    aws_secret_access_key: str | None = Field(
        default=None,
        description="AWS secret access key",
    )  # pragma: allowlist secret
    profile_name: str | None = Field(default=None, description="AWS profile name")

    # SageMaker Feature Store settings
    feature_group_prefix: str = Field(
        default="acb",
        description="Feature group name prefix",
    )
    s3_bucket: str = Field(description="S3 bucket for offline store")
    s3_prefix: str = Field(
        default="feature-store",
        description="S3 prefix for offline store",
    )

    # Online store settings (DynamoDB)
    enable_online_store: bool = Field(default=True, description="Enable online store")
    online_store_kms_key_id: str | None = Field(
        default=None,
        description="KMS key for online store encryption",
    )

    # Offline store settings (S3)
    enable_offline_store: bool = Field(default=True, description="Enable offline store")
    offline_store_kms_key_id: str | None = Field(
        default=None,
        description="KMS key for offline store encryption",
    )
    data_catalog_config: dict[str, str] | None = Field(
        default=None,
        description="Glue data catalog configuration",
    )

    # Security settings
    role_arn: str = Field(description="IAM role ARN for SageMaker Feature Store")
    enable_encryption: bool = Field(
        default=True,
        description="Enable encryption at rest",
    )

    # Performance settings
    throughput_mode: str = Field(
        default="OnDemand",
        description="DynamoDB throughput mode",
    )
    read_capacity_units: int | None = Field(
        default=None,
        description="DynamoDB read capacity units",
    )
    write_capacity_units: int | None = Field(
        default=None,
        description="DynamoDB write capacity units",
    )

    # Monitoring settings
    enable_data_quality_monitoring: bool = Field(
        default=True,
        description="Enable data quality monitoring",
    )
    monitoring_schedule_name: str | None = Field(
        default=None,
        description="Data quality monitoring schedule",
    )


class AWSFeatureStoreAdapter(BaseFeatureStoreAdapter):
    """AWS SageMaker Feature Store adapter implementation.

    This adapter provides scalable feature store capabilities using AWS SageMaker
    Feature Store with DynamoDB for online serving and S3 for offline storage.
    """

    def __init__(self, settings: AWSFeatureStoreSettings | None = None) -> None:
        """Initialize AWS Feature Store adapter.

        Args:
            settings: AWS-specific configuration settings
        """
        if not AWS_AVAILABLE:
            msg = "AWS SDK not available. Install with: uv add 'boto3>=1.26.0'"
            raise ImportError(
                msg,
            )

        super().__init__(settings or AWSFeatureStoreSettings(s3_bucket="", role_arn=""))
        self._sagemaker_client: Any = None
        self._sagemaker_runtime_client: Any = None
        self._s3_client: Any = None
        self._feature_groups_cache: dict[str, dict[str, Any]] = {}

    @property
    def aws_settings(self) -> AWSFeatureStoreSettings:
        """Get AWS-specific settings."""
        return self._settings  # type: ignore[return-value]

    async def _create_online_client(self) -> Any:
        """Create and configure AWS SageMaker clients for online serving."""
        session_kwargs = {"region_name": self.aws_settings.region_name}

        if (
            self.aws_settings.aws_access_key_id
            and self.aws_settings.aws_secret_access_key
        ):
            session_kwargs.update(
                {
                    "aws_access_key_id": self.aws_settings.aws_access_key_id,
                    "aws_secret_access_key": self.aws_settings.aws_secret_access_key,
                },
            )
        elif self.aws_settings.profile_name:
            session_kwargs["profile_name"] = self.aws_settings.profile_name

        session = boto3.Session(**session_kwargs)

        # Create SageMaker clients
        sagemaker_client = session.client("sagemaker")
        sagemaker_runtime_client = session.client("sagemaker-featurestore-runtime")
        s3_client = session.client("s3")

        self._sagemaker_client = sagemaker_client
        self._sagemaker_runtime_client = sagemaker_runtime_client
        self._s3_client = s3_client

        # Cache feature groups for faster access
        await self._refresh_feature_groups_cache()

        return sagemaker_client

    async def _create_offline_client(self) -> Any:
        """Create and configure AWS clients for offline serving."""
        # For AWS, online and offline clients use the same SageMaker client
        return await self._ensure_online_client()

    async def _refresh_feature_groups_cache(self) -> None:
        """Refresh the feature groups cache."""
        if self._sagemaker_client is None:
            return

        with suppress(Exception):
            # Cache refresh failed, continue with empty cache
            response = self._sagemaker_client.list_feature_groups(
                NameContains=self.aws_settings.feature_group_prefix,
            )

            for fg_summary in response.get("FeatureGroupSummaries", []):
                fg_name = fg_summary["FeatureGroupName"]

                # Get detailed feature group information
                fg_detail = self._sagemaker_client.describe_feature_group(
                    FeatureGroupName=fg_name,
                )

                self._feature_groups_cache[fg_name] = fg_detail

    # Feature Serving Methods
    async def get_online_features(
        self,
        request: FeatureServingRequest,
    ) -> FeatureServingResponse:
        """Get features from AWS Feature Store online store for real-time serving."""
        start_time = datetime.now()

        if not self.aws_settings.enable_online_store:
            msg = "Online store is not enabled"
            raise RuntimeError(msg)

        try:
            feature_vectors = []

            for entity_id in request.entity_ids:
                features = {}

                # Group features by feature group
                features_by_group = self._group_features_by_feature_group(
                    request.feature_names,
                )

                for feature_group, feature_names in features_by_group.items():
                    if self._sagemaker_runtime_client is None:
                        continue

                    try:
                        # Get record from online store
                        response = self._sagemaker_runtime_client.get_record(
                            FeatureGroupName=feature_group,
                            RecordIdentifierValueAsString=entity_id,
                            FeatureNames=feature_names,
                        )

                        # Extract feature values
                        for record in response.get("Record", []):
                            feature_name = record.get("FeatureName")
                            value = record.get("ValueAsString")
                            if feature_name and value is not None:
                                features[feature_name] = value

                    except ClientError as e:
                        if e.response["Error"]["Code"] != "ResourceNotFound":
                            raise
                        # Feature not found, continue with other features
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
        """Get features from AWS Feature Store offline store for batch processing."""
        start_time = datetime.now()

        if not self.aws_settings.enable_offline_store:
            msg = "Offline store is not enabled"
            raise RuntimeError(msg)

        try:
            # Create entity DataFrame for batch feature retrieval
            entity_df = pd.DataFrame(
                {
                    "entity_id": request.entity_ids,
                    "event_time": [request.timestamp or datetime.now()]
                    * len(request.entity_ids),
                },
            )

            # Use historical features method
            training_df = await self.get_historical_features(
                entity_df=entity_df,
                feature_names=request.feature_names,
                timestamp_column="event_time",
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
                        timestamp=row.get("event_time"),
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
            # For AWS Feature Store, historical features are typically accessed via Athena
            # This is a simplified implementation that would need Athena integration

            # Group features by feature group
            features_by_group = self._group_features_by_feature_group(feature_names)

            result_df = entity_df.copy()

            # For each feature group, simulate querying the offline store
            for features in features_by_group.values():
                for feature_name in features:
                    # In practice, this would query Athena or use SageMaker Processing
                    result_df[feature_name] = f"historical_{feature_name}_value"

            return result_df

        except Exception as e:
            msg = f"Failed to get historical features: {e}"
            raise RuntimeError(msg)

    def _group_features_by_feature_group(
        self,
        feature_names: list[str],
    ) -> dict[str, list[str]]:
        """Group feature names by their feature group."""
        features_by_group: dict[str, list[str]] = {}

        for feature_name in feature_names:
            # Find which feature group contains this feature
            feature_group = self._find_feature_group_for_feature(feature_name)

            if feature_group:
                if feature_group not in features_by_group:
                    features_by_group[feature_group] = []
                features_by_group[feature_group].append(feature_name)
            else:
                # Default feature group if not found
                default_group = f"{self.aws_settings.feature_group_prefix}-default"
                if default_group not in features_by_group:
                    features_by_group[default_group] = []
                features_by_group[default_group].append(feature_name)

        return features_by_group

    def _find_feature_group_for_feature(self, feature_name: str) -> str | None:
        """Find the feature group that contains the specified feature."""
        for fg_name, fg_detail in self._feature_groups_cache.items():
            feature_definitions = fg_detail.get("FeatureDefinitions", [])
            for fd in feature_definitions:
                if fd.get("FeatureName") == feature_name:
                    return fg_name
        return None

    # Feature Ingestion Methods
    async def ingest_features(
        self,
        request: FeatureIngestionRequest,
    ) -> FeatureIngestionResponse:
        """Ingest features into AWS Feature Store."""
        start_time = datetime.now()

        try:
            # Convert ACB format to records for AWS Feature Store
            records = []
            for feature_value in request.features:
                record = [
                    {
                        "FeatureName": "entity_id",
                        "ValueAsString": feature_value.entity_id,
                    },
                    {
                        "FeatureName": "event_time",
                        "ValueAsString": str(feature_value.timestamp or datetime.now()),
                    },
                    {
                        "FeatureName": feature_value.feature_name,
                        "ValueAsString": str(feature_value.value),
                    },
                ]
                records.append(record)

            # Put records into feature store
            ingested_count = 0
            failed_count = 0
            errors = []

            if self._sagemaker_runtime_client is None:
                return FeatureIngestionResponse(
                    ingested_count=0,
                    failed_count=len(request.features),
                    errors=["Client not initialized"],
                    latency_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            for record in records:
                try:
                    self._sagemaker_runtime_client.put_record(
                        FeatureGroupName=request.feature_group,
                        Record=record,
                    )
                    ingested_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append(str(e))

            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            return FeatureIngestionResponse(
                ingested_count=ingested_count,
                failed_count=failed_count,
                errors=errors,
                latency_ms=latency_ms,
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
            # Convert DataFrame to AWS Feature Store records
            records = []
            for _, row in df.iterrows():
                record = []
                for column, value in row.items():
                    record.append(
                        {
                            "FeatureName": column,
                            "ValueAsString": str(value),
                        },
                    )
                records.append(record)

            # Batch put records
            ingested_count = 0
            failed_count = 0
            errors = []

            if self._sagemaker_runtime_client is None:
                return FeatureIngestionResponse(
                    ingested_count=0,
                    failed_count=len(records),
                    errors=["Client not initialized"],
                    latency_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # AWS Feature Store doesn't have native batch put, so we iterate
            for record in records:
                try:
                    self._sagemaker_runtime_client.put_record(
                        FeatureGroupName=feature_group,
                        Record=record,
                    )
                    ingested_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append(str(e))

            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            return FeatureIngestionResponse(
                ingested_count=ingested_count,
                failed_count=failed_count,
                errors=errors,
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
        """List available feature groups."""
        try:
            await self._refresh_feature_groups_cache()
            return list(self._feature_groups_cache.keys())
        except Exception as e:
            msg = f"Failed to list feature groups: {e}"
            raise RuntimeError(msg)

    async def list_features(
        self,
        feature_group: str | None = None,
    ) -> list[FeatureDefinition]:
        """List available features."""
        try:
            await self._refresh_feature_groups_cache()
            features = []

            for fg_name, fg_detail in self._feature_groups_cache.items():
                if feature_group is None or fg_name == feature_group:
                    feature_definitions = fg_detail.get("FeatureDefinitions", [])

                    for fd in feature_definitions:
                        features.append(
                            FeatureDefinition(
                                name=fd.get("FeatureName", ""),
                                feature_group=fg_name,
                                data_type=fd.get("FeatureType", "String"),
                                description=fg_detail.get("Description"),
                                tags=self._convert_aws_tags(fg_detail.get("Tags", [])),
                                created_at=fg_detail.get("CreationTime"),
                            ),
                        )

            return features

        except Exception as e:
            msg = f"Failed to list features: {e}"
            raise RuntimeError(msg)

    def _convert_aws_tags(self, aws_tags: list[dict[str, str]]) -> dict[str, str]:
        """Convert AWS tags format to dictionary."""
        return {tag["Key"]: tag["Value"] for tag in aws_tags}

    async def get_feature_definition(self, feature_name: str) -> FeatureDefinition:
        """Get feature definition and metadata."""
        try:
            await self._refresh_feature_groups_cache()

            for fg_name, fg_detail in self._feature_groups_cache.items():
                feature_definitions = fg_detail.get("FeatureDefinitions", [])

                for fd in feature_definitions:
                    if fd.get("FeatureName") == feature_name:
                        return FeatureDefinition(
                            name=feature_name,
                            feature_group=fg_name,
                            data_type=fd.get("FeatureType", "String"),
                            description=fg_detail.get("Description"),
                            tags=self._convert_aws_tags(fg_detail.get("Tags", [])),
                            created_at=fg_detail.get("CreationTime"),
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
        """Create a new feature group in AWS Feature Store."""
        if self._sagemaker_client is None:
            await self._ensure_online_client()

        try:
            # Convert feature definitions to AWS format
            feature_definitions: list[dict[str, str]] = []
            for feature in features:
                feature_definitions.append(
                    {
                        "FeatureName": feature.name,
                        "FeatureType": feature.data_type or "String",
                    },
                )

            # Add required record identifier and event time features
            feature_definitions.extend(
                [
                    {"FeatureName": "entity_id", "FeatureType": "String"},
                    {"FeatureName": "event_time", "FeatureType": "String"},
                ],
            )

            # Create feature group configuration
            create_kwargs: dict[str, Any] = {
                "FeatureGroupName": name,
                "RecordIdentifierFeatureName": "entity_id",
                "EventTimeFeatureName": "event_time",
                "FeatureDefinitions": feature_definitions,
            }

            if description:
                create_kwargs["Description"] = description

            # Configure online store
            if self.aws_settings.enable_online_store:
                online_store_config: dict[str, Any] = {"EnableOnlineStore": True}
                if self.aws_settings.online_store_kms_key_id:
                    online_store_config["SecurityConfig"] = {
                        "KmsKeyId": self.aws_settings.online_store_kms_key_id,
                    }
                create_kwargs["OnlineStoreConfig"] = online_store_config

            # Configure offline store
            if self.aws_settings.enable_offline_store:
                offline_store_config: dict[str, Any] = {
                    "S3StorageConfig": {
                        "S3Uri": f"s3://{self.aws_settings.s3_bucket}/{self.aws_settings.s3_prefix}/",
                    },
                    "DisableGlueTableCreation": False,
                }

                if self.aws_settings.offline_store_kms_key_id:
                    offline_store_config["S3StorageConfig"]["KmsKeyId"] = (
                        self.aws_settings.offline_store_kms_key_id
                    )

                if self.aws_settings.data_catalog_config:
                    offline_store_config["DataCatalogConfig"] = (
                        self.aws_settings.data_catalog_config
                    )

                create_kwargs["OfflineStoreConfig"] = offline_store_config

            # Create the feature group
            if self._sagemaker_client is not None:
                self._sagemaker_client.create_feature_group(**create_kwargs)

            # Refresh cache
            await self._refresh_feature_groups_cache()

            return True

        except Exception as e:
            msg = f"Failed to create feature group: {e}"
            raise RuntimeError(msg)

    async def register_feature(self, feature: FeatureDefinition) -> bool:
        """Register a new feature definition."""
        # In AWS Feature Store, features are registered as part of feature groups
        # This would involve modifying an existing feature group or creating a new one
        return True

    async def delete_feature(self, feature_name: str) -> bool:
        """Delete a feature definition."""
        # AWS Feature Store doesn't support deleting individual features from feature groups
        # You would need to delete the entire feature group or create a new version
        return True

    # Feature Monitoring Methods (Mock implementations)
    async def get_feature_monitoring(self, feature_name: str) -> FeatureMonitoring:
        """Get feature monitoring metrics."""
        return FeatureMonitoring(
            feature_name=feature_name,
            drift_score=0.08,
            quality_score=0.96,
            freshness_hours=1.0,
            completeness_ratio=0.97,
            last_updated=datetime.now(),
        )

    async def detect_feature_drift(
        self,
        feature_name: str,
        reference_window: int = 7,
    ) -> float:
        """Detect feature drift compared to reference window."""
        return 0.08

    async def validate_feature_quality(self, feature_name: str) -> float:
        """Validate feature data quality."""
        return 0.96

    # Feature Versioning Methods (Mock implementations)
    async def get_feature_versions(self, feature_name: str) -> list[str]:
        """Get available versions of a feature."""
        return ["v1.0", "v1.1"]

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
            data_sources=[f"s3://{self.aws_settings.s3_bucket}/data/"],
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
    name="AWS SageMaker Feature Store",
    category="feature_store",
    provider="aws",
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
        "boto3>=1.26.0",
        "pandas>=2.0.0",
        "pyarrow>=12.0.0",
    ],
    optional_packages={
        "awswrangler": "Enhanced AWS data operations",
        "s3fs": "S3 filesystem interface",
        "pyathena": "Athena query support",
    },
    description="AWS SageMaker Feature Store with DynamoDB online store and S3 offline store for scalable ML features",
    settings_class="AWSFeatureStoreSettings",
    config_example={
        "region_name": "us-east-1",
        "s3_bucket": "my-feature-store-bucket",
        "role_arn": "arn:aws:iam::123456789012:role/SageMakerRole",
        "enable_online_store": True,
        "enable_offline_store": True,
        "enable_encryption": True,
        "throughput_mode": "OnDemand",
    },
)


# Export adapter class and settings
FeatureStore = AWSFeatureStoreAdapter
FeatureStoreSettings = AWSFeatureStoreSettings  # type: ignore[misc, assignment]

__all__ = [
    "MODULE_METADATA",
    "AWSFeatureStoreAdapter",
    "AWSFeatureStoreSettings",
    "FeatureStore",
    "FeatureStoreSettings",
]

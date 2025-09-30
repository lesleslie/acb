"""Tests for AWS SageMaker Feature Store Adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Optional

from acb.adapters.feature_store.aws import (
    AWSFeatureStoreAdapter,
    AWSFeatureStoreSettings,
)
from acb.adapters.feature_store._base import (
    FeatureDefinition,
    FeatureServingRequest,
    FeatureGroup,
    FeatureDataType,
    FeatureStatus,
)


@pytest.fixture
def aws_settings():
    """Create AWS Feature Store settings for testing."""
    return AWSFeatureStoreSettings(
        region_name="us-east-1",
        role_arn="arn:aws:iam::123456789012:role/SageMakerFeatureStoreRole",
        s3_bucket="test-feature-store-bucket",
        dynamodb_table_prefix="feature-store",
    )


@pytest.fixture
def mock_sagemaker_client():
    """Create mock SageMaker client."""
    mock_client = MagicMock()
    mock_client.describe_feature_group = MagicMock()
    mock_client.list_feature_groups = MagicMock()
    mock_client.create_feature_group = MagicMock()
    mock_client.delete_feature_group = MagicMock()
    return mock_client


@pytest.fixture
def mock_sagemaker_runtime_client():
    """Create mock SageMaker Runtime client."""
    mock_client = MagicMock()
    mock_client.get_record = MagicMock()
    mock_client.batch_get_record = MagicMock()
    return mock_client


class TestAWSFeatureStoreAdapter:
    """Test AWS Feature Store adapter implementation."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, aws_settings):
        """Test AWS adapter initialization."""
        adapter = AWSFeatureStoreAdapter(aws_settings)
        assert adapter.settings == aws_settings
        assert adapter._sagemaker_client is None
        assert adapter._runtime_client is None

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_client_creation(self, mock_boto_client, aws_settings):
        """Test AWS client creation."""
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        adapter = AWSFeatureStoreAdapter(aws_settings)
        clients = await adapter._create_client()

        assert clients["sagemaker"] == mock_sm_client
        assert clients["runtime"] == mock_runtime_client

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_online_feature_serving(self, mock_boto_client, aws_settings):
        """Test online feature serving."""
        # Setup mocks
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        mock_runtime_client.get_record.return_value = {
            "Record": [
                {"FeatureName": "user_age", "ValueAsString": "25"},
                {"FeatureName": "user_location", "ValueAsString": "NYC"},
            ]
        }

        adapter = AWSFeatureStoreAdapter(aws_settings)

        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age", "user_location"],
        )

        response = await adapter.get_online_features(request)

        assert response.entity_id == "user_123"
        assert len(response.features) == 2
        assert "user_age" in response.features
        assert "user_location" in response.features

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_offline_feature_serving(self, mock_boto_client, aws_settings):
        """Test offline feature serving."""
        # Setup mocks
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        # Mock S3 query results
        with patch("pandas.read_parquet") as mock_read_parquet:
            mock_df = MagicMock()
            mock_df.to_dict.return_value = {
                "entity_id": ["user_123"],
                "user_age": [25],
                "user_location": ["NYC"],
                "event_time": [datetime.now()],
            }
            mock_read_parquet.return_value = mock_df

            adapter = AWSFeatureStoreAdapter(aws_settings)

            request = FeatureServingRequest(
                entity_id="user_123",
                feature_names=["user_age", "user_location"],
            )

            vectors = await adapter.get_offline_features(request)
            assert isinstance(vectors, list)

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_feature_registration(self, mock_boto_client, aws_settings):
        """Test feature registration."""
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        mock_sm_client.create_feature_group.return_value = {
            "FeatureGroupArn": "arn:aws:sagemaker:us-east-1:123456789012:feature-group/test-group"
        }

        adapter = AWSFeatureStoreAdapter(aws_settings)

        feature_def = FeatureDefinition(
            name="user_age",
            data_type=FeatureDataType.INTEGER,
            description="User age",
            feature_group="user_features",
            status=FeatureStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        result = await adapter.register_feature(feature_def)
        assert result is True

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_list_features(self, mock_boto_client, aws_settings):
        """Test listing features."""
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        mock_sm_client.list_feature_groups.return_value = {
            "FeatureGroupSummaries": [
                {
                    "FeatureGroupName": "user_features",
                    "FeatureGroupArn": "arn:aws:sagemaker:us-east-1:123456789012:feature-group/user_features",
                    "CreationTime": datetime.now(),
                    "FeatureGroupStatus": "Created",
                }
            ]
        }

        mock_sm_client.describe_feature_group.return_value = {
            "FeatureGroupName": "user_features",
            "FeatureDefinitions": [
                {"FeatureName": "user_age", "FeatureType": "Integral"},
                {"FeatureName": "user_location", "FeatureType": "String"},
            ],
        }

        adapter = AWSFeatureStoreAdapter(aws_settings)
        features = await adapter.list_features()

        assert len(features) == 2
        assert features[0].name == "user_age"
        assert features[1].name == "user_location"

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_feature_group_creation(self, mock_boto_client, aws_settings):
        """Test feature group creation."""
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        mock_sm_client.create_feature_group.return_value = {
            "FeatureGroupArn": "arn:aws:sagemaker:us-east-1:123456789012:feature-group/user_features"
        }

        adapter = AWSFeatureStoreAdapter(aws_settings)

        group = FeatureGroup(
            name="user_features",
            description="User-related features",
            entity_type="user",
            online_store_enabled=True,
            offline_store_enabled=True,
            created_at=datetime.now(),
        )

        result = await adapter.create_feature_group(group)
        assert result is True

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_get_feature_group(self, mock_boto_client, aws_settings):
        """Test getting feature group."""
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        mock_sm_client.describe_feature_group.return_value = {
            "FeatureGroupName": "user_features",
            "Description": "User features",
            "CreationTime": datetime.now(),
            "OnlineStoreConfig": {"EnableOnlineStore": True},
            "OfflineStoreConfig": {"S3StorageConfig": {"S3Uri": "s3://bucket/path"}},
        }

        adapter = AWSFeatureStoreAdapter(aws_settings)
        group = await adapter.get_feature_group("user_features")

        assert group is not None
        assert group.name == "user_features"

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_delete_feature_group(self, mock_boto_client, aws_settings):
        """Test deleting feature group."""
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        mock_sm_client.delete_feature_group.return_value = {}

        adapter = AWSFeatureStoreAdapter(aws_settings)
        result = await adapter.delete_feature_group("user_features")

        assert result is True
        mock_sm_client.delete_feature_group.assert_called_once_with(
            FeatureGroupName="user_features"
        )

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_health_check(self, mock_boto_client, aws_settings):
        """Test health check."""
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        adapter = AWSFeatureStoreAdapter(aws_settings)
        health = await adapter.health_check()

        assert health is True

    @pytest.mark.asyncio
    async def test_context_manager(self, aws_settings):
        """Test adapter as context manager."""
        with patch("boto3.client"):
            adapter = AWSFeatureStoreAdapter(aws_settings)
            async with adapter:
                assert adapter._sagemaker_client is not None
                assert adapter._runtime_client is not None

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_feature_monitoring(self, mock_boto_client, aws_settings):
        """Test feature monitoring."""
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        adapter = AWSFeatureStoreAdapter(aws_settings)
        metrics = await adapter.monitor_features(["user_age"])

        assert metrics.feature_names == ["user_age"]
        assert metrics.request_count >= 0

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_data_quality_validation(self, mock_boto_client, aws_settings):
        """Test data quality validation."""
        mock_sm_client = MagicMock()
        mock_runtime_client = MagicMock()
        mock_boto_client.side_effect = [mock_sm_client, mock_runtime_client]

        adapter = AWSFeatureStoreAdapter(aws_settings)
        result = await adapter.validate_data_quality(["user_age"], "s3://bucket/data")

        assert result.feature_names == ["user_age"]
        assert result.data_source == "s3://bucket/data"

    @pytest.mark.asyncio
    async def test_error_handling(self, aws_settings):
        """Test error handling."""
        with patch("boto3.client", side_effect=Exception("AWS connection failed")):
            adapter = AWSFeatureStoreAdapter(aws_settings)

            health = await adapter.health_check()
            assert health is False


class TestAWSFeatureStoreSettings:
    """Test AWS Feature Store settings."""

    def test_settings_creation(self):
        """Test settings creation."""
        settings = AWSFeatureStoreSettings(
            region_name="us-east-1",
            role_arn="arn:aws:iam::123456789012:role/TestRole",
        )

        assert settings.region_name == "us-east-1"
        assert settings.role_arn == "arn:aws:iam::123456789012:role/TestRole"

    def test_settings_defaults(self):
        """Test settings defaults."""
        settings = AWSFeatureStoreSettings()

        assert settings.region_name == "us-east-1"
        assert settings.enable_online_store is True
        assert settings.enable_offline_store is True
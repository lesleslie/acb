"""Tests for Feature Store Base Implementation."""

import pytest
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from acb.adapters.feature_store._base import (
    BaseFeatureStoreAdapter,
    FeatureStoreSettings,
    FeatureDefinition,
    FeatureValue,
    FeatureVector,
    FeatureServingRequest,
    FeatureServingResponse,
    FeatureGroup,
    FeatureView,
    FeatureMonitoringMetrics,
    DataQualityResult,
    FeatureLineage,
    FeatureExperiment,
    FeatureDataType,
    FeatureStatus,
    DataQualityStatus,
)


class MockFeatureStoreAdapter(BaseFeatureStoreAdapter):
    """Mock feature store adapter for testing."""

    def __init__(self, settings: Optional[FeatureStoreSettings] = None) -> None:
        super().__init__(settings)
        self._mock_client = MagicMock()
        self._features = {}
        self._feature_groups = {}
        self._feature_views = {}

    async def _create_client(self) -> Any:
        """Create mock client."""
        return self._mock_client

    async def get_online_features(
        self, request: FeatureServingRequest
    ) -> FeatureServingResponse:
        """Mock online feature serving."""
        # Create mock feature values
        feature_values = {}
        for feature_name in request.feature_names:
            feature_values[feature_name] = FeatureValue(
                name=feature_name,
                value=f"mock_value_{feature_name}",
                data_type=FeatureDataType.STRING,
                timestamp=datetime.now(),
            )

        return FeatureServingResponse(
            entity_id=request.entity_id,
            features=feature_values,
            metadata={"source": "mock", "latency_ms": 5.0},
        )

    async def get_offline_features(
        self, request: FeatureServingRequest
    ) -> List[FeatureVector]:
        """Mock offline feature serving."""
        return [
            FeatureVector(
                entity_id=request.entity_id,
                features={
                    name: FeatureValue(
                        name=name,
                        value=f"offline_value_{name}",
                        data_type=FeatureDataType.STRING,
                        timestamp=datetime.now(),
                    )
                    for name in request.feature_names
                },
                timestamp=datetime.now(),
            )
        ]

    async def register_feature(self, feature_def: FeatureDefinition) -> bool:
        """Mock feature registration."""
        self._features[feature_def.name] = feature_def
        return True

    async def list_features(
        self, feature_group: Optional[str] = None
    ) -> List[FeatureDefinition]:
        """Mock feature listing."""
        features = list(self._features.values())
        if feature_group:
            features = [f for f in features if f.feature_group == feature_group]
        return features

    async def get_feature(self, feature_name: str) -> Optional[FeatureDefinition]:
        """Mock get feature."""
        return self._features.get(feature_name)

    async def delete_feature(self, feature_name: str) -> bool:
        """Mock feature deletion."""
        if feature_name in self._features:
            del self._features[feature_name]
            return True
        return False

    async def create_feature_group(self, group: FeatureGroup) -> bool:
        """Mock feature group creation."""
        self._feature_groups[group.name] = group
        return True

    async def list_feature_groups(self) -> List[FeatureGroup]:
        """Mock feature group listing."""
        return list(self._feature_groups.values())

    async def get_feature_group(self, group_name: str) -> Optional[FeatureGroup]:
        """Mock get feature group."""
        return self._feature_groups.get(group_name)

    async def delete_feature_group(self, group_name: str) -> bool:
        """Mock feature group deletion."""
        if group_name in self._feature_groups:
            del self._feature_groups[group_name]
            return True
        return False

    async def create_feature_view(self, view: FeatureView) -> bool:
        """Mock feature view creation."""
        self._feature_views[view.name] = view
        return True

    async def list_feature_views(self) -> List[FeatureView]:
        """Mock feature view listing."""
        return list(self._feature_views.values())

    async def get_feature_view(self, view_name: str) -> Optional[FeatureView]:
        """Mock get feature view."""
        return self._feature_views.get(view_name)

    async def delete_feature_view(self, view_name: str) -> bool:
        """Mock feature view deletion."""
        if view_name in self._feature_views:
            del self._feature_views[view_name]
            return True
        return False

    async def monitor_features(
        self, feature_names: List[str], window_hours: int = 24
    ) -> FeatureMonitoringMetrics:
        """Mock feature monitoring."""
        return FeatureMonitoringMetrics(
            feature_names=feature_names,
            window_start=datetime.now() - timedelta(hours=window_hours),
            window_end=datetime.now(),
            request_count=1000,
            avg_latency_ms=10.5,
            p95_latency_ms=25.0,
            error_rate=0.01,
            null_rate=0.05,
            data_freshness_hours=2.0,
            drift_score=0.15,
            metadata={"source": "mock"},
        )

    async def validate_data_quality(
        self, feature_names: List[str], data_source: str
    ) -> DataQualityResult:
        """Mock data quality validation."""
        return DataQualityResult(
            feature_names=feature_names,
            data_source=data_source,
            status=DataQualityStatus.PASSED,
            completeness_score=0.95,
            validity_score=0.98,
            consistency_score=0.92,
            uniqueness_score=0.89,
            anomaly_count=3,
            check_timestamp=datetime.now(),
            issues=[],
            metadata={"total_records": 10000},
        )

    async def get_feature_lineage(self, feature_name: str) -> FeatureLineage:
        """Mock feature lineage."""
        return FeatureLineage(
            feature_name=feature_name,
            upstream_sources=["raw_table", "feature_store"],
            downstream_consumers=["model_a", "model_b"],
            transformations=["aggregate", "normalize"],
            last_updated=datetime.now(),
            metadata={"pipeline": "feature_pipeline_v1"},
        )

    async def create_feature_experiment(self, experiment: FeatureExperiment) -> bool:
        """Mock feature experiment creation."""
        return True

    async def get_feature_experiment_results(
        self, experiment_name: str
    ) -> Dict[str, Any]:
        """Mock feature experiment results."""
        return {
            "experiment_name": experiment_name,
            "status": "completed",
            "control_metrics": {"accuracy": 0.85, "f1": 0.82},
            "treatment_metrics": {"accuracy": 0.87, "f1": 0.84},
            "statistical_significance": True,
            "p_value": 0.03,
        }


@pytest.fixture
def mock_settings():
    """Create mock feature store settings."""
    return FeatureStoreSettings(
        online_store_host="localhost",
        online_store_port=6379,
        offline_store_host="localhost",
        offline_store_port=5432,
    )


@pytest.fixture
def mock_adapter(mock_settings):
    """Create mock feature store adapter."""
    return MockFeatureStoreAdapter(mock_settings)


@pytest.fixture
def sample_feature_definition():
    """Create sample feature definition."""
    return FeatureDefinition(
        name="user_age",
        data_type=FeatureDataType.INTEGER,
        description="User age in years",
        feature_group="user_features",
        status=FeatureStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def sample_feature_group():
    """Create sample feature group."""
    return FeatureGroup(
        name="user_features",
        description="User-related features",
        entity_type="user",
        online_store_enabled=True,
        offline_store_enabled=True,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_feature_view():
    """Create sample feature view."""
    return FeatureView(
        name="user_profile_view",
        description="User profile features for recommendations",
        feature_group="user_features",
        feature_names=["user_age", "user_location"],
        ttl_hours=24,
        created_at=datetime.now(),
    )


class TestBaseFeatureStoreAdapter:
    """Test base feature store adapter functionality."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, mock_settings):
        """Test adapter initialization."""
        adapter = MockFeatureStoreAdapter(mock_settings)
        assert adapter.settings == mock_settings
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_online_feature_serving(self, mock_adapter):
        """Test online feature serving."""
        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age", "user_location"],
        )

        response = await mock_adapter.get_online_features(request)

        assert response.entity_id == "user_123"
        assert len(response.features) == 2
        assert "user_age" in response.features
        assert "user_location" in response.features
        assert response.metadata["source"] == "mock"

    @pytest.mark.asyncio
    async def test_offline_feature_serving(self, mock_adapter):
        """Test offline feature serving."""
        request = FeatureServingRequest(
            entity_id="user_123",
            feature_names=["user_age", "user_location"],
        )

        vectors = await mock_adapter.get_offline_features(request)

        assert len(vectors) == 1
        assert vectors[0].entity_id == "user_123"
        assert len(vectors[0].features) == 2

    @pytest.mark.asyncio
    async def test_feature_registration(self, mock_adapter, sample_feature_definition):
        """Test feature registration."""
        result = await mock_adapter.register_feature(sample_feature_definition)
        assert result is True

        # Verify feature was registered
        features = await mock_adapter.list_features()
        assert len(features) == 1
        assert features[0].name == "user_age"

    @pytest.mark.asyncio
    async def test_feature_management(self, mock_adapter, sample_feature_definition):
        """Test feature CRUD operations."""
        # Create
        await mock_adapter.register_feature(sample_feature_definition)

        # Read
        feature = await mock_adapter.get_feature("user_age")
        assert feature is not None
        assert feature.name == "user_age"

        # List
        features = await mock_adapter.list_features()
        assert len(features) == 1

        # Delete
        result = await mock_adapter.delete_feature("user_age")
        assert result is True

        # Verify deletion
        feature = await mock_adapter.get_feature("user_age")
        assert feature is None

    @pytest.mark.asyncio
    async def test_feature_group_management(self, mock_adapter, sample_feature_group):
        """Test feature group CRUD operations."""
        # Create
        result = await mock_adapter.create_feature_group(sample_feature_group)
        assert result is True

        # Read
        group = await mock_adapter.get_feature_group("user_features")
        assert group is not None
        assert group.name == "user_features"

        # List
        groups = await mock_adapter.list_feature_groups()
        assert len(groups) == 1

        # Delete
        result = await mock_adapter.delete_feature_group("user_features")
        assert result is True

    @pytest.mark.asyncio
    async def test_feature_view_management(self, mock_adapter, sample_feature_view):
        """Test feature view CRUD operations."""
        # Create
        result = await mock_adapter.create_feature_view(sample_feature_view)
        assert result is True

        # Read
        view = await mock_adapter.get_feature_view("user_profile_view")
        assert view is not None
        assert view.name == "user_profile_view"

        # List
        views = await mock_adapter.list_feature_views()
        assert len(views) == 1

        # Delete
        result = await mock_adapter.delete_feature_view("user_profile_view")
        assert result is True

    @pytest.mark.asyncio
    async def test_feature_monitoring(self, mock_adapter):
        """Test feature monitoring."""
        metrics = await mock_adapter.monitor_features(["user_age", "user_location"])

        assert metrics.feature_names == ["user_age", "user_location"]
        assert metrics.request_count == 1000
        assert metrics.avg_latency_ms == 10.5
        assert metrics.p95_latency_ms == 25.0
        assert metrics.error_rate == 0.01

    @pytest.mark.asyncio
    async def test_data_quality_validation(self, mock_adapter):
        """Test data quality validation."""
        result = await mock_adapter.validate_data_quality(
            ["user_age"], "user_table"
        )

        assert result.feature_names == ["user_age"]
        assert result.data_source == "user_table"
        assert result.status == DataQualityStatus.PASSED
        assert result.completeness_score == 0.95

    @pytest.mark.asyncio
    async def test_feature_lineage(self, mock_adapter):
        """Test feature lineage tracking."""
        lineage = await mock_adapter.get_feature_lineage("user_age")

        assert lineage.feature_name == "user_age"
        assert "raw_table" in lineage.upstream_sources
        assert "model_a" in lineage.downstream_consumers

    @pytest.mark.asyncio
    async def test_feature_experiment(self, mock_adapter):
        """Test feature experiment functionality."""
        experiment = FeatureExperiment(
            name="test_experiment",
            description="Test A/B experiment",
            control_features=["user_age"],
            treatment_features=["user_age_normalized"],
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=7),
        )

        result = await mock_adapter.create_feature_experiment(experiment)
        assert result is True

        # Get experiment results
        results = await mock_adapter.get_feature_experiment_results("test_experiment")
        assert results["experiment_name"] == "test_experiment"
        assert results["statistical_significance"] is True

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_adapter):
        """Test adapter as context manager."""
        async with mock_adapter as adapter:
            assert adapter._client is not None

    @pytest.mark.asyncio
    async def test_health_check(self, mock_adapter):
        """Test adapter health check."""
        health = await mock_adapter.health_check()
        assert health is True

    @pytest.mark.asyncio
    async def test_metrics_collection(self, mock_adapter):
        """Test metrics collection."""
        metrics = await mock_adapter.get_metrics()
        assert isinstance(metrics, dict)


class TestFeatureStoreDataModels:
    """Test feature store data models."""

    def test_feature_definition_creation(self):
        """Test feature definition creation."""
        feature = FeatureDefinition(
            name="test_feature",
            data_type=FeatureDataType.FLOAT,
            description="Test feature",
            feature_group="test_group",
            status=FeatureStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert feature.name == "test_feature"
        assert feature.data_type == FeatureDataType.FLOAT
        assert feature.status == FeatureStatus.ACTIVE

    def test_feature_serving_request_validation(self):
        """Test feature serving request validation."""
        request = FeatureServingRequest(
            entity_id="entity_123",
            feature_names=["feature1", "feature2"],
        )

        assert request.entity_id == "entity_123"
        assert len(request.feature_names) == 2

    def test_feature_monitoring_metrics_creation(self):
        """Test feature monitoring metrics creation."""
        metrics = FeatureMonitoringMetrics(
            feature_names=["feature1"],
            window_start=datetime.now(),
            window_end=datetime.now(),
            request_count=100,
            avg_latency_ms=5.0,
            p95_latency_ms=15.0,
            error_rate=0.01,
            null_rate=0.02,
            data_freshness_hours=1.0,
            drift_score=0.1,
        )

        assert metrics.feature_names == ["feature1"]
        assert metrics.request_count == 100
        assert metrics.error_rate == 0.01

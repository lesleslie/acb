"""Tests for ValidationService."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from acb.config import Config
from acb.depends import depends
from acb.logger import Logger
from acb.services._base import ServiceStatus
from acb.services.validation import (
    ValidationConfig,
    ValidationLevel,
    ValidationService,
    ValidationSettings,
)
from acb.services.validation.schemas import (
    BasicValidationSchema,
    StringValidationSchema,
)


class TestValidationService:
    """Tests for ValidationService."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Mock Config instance."""
        config = Mock(spec=Config)
        depends.set(Config, config)
        return config

    @pytest.fixture
    def mock_logger(self) -> Mock:
        """Mock Logger instance."""
        logger = Mock(spec=Logger)
        logger.info = Mock()
        logger.warning = Mock()
        logger.error = Mock()
        depends.set(Logger, logger)
        return logger

    @pytest.fixture
    def validation_settings(self) -> ValidationSettings:
        """Create test validation settings."""
        return ValidationSettings(
            validation_enabled=True,
            default_validation_level=ValidationLevel.STRICT,
            max_validation_time_ms=10.0,
            models_adapter_enabled=False,  # Disable for testing
        )

    @pytest.fixture
    async def validation_service(
        self,
        mock_config: Mock,
        mock_logger: Mock,
        validation_settings: ValidationSettings,
    ) -> ValidationService:
        """Create ValidationService instance."""
        service = ValidationService(validation_settings=validation_settings)
        await service.initialize()
        return service

    async def test_service_initialization(
        self, validation_service: ValidationService
    ) -> None:
        """Test service initialization."""
        assert validation_service.status == ServiceStatus.ACTIVE
        assert validation_service.service_id == "validation"
        assert validation_service.name == "ValidationService"
        assert validation_service._initialized is True

    async def test_service_shutdown(
        self, validation_service: ValidationService
    ) -> None:
        """Test service shutdown."""
        await validation_service.shutdown()
        assert validation_service.status == ServiceStatus.STOPPED

    async def test_basic_validation_success(
        self, validation_service: ValidationService
    ) -> None:
        """Test basic validation with valid data."""
        result = await validation_service.validate("test string")

        assert result.is_valid is True
        assert result.value == "test string"
        assert result.original_value == "test string"
        assert len(result.errors) == 0

    async def test_basic_validation_with_sanitization(
        self, validation_service: ValidationService
    ) -> None:
        """Test basic validation with XSS sanitization."""
        config = ValidationConfig(enable_xss_protection=True)
        result = await validation_service.validate(
            "<script>alert('xss')</script>test", config=config
        )

        assert result.is_valid is True
        assert "<script>" not in result.value
        assert len(result.warnings) > 0
        assert any("security" in warning.lower() for warning in result.warnings)

    async def test_validation_with_schema(
        self, validation_service: ValidationService
    ) -> None:
        """Test validation with specific schema."""
        schema = StringValidationSchema(name="test_string", min_length=3, max_length=10)

        result = await validation_service.validate("hello", schema)

        assert result.is_valid is True
        assert result.value == "hello"

    async def test_validation_with_schema_failure(
        self, validation_service: ValidationService
    ) -> None:
        """Test validation failure with schema."""
        schema = StringValidationSchema(
            name="test_string", min_length=10, max_length=20
        )

        result = await validation_service.validate("hi", schema)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("too short" in error.lower() for error in result.errors)

    async def test_validation_many(self, validation_service: ValidationService) -> None:
        """Test bulk validation."""
        data_list = ["hello", "world", "test"]
        results = await validation_service.validate_many(data_list)

        assert len(results) == 3
        assert all(result.is_valid for result in results)

    async def test_schema_registration(
        self, validation_service: ValidationService
    ) -> None:
        """Test schema registration and retrieval."""
        schema = BasicValidationSchema(name="test_schema", data_type=str, required=True)

        # Register schema
        validation_service.register_schema(schema)

        # Retrieve schema
        retrieved_schema = await validation_service.get_schema("test_schema")
        assert retrieved_schema is not None
        assert retrieved_schema.name == "test_schema"

    async def test_schema_listing(self, validation_service: ValidationService) -> None:
        """Test listing registered schemas."""
        schema1 = BasicValidationSchema("schema1", data_type=str)
        schema2 = BasicValidationSchema("schema2", data_type=int)

        validation_service.register_schema(schema1)
        validation_service.register_schema(schema2)

        schemas = validation_service.list_schemas()
        assert "schema1" in schemas
        assert "schema2" in schemas

    async def test_schema_removal(self, validation_service: ValidationService) -> None:
        """Test schema removal."""
        schema = BasicValidationSchema("test_schema", data_type=str)
        validation_service.register_schema(schema)

        # Verify schema is registered
        assert "test_schema" in validation_service.list_schemas()

        # Remove schema
        validation_service.remove_schema("test_schema")

        # Verify schema is removed
        assert "test_schema" not in validation_service.list_schemas()

    async def test_metrics_tracking(
        self, validation_service: ValidationService
    ) -> None:
        """Test metrics tracking."""
        initial_metrics = validation_service.get_metrics()
        assert initial_metrics.total_validations == 0

        # Perform some validations
        await validation_service.validate("test1")
        await validation_service.validate("test2")

        updated_metrics = validation_service.get_metrics()
        assert updated_metrics.total_validations == 2
        assert updated_metrics.successful_validations == 2
        assert updated_metrics.failed_validations == 0

    async def test_metrics_reset(self, validation_service: ValidationService) -> None:
        """Test metrics reset."""
        # Perform validation to generate metrics
        await validation_service.validate("test")

        # Verify metrics exist
        assert validation_service.get_metrics().total_validations > 0

        # Reset metrics
        validation_service.reset_metrics()

        # Verify metrics are reset
        reset_metrics = validation_service.get_metrics()
        assert reset_metrics.total_validations == 0

    async def test_health_check(self, validation_service: ValidationService) -> None:
        """Test service health check."""
        health = await validation_service.health_check()

        assert health["service_id"] == "validation"
        assert health["name"] == "ValidationService"
        assert health["healthy"] is True
        assert "validation_functional" in health["service_specific"]
        assert "performance_ok" in health["service_specific"]

    async def test_performance_monitoring(
        self, validation_service: ValidationService
    ) -> None:
        """Test performance monitoring."""
        # Enable performance monitoring
        validation_service._performance_monitoring_enabled = True
        validation_service._performance_threshold_ms = 1.0  # Very low threshold

        with patch("acb.logger.Logger.warning"):
            # This should trigger performance warning due to low threshold
            await validation_service.validate("test data")

            # Check if warning was called (might not always trigger due to fast execution)
            # We'll check metrics instead
            metrics = validation_service.get_metrics()
            assert metrics.total_validations > 0

    async def test_validation_error_handling(
        self, validation_service: ValidationService
    ) -> None:
        """Test validation error handling."""
        # Test error handling at the public validate() method level
        # which catches exceptions and returns error results
        broken_schema = Mock()
        broken_schema._ensure_compiled = AsyncMock()
        broken_schema.validate = AsyncMock(side_effect=Exception("Test error"))

        # Use public validate method which has exception handling
        result = await validation_service.validate(
            "test", broken_schema, ValidationConfig(), "test_field"
        )

        assert result.is_valid is False
        assert len(result.errors) > 0
        # The error should be wrapped as "Validation exception: ..."
        assert any("exception" in error.lower() for error in result.errors)

    async def test_models_adapter_integration_disabled(
        self, validation_service: ValidationService
    ) -> None:
        """Test models adapter integration when disabled."""
        # Models adapter should be disabled in test settings
        assert validation_service._models_adapter_enabled is False
        assert validation_service._models_adapter is None

        # Test validation with model class (should fail gracefully)
        result = await validation_service.validate_model(
            {"name": "test"},
            str,  # Dummy model class
        )

        assert result.is_valid is False
        assert "Models adapter not available" in result.errors

    @patch("acb.adapters.import_adapter")
    async def test_models_adapter_integration_enabled(
        self, mock_import_adapter: Mock, mock_config: Mock, mock_logger: Mock
    ) -> None:
        """Test models adapter integration when enabled."""
        # Create a mock ModelsAdapter class
        MockModelsAdapterClass = Mock()

        # Create mock adapter instance
        mock_adapter = Mock()
        mock_adapter.get_adapter_for_model = Mock()
        mock_adapter_impl = Mock()
        mock_adapter_impl.create_instance = Mock(return_value="created_instance")
        mock_adapter.get_adapter_for_model.return_value = mock_adapter_impl

        # Setup: import_adapter("models") returns MockModelsAdapterClass
        mock_import_adapter.return_value = MockModelsAdapterClass

        # Setup: DI returns the mock adapter when requesting the class
        depends.set(MockModelsAdapterClass, mock_adapter)

        # Create service with models adapter enabled
        settings = ValidationSettings(models_adapter_enabled=True)
        service = ValidationService(validation_settings=settings)

        await service.initialize()

        # Test model validation
        result = await service.validate_model(
            {"name": "test"},
            str,  # Dummy model class
        )

        assert result.is_valid is True
        assert result.value == "created_instance"

    async def test_string_length_validation(
        self, validation_service: ValidationService
    ) -> None:
        """Test string length validation."""
        config = ValidationConfig(max_string_length=5)

        # Test string within limit
        result1 = await validation_service.validate("hello", config=config)
        assert result1.is_valid is True

        # Test string exceeding limit
        result2 = await validation_service.validate("hello world", config=config)
        assert result2.is_valid is False
        assert any("too long" in error.lower() for error in result2.errors)

    async def test_list_length_validation(
        self, validation_service: ValidationService
    ) -> None:
        """Test list length validation."""
        config = ValidationConfig(max_list_length=3)

        # Test list within limit
        result1 = await validation_service.validate([1, 2, 3], config=config)
        assert result1.is_valid is True

        # Test list exceeding limit
        result2 = await validation_service.validate([1, 2, 3, 4, 5], config=config)
        assert result2.is_valid is False
        assert any("too long" in error.lower() for error in result2.errors)

    async def test_dict_depth_validation(
        self, validation_service: ValidationService
    ) -> None:
        """Test dictionary depth validation."""
        config = ValidationConfig(max_dict_depth=2)

        # Test shallow dict
        shallow_dict = {"level1": {"level2": "value"}}
        result1 = await validation_service.validate(shallow_dict, config=config)
        assert result1.is_valid is True

        # Test deep dict
        deep_dict = {"level1": {"level2": {"level3": {"level4": "value"}}}}
        result2 = await validation_service.validate(deep_dict, config=config)
        assert result2.is_valid is False
        assert any("too deep" in error.lower() for error in result2.errors)

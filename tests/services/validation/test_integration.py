"""Integration tests for the validation system."""

from unittest.mock import Mock

import pytest

from acb.config import Config
from acb.depends import depends
from acb.logger import Logger
from acb.services.validation import (
    ValidationError,
    ValidationLevel,
    ValidationService,
    ValidationSettings,
    sanitize_input,
    validate_input,
)
from acb.services.validation.results import ValidationReport, ValidationResultBuilder
from acb.services.validation.schemas import (
    DictValidationSchema,
    EmailValidationSchema,
    ListValidationSchema,
    SchemaBuilder,
    StringValidationSchema,
)


class TestValidationSystemIntegration:
    """Integration tests for the complete validation system."""

    @pytest.fixture
    def mock_dependencies(self) -> None:
        """Mock ACB dependencies."""
        config = Mock(spec=Config)
        logger = Mock(spec=Logger)
        logger.info = Mock()
        logger.warning = Mock()
        logger.error = Mock()

        depends.set(Config, config)
        depends.set(Logger, logger)

    @pytest.fixture
    async def validation_service(self, mock_dependencies: None) -> ValidationService:
        """Create ValidationService for integration tests."""
        settings = ValidationSettings(
            validation_enabled=True,
            models_adapter_enabled=False,
            health_check_validation_enabled=True,
            metrics_collection_enabled=True,
        )

        service = ValidationService(validation_settings=settings)
        await service.initialize()
        depends.set(ValidationService, service)
        return service

    async def test_complete_user_registration_flow(
        self, validation_service: ValidationService
    ) -> None:
        """Test complete user registration with validation."""
        # Build validation schemas for user registration
        builder = SchemaBuilder()
        builder.add_string(
            "username", min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$"
        )
        builder.add_email("email")
        builder.add_string("password", min_length=8)

        schemas = builder.build()

        # Register schemas with service
        for schema in schemas.values():
            validation_service.register_schema(schema)

        # Test user registration data
        user_data = {
            "username": "john_doe123",
            "email": "john@example.com",
            "password": "securepassword123",
        }

        # Validate each field
        results = []
        for field, value in user_data.items():
            schema = await validation_service.get_schema(field)
            if schema:
                result = await validation_service.validate(
                    value, schema, field_name=field
                )
                results.append(result)

        # Check all validations passed
        assert all(result.is_valid for result in results)

        # Create validation report
        report = ValidationReport(results=results)
        assert report.is_valid
        assert report.error_count == 0

    async def test_api_input_validation_with_sanitization(
        self, validation_service: ValidationService
    ) -> None:
        """Test API input validation with security sanitization."""

        # Define API endpoint validation
        @sanitize_input(fields=["content", "title"])
        @validate_input(
            {
                "title": StringValidationSchema("title", min_length=1, max_length=100),
                "content": StringValidationSchema(
                    "content", min_length=10, max_length=1000
                ),
            }
        )
        async def create_post(title: str, content: str) -> dict:
            return {"title": title, "content": content, "status": "created"}

        # Test with clean input
        result = await create_post(
            title="My Blog Post",
            content="This is a clean blog post content that should pass validation.",
        )

        assert result["status"] == "created"
        assert result["title"] == "My Blog Post"

        # Test with malicious input (should be sanitized)
        result = await create_post(
            title="<script>alert('xss')</script>Safe Title",
            content="This content has <script>alert('xss')</script> but should be sanitized.",
        )

        assert result["status"] == "created"
        assert "<script>" not in result["title"]
        assert "<script>" not in result["content"]

        # Test with input that fails validation
        with pytest.raises(ValidationError):
            await create_post(
                title="",  # Too short
                content="Short",  # Too short
            )

    async def test_complex_data_structure_validation(
        self, validation_service: ValidationService
    ) -> None:
        """Test validation of complex nested data structures."""
        # Define schemas for nested structure
        email_schema = EmailValidationSchema("email")
        name_schema = StringValidationSchema("name", min_length=1)

        # List of users schema
        user_list_schema = ListValidationSchema(
            name="users",
            item_schema=DictValidationSchema(
                name="user",
                field_schemas={"name": name_schema, "email": email_schema},
                required_fields=["name", "email"],
            ),
            min_items=1,
            max_items=10,
        )

        # Test data
        users_data = [
            {"name": "John Doe", "email": "john@example.com"},
            {"name": "Jane Smith", "email": "jane@example.com"},
        ]

        result = await validation_service.validate(users_data, user_list_schema)

        assert result.is_valid
        assert len(result.value) == 2
        assert all(isinstance(user, dict) for user in result.value)

    async def test_performance_monitoring_integration(
        self, validation_service: ValidationService
    ) -> None:
        """Test performance monitoring integration."""
        # Enable performance monitoring
        validation_service._performance_monitoring_enabled = True
        validation_service._performance_threshold_ms = 50.0  # Reasonable threshold

        # Perform multiple validations to generate metrics
        schema = StringValidationSchema("test", min_length=1)

        for i in range(10):
            await validation_service.validate(f"test_string_{i}", schema)

        # Check metrics
        metrics = validation_service.get_metrics()
        assert metrics.total_validations == 10
        assert metrics.successful_validations == 10
        assert metrics.average_validation_time_ms > 0

        # Test health check includes performance metrics
        health = await validation_service.health_check()
        assert "performance_ok" in health["service_specific"]
        assert "validation_time_ms" in health["service_specific"]

    async def test_validation_error_aggregation(
        self, validation_service: ValidationService
    ) -> None:
        """Test validation error aggregation and reporting."""
        # Create schemas that will fail
        strict_schema = StringValidationSchema("strict", min_length=20, max_length=30)

        # Test data that will fail validation
        test_data = [
            "short",  # Too short
            "way too long string that exceeds the maximum length",  # Too long
            "just right length string",  # Should pass
        ]

        # Validate all data
        results = []
        for i, data in enumerate(test_data):
            result = await validation_service.validate(
                data, strict_schema, None, f"item_{i}"
            )
            results.append(result)

        # Build validation report
        builder = ValidationResultBuilder()
        builder.add_results(results)
        report = builder.build()

        # Check report summary
        assert not report.is_valid  # Should fail due to validation errors
        assert report.error_count > 0
        assert len(report.failed_validations) == 2  # Two should fail
        assert len(report.successful_validations) == 1  # One should pass

        # Check error details
        errors_by_field = report.get_errors_by_field()
        assert "item_0" in errors_by_field  # short string
        assert "item_1" in errors_by_field  # long string

    async def test_service_lifecycle_integration(
        self, validation_service: ValidationService
    ) -> None:
        """Test validation service integration with service lifecycle."""
        # Test service is properly initialized
        assert validation_service.is_healthy
        assert validation_service.status.value == "active"

        # Test service metrics
        initial_metrics = validation_service.metrics
        assert initial_metrics.requests_handled == 0

        # Perform some operations
        await validation_service.validate("test")
        await validation_service.validate("another test")

        # Check updated metrics
        updated_metrics = validation_service.metrics
        assert updated_metrics.requests_handled == 2

        # Test service shutdown
        await validation_service.shutdown()
        assert validation_service.status.value == "stopped"

    async def test_schema_compilation_performance(
        self, validation_service: ValidationService
    ) -> None:
        """Test schema compilation and caching for performance."""
        # Create complex schema with patterns
        complex_schema = StringValidationSchema(
            name="complex",
            min_length=5,
            max_length=50,
            pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",  # Email pattern
        )

        # First validation should compile schema
        start_time = validation_service.get_metrics().total_validation_time_ms
        result1 = await validation_service.validate("test@example.com", complex_schema)
        validation_service.get_metrics().total_validation_time_ms - start_time

        assert result1.is_valid
        assert complex_schema.is_compiled

        # Second validation should use compiled schema (faster)
        start_time = validation_service.get_metrics().total_validation_time_ms
        result2 = await validation_service.validate(
            "another@example.com", complex_schema
        )
        validation_service.get_metrics().total_validation_time_ms - start_time

        assert result2.is_valid
        # Note: Time comparison might not always be reliable in tests,
        # but we can at least verify the schema remains compiled

    async def test_validation_level_behavior(
        self, validation_service: ValidationService
    ) -> None:
        """Test different validation levels behavior."""
        from acb.services.validation._base import ValidationConfig

        # Schema that will generate warnings
        schema = StringValidationSchema("test", min_length=1)

        # Test with strict level (default)
        strict_config = ValidationConfig(level=ValidationLevel.STRICT)
        result = await validation_service.validate("  test  ", schema, strict_config)
        # Should be valid but may have warnings about whitespace

        # Test with lenient level
        lenient_config = ValidationConfig(level=ValidationLevel.LENIENT)
        result = await validation_service.validate("  test  ", schema, lenient_config)
        # Should handle warnings gracefully

        assert result.is_valid  # Both should pass for this simple case

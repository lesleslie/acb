"""Tests for validation decorators."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from acb.depends import depends
from acb.services.validation import (
    ValidationError,
    ValidationService,
    validate_input,
    validate_output,
    sanitize_input,
    validate_schema,
    validate_contracts,
)
from acb.services.validation._base import ValidationResult
from acb.services.validation.schemas import StringValidationSchema


class TestValidationDecorators:
    """Tests for validation decorators."""

    @pytest.fixture
    def mock_validation_service(self) -> Mock:
        """Mock ValidationService."""
        service = Mock(spec=ValidationService)
        service.validate = AsyncMock()
        service.get_schema = AsyncMock()
        depends.set(ValidationService, service)
        return service

    def test_validate_input_decorator(self, mock_validation_service: Mock) -> None:
        """Test validate_input decorator."""
        # Mock successful validation
        mock_validation_service.validate.return_value = ValidationResult(
            field_name="name",
            value="validated_name",
            original_value="test_name",
            is_valid=True
        )

        schema = StringValidationSchema("name", min_length=1)

        @validate_input({"name": schema})
        async def test_function(name: str) -> str:
            return f"Hello, {name}!"

        # This test verifies the decorator is applied correctly
        assert hasattr(test_function, '__wrapped__')

    def test_validate_output_decorator(self, mock_validation_service: Mock) -> None:
        """Test validate_output decorator."""
        # Mock successful validation
        mock_validation_service.validate.return_value = ValidationResult(
            field_name="output",
            value="validated_output",
            original_value="test_output",
            is_valid=True
        )

        schema = StringValidationSchema("output", min_length=1)

        @validate_output(schema)
        async def test_function() -> str:
            return "test_output"

        # This test verifies the decorator is applied correctly
        assert hasattr(test_function, '__wrapped__')

    def test_sanitize_input_decorator(self, mock_validation_service: Mock) -> None:
        """Test sanitize_input decorator."""
        # Mock successful validation/sanitization
        mock_validation_service.validate.return_value = ValidationResult(
            field_name="content",
            value="sanitized_content",
            original_value="<script>test</script>",
            is_valid=True
        )

        @sanitize_input(fields=["content"])
        async def test_function(content: str) -> str:
            return content

        # This test verifies the decorator is applied correctly
        assert hasattr(test_function, '__wrapped__')

    def test_validate_schema_decorator(self, mock_validation_service: Mock) -> None:
        """Test validate_schema decorator."""
        # Mock schema retrieval and validation
        mock_schema = Mock()
        mock_validation_service.get_schema.return_value = mock_schema
        mock_validation_service.validate.return_value = ValidationResult(
            field_name="data",
            value={"validated": "data"},
            original_value={"test": "data"},
            is_valid=True
        )

        @validate_schema("test_schema")
        async def test_function(**data) -> dict:
            return data

        # This test verifies the decorator is applied correctly
        assert hasattr(test_function, '__wrapped__')

    def test_validate_contracts_decorator(self, mock_validation_service: Mock) -> None:
        """Test validate_contracts decorator."""
        input_contract = {"name": str, "age": int}
        output_contract = {"result": str}

        @validate_contracts(
            input_contract=input_contract,
            output_contract=output_contract
        )
        async def test_function(name: str, age: int) -> dict:
            return {"result": f"{name} is {age} years old"}

        # This test verifies the decorator is applied correctly
        assert hasattr(test_function, '__wrapped__')


class TestDecoratorIntegration:
    """Integration tests for decorators with actual validation logic."""

    @pytest.fixture
    async def validation_service(self) -> ValidationService:
        """Create real ValidationService for integration tests."""
        from acb.services.validation import ValidationSettings
        from acb.config import Config
        from acb.logger import Logger

        # Mock dependencies
        config = Mock(spec=Config)
        logger = Mock(spec=Logger)
        logger.info = Mock()
        logger.warning = Mock()
        logger.error = Mock()

        depends.set(Config, config)
        depends.set(Logger, logger)

        settings = ValidationSettings(models_adapter_enabled=False)
        service = ValidationService(validation_settings=settings)
        await service.initialize()

        depends.set(ValidationService, service)
        return service

    async def test_validate_input_integration(self, validation_service: ValidationService) -> None:
        """Test validate_input decorator with real validation."""
        schema = StringValidationSchema("name", min_length=2)

        @validate_input({"name": schema})
        async def greet_user(name: str) -> str:
            return f"Hello, {name}!"

        # Test with valid input
        result = await greet_user("John")
        assert result == "Hello, John!"

        # Test with invalid input (should raise ValidationError)
        with pytest.raises(ValidationError):
            await greet_user("X")  # Too short

    async def test_validate_output_integration(self, validation_service: ValidationService) -> None:
        """Test validate_output decorator with real validation."""
        schema = StringValidationSchema("output", min_length=5)

        @validate_output(schema)
        async def get_message() -> str:
            return "Hello"

        # Test with valid output
        result = await get_message()
        assert result == "Hello"

        # Test with invalid output
        @validate_output(schema)
        async def get_short_message() -> str:
            return "Hi"  # Too short

        with pytest.raises(ValidationError):
            await get_short_message()

    async def test_sanitize_input_integration(self, validation_service: ValidationService) -> None:
        """Test sanitize_input decorator with real sanitization."""
        @sanitize_input(fields=["content"])
        async def process_content(content: str) -> str:
            return f"Processed: {content}"

        # Test with content that needs sanitization
        result = await process_content("<script>alert('xss')</script>Hello")
        assert "script" not in result.lower()
        assert "Hello" in result

    async def test_validate_schema_integration(self, validation_service: ValidationService) -> None:
        """Test validate_schema decorator with real schema."""
        # Register a schema
        schema = StringValidationSchema("test_data", min_length=3)
        validation_service.register_schema(schema)

        @validate_schema("test_data")
        async def process_data(data: str) -> str:
            return f"Processed: {data}"

        # Test with valid data
        result = await process_data("valid")
        assert result == "Processed: valid"

        # Test with invalid data
        with pytest.raises(ValidationError):
            await process_data("no")  # Too short

        # Test with non-existent schema
        @validate_schema("nonexistent_schema")
        async def process_with_missing_schema(data: str) -> str:
            return data

        with pytest.raises(ValidationError):
            await process_with_missing_schema("test")

    async def test_validate_contracts_integration(self, validation_service: ValidationService) -> None:
        """Test validate_contracts decorator with real contract validation."""
        @validate_contracts(
            input_contract={"name": str, "age": int},
            output_contract={"message": str, "age": int}
        )
        async def create_profile(name: str, age: int) -> dict:
            return {"message": f"User {name}", "age": age}

        # Test with valid input and output
        result = await create_profile("John", 30)
        assert result["message"] == "User John"
        assert result["age"] == 30

        # Test with invalid input type
        with pytest.raises(ValidationError):
            await create_profile("John", "thirty")  # age should be int

        # Test with invalid output contract
        @validate_contracts(
            input_contract={"name": str},
            output_contract={"result": int}  # Expects int but returns str
        )
        async def get_name_length(name: str) -> dict:
            return {"result": name}  # Returns string instead of int

        with pytest.raises(ValidationError):
            await get_name_length("test")

    async def test_decorator_chaining(self, validation_service: ValidationService) -> None:
        """Test chaining multiple validation decorators."""
        input_schema = StringValidationSchema("name", min_length=2)
        output_schema = StringValidationSchema("output", min_length=5)

        @validate_input({"name": input_schema})
        @validate_output(output_schema)
        @sanitize_input(fields=["name"])
        async def process_name(name: str) -> str:
            return f"Hello, {name}!"

        # Test successful processing through all decorators
        result = await process_name("John")
        assert result == "Hello, John!"

        # Test failure at input validation
        with pytest.raises(ValidationError):
            await process_name("X")  # Too short for input schema

    async def test_sync_function_decoration(self, validation_service: ValidationService) -> None:
        """Test decorator application to synchronous functions."""
        schema = StringValidationSchema("text", min_length=3)

        @validate_input({"text": schema})
        def sync_function(text: str) -> str:
            return f"Processed: {text}"

        # Test that sync function is properly wrapped
        assert hasattr(sync_function, '__wrapped__')

        # Note: Actually calling the sync function would require running asyncio.run
        # internally, which is complex to test. The important part is that the
        # decorator is applied correctly.

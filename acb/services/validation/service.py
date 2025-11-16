"""ValidationService implementation for ACB validation system.

This module provides the main ValidationService class that integrates
with ACB's Services Layer and provides comprehensive validation capabilities.
"""

from __future__ import annotations

import time

import asyncio
import typing as t

from acb.depends import Inject, depends
from acb.services._base import ServiceBase, ServiceConfig
from acb.services.validation._base import (
    ValidationConfig,
    ValidationMetrics,
    ValidationProtocol,
    ValidationRegistry,
    ValidationResult,
    ValidationSchema,
    ValidationSettings,
)

if t.TYPE_CHECKING:
    from acb.config import Config

# Service metadata for discovery system
try:
    from acb.services.discovery import (
        ServiceCapability,
        ServiceMetadata,
        ServiceStatus,
        generate_service_id,
    )

    SERVICE_METADATA: ServiceMetadata | None = ServiceMetadata(
        service_id=generate_service_id(),
        name="Validation Service",
        category="validation",
        service_type="validator",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework Team",
        created_date="2024-01-01T00:00:00",
        last_modified="2024-01-01T00:00:00",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.SCHEMA_VALIDATION,
            ServiceCapability.INPUT_SANITIZATION,
            ServiceCapability.OUTPUT_VALIDATION,
            ServiceCapability.CONTRACT_VALIDATION,
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.METRICS_COLLECTION,
        ],
        description="Comprehensive data validation service with security features and models adapter integration",
        settings_class="ValidationSettings",
        config_example={
            "default_validation_level": "strict",
            "enable_performance_monitoring": True,
            "enable_sanitization": True,
            "models_adapter_enabled": True,
        },
    )
except ImportError:
    # Discovery system not available
    SERVICE_METADATA = None


class ValidationService(ServiceBase, ValidationProtocol):
    """Main validation service for ACB applications.

    This service provides comprehensive data validation capabilities including:
    - Schema validation using Pydantic/msgspec integration
    - Input sanitization for security
    - Output contract validation
    - Type coercion and transformation
    - Performance monitoring and metrics
    - Health check integration

    Performance targets:
    - <1ms validation for standard schemas
    - <10ms for bulk validation (100 items)
    - <5ms schema compilation for complex schemas
    """

    config: Inject[Config]

    def __init__(
        self,
        service_config: ServiceConfig | None = None,
        validation_settings: ValidationSettings | None = None,
    ) -> None:
        # Initialize ServiceBase
        service_config = service_config or ServiceConfig(
            service_id="validation",
            name="ValidationService",
            description="Universal data validation service with security features",
        )
        super().__init__(service_config=service_config)

        # Initialize validation-specific components
        self._validation_settings = validation_settings or ValidationSettings()
        self._registry = ValidationRegistry()
        self._validation_metrics = ValidationMetrics()
        self._default_config = ValidationConfig(
            level=self._validation_settings.default_validation_level,
        )

        # Performance monitoring
        self._performance_monitoring_enabled = (
            self._validation_settings.enable_performance_monitoring
        )
        self._performance_threshold_ms = (
            self._validation_settings.performance_threshold_ms
        )

        # Models adapter integration
        self._models_adapter: t.Any = None
        self._models_adapter_enabled = self._validation_settings.models_adapter_enabled

    async def _initialize(self) -> None:
        """Initialize the ValidationService."""
        self.logger.info("Initializing ValidationService")

        # Initialize models adapter if enabled
        if self._models_adapter_enabled:
            await self._initialize_models_adapter()

        # Register default validation schemas
        await self._register_default_schemas()

        # Set up performance monitoring
        if self._performance_monitoring_enabled:
            self.set_custom_metric("validation_enabled", True)
            self.set_custom_metric(
                "performance_threshold_ms",
                self._performance_threshold_ms,
            )

        self.logger.info("ValidationService initialized successfully")

    async def _shutdown(self) -> None:
        """Shutdown the ValidationService."""
        self.logger.info("Shutting down ValidationService")

        # Clear registry and cache
        self._registry.clear()

        # Clean up models adapter
        self._models_adapter = None

        self.logger.info("ValidationService shut down successfully")

    async def _health_check(self) -> dict[str, t.Any]:
        """Perform ValidationService health check."""
        try:
            # Test basic validation functionality
            test_data = {"test": "value"}
            start_time = time.perf_counter()
            result = await self.validate(test_data)
            validation_time = (time.perf_counter() - start_time) * 1000

            # Check performance
            performance_ok = validation_time < self._performance_threshold_ms

            return {
                "validation_functional": result is not None,
                "performance_ok": performance_ok,
                "validation_time_ms": validation_time,
                "schemas_registered": len(self._registry.list_schemas()),
                "models_adapter_enabled": self._models_adapter_enabled,
                "models_adapter_available": self._models_adapter is not None,
                "metrics": self._validation_metrics.to_dict(),
            }

        except Exception as e:
            return {
                "validation_functional": False,
                "error": str(e),
                "schemas_registered": len(self._registry.list_schemas()),
            }

    async def _initialize_models_adapter(self) -> None:
        """Initialize models adapter integration."""
        try:
            from acb.adapters import import_adapter

            ModelsAdapter = import_adapter("models")
            self._models_adapter = await depends.get(ModelsAdapter)
            self.logger.info("Models adapter integration enabled")
        except Exception as e:
            self.logger.warning(f"Failed to initialize models adapter: {e}")
            self._models_adapter_enabled = False

    async def _register_default_schemas(self) -> None:
        """Register default validation schemas."""
        # This will be expanded with built-in schemas

    async def validate(
        self,
        data: t.Any,
        schema: ValidationSchema | None = None,
        config: ValidationConfig | None = None,
        field_name: str | None = None,
    ) -> ValidationResult:
        """Validate data using optional schema and configuration.

        Args:
            data: Data to validate
            schema: Optional validation schema
            config: Optional validation configuration
            field_name: Optional field name for error reporting

        Returns:
            ValidationResult with validation outcome
        """
        start_time = time.perf_counter()

        try:
            # Use provided config or default
            validation_config = config or self._default_config

            # Basic validation if no schema provided
            if schema is None:
                result = await self._validate_basic(data, validation_config, field_name)
            else:
                result = await self._validate_with_schema(
                    data,
                    schema,
                    validation_config,
                    field_name,
                )

            # Calculate validation time
            validation_time_ms = (time.perf_counter() - start_time) * 1000
            result.validation_time_ms = validation_time_ms

            # Record metrics
            self._validation_metrics.record_validation(
                success=result.is_valid,
                validation_time_ms=validation_time_ms,
            )

            # Update service metrics
            self.increment_requests()
            if not result.is_valid:
                self.record_error(f"Validation failed: {'; '.join(result.errors)}")

            # Performance monitoring
            if (
                self._performance_monitoring_enabled
                and validation_time_ms > self._performance_threshold_ms
            ):
                self.logger.warning(
                    f"Validation performance warning: {validation_time_ms:.2f}ms "
                    f"(threshold: {self._performance_threshold_ms}ms)",
                )

            return result

        except Exception as e:
            validation_time_ms = (time.perf_counter() - start_time) * 1000
            self.logger.exception(f"Validation error: {e}")

            # Record error metrics
            self._validation_metrics.record_validation(
                success=False,
                validation_time_ms=validation_time_ms,
            )
            self.record_error(str(e))

            # Return error result
            result = ValidationResult(
                field_name=field_name,
                is_valid=False,
                value=data,
                original_value=data,
                validation_time_ms=validation_time_ms,
            )
            result.add_error(f"Validation exception: {e}")
            return result

    async def validate_many(
        self,
        data_list: list[t.Any],
        schema: ValidationSchema | None = None,
        config: ValidationConfig | None = None,
    ) -> list[ValidationResult]:
        """Validate multiple data items.

        Args:
            data_list: List of data items to validate
            schema: Optional validation schema
            config: Optional validation configuration

        Returns:
            List of ValidationResult objects
        """
        # Use concurrent validation for performance
        tasks = [
            self.validate(data, schema, config, f"item_{i}")
            for i, data in enumerate(data_list)
        ]

        return await asyncio.gather(*tasks)

    async def _validate_basic(
        self,
        data: t.Any,
        config: ValidationConfig,
        field_name: str | None,
    ) -> ValidationResult:
        """Perform basic validation without a specific schema."""
        result = ValidationResult(
            field_name=field_name,
            value=data,
            original_value=data,
        )

        # Basic type and security validation
        if config.enable_sanitization:
            await self._apply_basic_sanitization(result, config)

        # Basic size limits
        if isinstance(data, str) and len(data) > config.max_string_length:
            result.add_error(
                f"String too long: {len(data)} > {config.max_string_length}",
            )

        elif isinstance(data, list | tuple) and len(data) > config.max_list_length:
            result.add_error(f"List too long: {len(data)} > {config.max_list_length}")

        elif isinstance(data, dict):
            if await self._check_dict_depth(data) > config.max_dict_depth:
                result.add_error(f"Dictionary too deep: > {config.max_dict_depth}")

        return result

    async def _validate_with_schema(
        self,
        data: t.Any,
        schema: ValidationSchema,
        config: ValidationConfig,
        field_name: str | None,
    ) -> ValidationResult:
        """Validate data using a specific schema."""
        # Ensure schema is compiled for performance
        await schema._ensure_compiled()

        # Use schema validation
        result = await schema.validate(data, field_name)

        # Apply additional configuration-based validation
        if config.enable_sanitization and result.is_valid:
            await self._apply_basic_sanitization(result, config)

        return result

    async def _apply_basic_sanitization(
        self,
        result: ValidationResult,
        config: ValidationConfig,
    ) -> None:
        """Apply basic sanitization to validation result."""
        if not isinstance(result.value, str):
            return

        # Basic XSS protection for strings
        if config.enable_xss_protection:
            # Simple HTML tag removal for basic protection
            import re

            cleaned_value = re.sub(
                r"<[^>]*>",
                "",
                result.value,
            )  # REGEX OK: XSS prevention
            if cleaned_value != result.value:
                result.value = cleaned_value
                result.add_warning("HTML tags removed for security")

        # Basic SQL injection patterns (simple detection)
        if config.enable_sql_injection_protection:
            sql_patterns = [
                r"\b(union|select|insert|update|delete|drop|create|alter)\b",
                r'[\'";]',
                r"--",
                r"/\*.*?\*/",
            ]
            import re

            for pattern in sql_patterns:
                if re.search(
                    pattern,
                    result.value,
                    re.IGNORECASE,
                ):  # REGEX OK: SQL injection prevention
                    result.add_warning("Potential SQL injection pattern detected")
                    break

    async def _check_dict_depth(
        self,
        data: dict[str, t.Any],
        current_depth: int = 0,
    ) -> int:
        """Check dictionary nesting depth."""
        if not isinstance(data, dict):
            return current_depth

        max_depth = current_depth
        for value in data.values():
            if isinstance(value, dict):
                depth = await self._check_dict_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)

        return max_depth

    # Registry management methods
    def register_schema(self, schema: ValidationSchema) -> None:
        """Register a validation schema."""
        self._registry.register(schema)
        self.logger.info(f"Registered validation schema: {schema.name}")

    async def get_schema(self, name: str) -> ValidationSchema | None:
        """Get a compiled validation schema by name."""
        return await self._registry.get_compiled_schema(name)

    def list_schemas(self) -> list[str]:
        """List all registered schema names."""
        return self._registry.list_schemas()

    def remove_schema(self, name: str) -> None:
        """Remove a schema from the registry."""
        self._registry.remove_schema(name)
        self.logger.info(f"Removed validation schema: {name}")

    # Performance and metrics methods
    def get_metrics(self) -> ValidationMetrics:
        """Get validation metrics."""
        return self._validation_metrics

    def reset_metrics(self) -> None:
        """Reset validation metrics."""
        self._validation_metrics = ValidationMetrics()
        self.logger.info("Validation metrics reset")

    # Models adapter integration methods
    async def validate_model(
        self,
        data: t.Any,
        model_class: type[t.Any],
        config: ValidationConfig | None = None,
    ) -> ValidationResult:
        """Validate data against a model class using models adapter."""
        if not self._models_adapter_enabled or self._models_adapter is None:
            result = ValidationResult(value=data, original_value=data, is_valid=False)
            result.add_error("Models adapter not available")
            return result

        try:
            # Get appropriate adapter for model type
            adapter = self._models_adapter.get_adapter_for_model(model_class)

            # Create instance to validate
            instance = adapter.create_instance(
                model_class,
                **data if isinstance(data, dict) else {"value": data},
            )

            # Return successful validation
            return ValidationResult(value=instance, original_value=data, is_valid=True)

        except Exception as e:
            result = ValidationResult(value=data, original_value=data, is_valid=False)
            result.add_error(f"Model validation failed: {e}")
            return result

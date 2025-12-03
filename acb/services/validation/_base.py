"""Base validation classes and types for ACB validation system.

This module provides the foundational types, classes, and protocols
for the ACB validation layer.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from enum import Enum

import typing as t
from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict

from acb.config import Settings


class ValidationLevel(Enum):
    """Validation strictness levels."""

    STRICT = "strict"  # Fail on any validation error
    LENIENT = "lenient"  # Allow warnings, fail on errors
    PERMISSIVE = "permissive"  # Only fail on critical errors


@dataclass
class ValidationResult:
    """Result of a single validation operation."""

    field_name: str | None = None
    is_valid: bool = True
    value: t.Any = None
    original_value: t.Any = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validation_time_ms: float = 0.0
    metadata: dict[str, t.Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def has_errors(self) -> bool:
        """Check if result has errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if result has warnings."""
        return len(self.warnings) > 0


class ValidationConfig(BaseModel):
    """Configuration for validation operations."""

    model_config = ConfigDict(extra="forbid")

    level: ValidationLevel = ValidationLevel.STRICT
    max_validation_time_ms: float = 10.0
    enable_coercion: bool = True
    enable_sanitization: bool = True
    strict_types: bool = True
    allow_extra_fields: bool = False
    validate_defaults: bool = True

    # Security settings
    enable_xss_protection: bool = True
    enable_sql_injection_protection: bool = True
    enable_path_traversal_protection: bool = True
    max_string_length: int = 10000
    max_list_length: int = 1000
    max_dict_depth: int = 10

    # Performance settings
    enable_schema_caching: bool = True
    cache_ttl_seconds: int = 3600
    max_cache_size: int = 1000


class ValidationSettings(Settings):
    """Settings for ValidationService."""

    # Basic validation settings
    validation_enabled: bool = True
    default_validation_level: ValidationLevel = ValidationLevel.STRICT
    max_validation_time_ms: float = 10.0

    # Performance settings
    enable_performance_monitoring: bool = True
    performance_threshold_ms: float = 5.0
    enable_result_caching: bool = True
    cache_ttl_seconds: int = 3600

    # Security settings
    enable_security_validation: bool = True
    max_input_size_bytes: int = 1048576  # 1MB
    enable_sanitization: bool = True

    # Integration settings
    models_adapter_enabled: bool = True
    health_check_validation_enabled: bool = True
    metrics_collection_enabled: bool = True


class ValidationSchema(ABC):
    """Abstract base class for validation schemas."""

    def __init__(self, name: str, config: ValidationConfig | None = None) -> None:
        self.name = name
        self.config = config or ValidationConfig()
        self._compiled = False
        self._compile_time: float | None = None

    @abstractmethod
    async def validate(
        self,
        data: t.Any,
        field_name: str | None = None,
    ) -> ValidationResult:
        """Validate data against this schema.

        Args:
            data: Data to validate
            field_name: Optional field name for error reporting

        Returns:
            ValidationResult with validation outcome
        """
        ...

    @abstractmethod
    async def compile(self) -> None:
        """Compile the schema for optimal performance.

        This method should prepare the schema for fast validation,
        including any preprocessing, optimization, or caching.
        """
        ...

    async def _ensure_compiled(self) -> None:
        """Ensure schema is compiled before validation."""
        if not self._compiled:
            start_time = time.perf_counter()
            await self.compile()
            self._compile_time = (time.perf_counter() - start_time) * 1000
            self._compiled = True

    @property
    def is_compiled(self) -> bool:
        """Check if schema is compiled."""
        return self._compiled

    @property
    def compile_time_ms(self) -> float | None:
        """Get schema compilation time in milliseconds."""
        return self._compile_time


class ValidationRegistry:
    """Registry for validation schemas."""

    def __init__(self) -> None:
        self._schemas: dict[str, ValidationSchema] = {}
        self._compiled_schemas: dict[str, ValidationSchema] = {}

    def register(self, schema: ValidationSchema) -> None:
        """Register a validation schema."""
        self._schemas[schema.name] = schema

    def get_schema(self, name: str) -> ValidationSchema | None:
        """Get a registered schema by name."""
        return self._schemas.get(name)

    async def get_compiled_schema(self, name: str) -> ValidationSchema | None:
        """Get a compiled schema by name."""
        schema = self._schemas.get(name)
        if schema is None:
            return None

        if name not in self._compiled_schemas:
            await schema._ensure_compiled()
            self._compiled_schemas[name] = schema

        return self._compiled_schemas[name]

    def list_schemas(self) -> list[str]:
        """List all registered schema names."""
        return list(self._schemas.keys())

    def remove_schema(self, name: str) -> None:
        """Remove a schema from the registry."""
        self._schemas.pop(name, None)
        self._compiled_schemas.pop(name, None)

    def clear(self) -> None:
        """Clear all schemas from the registry."""
        self._schemas.clear()
        self._compiled_schemas.clear()


class ValidationProtocol(t.Protocol):
    """Protocol for validation implementations."""

    async def validate(
        self,
        data: t.Any,
        schema: ValidationSchema | None = None,
        config: ValidationConfig | None = None,
    ) -> ValidationResult:
        """Validate data using optional schema and configuration."""
        ...

    async def validate_many(
        self,
        data_list: list[t.Any],
        schema: ValidationSchema | None = None,
        config: ValidationConfig | None = None,
    ) -> list[ValidationResult]:
        """Validate multiple data items."""
        ...


class ValidationMetrics:
    """Metrics tracking for validation operations."""

    def __init__(self) -> None:
        self.total_validations: int = 0
        self.successful_validations: int = 0
        self.failed_validations: int = 0
        self.average_validation_time_ms: float = 0.0
        self.max_validation_time_ms: float = 0.0
        self.total_validation_time_ms: float = 0.0
        self.schema_cache_hits: int = 0
        self.schema_cache_misses: int = 0

    def record_validation(
        self,
        success: bool,
        validation_time_ms: float,
        cache_hit: bool = False,
    ) -> None:
        """Record a validation operation."""
        self.total_validations += 1

        if success:
            self.successful_validations += 1
        else:
            self.failed_validations += 1

        self.total_validation_time_ms += validation_time_ms
        self.average_validation_time_ms = (
            self.total_validation_time_ms / self.total_validations
        )

        self.max_validation_time_ms = max(
            self.max_validation_time_ms,
            validation_time_ms,
        )

        if cache_hit:
            self.schema_cache_hits += 1
        else:
            self.schema_cache_misses += 1

    @property
    def success_rate(self) -> float:
        """Get validation success rate."""
        if self.total_validations == 0:
            return 0.0
        return self.successful_validations / self.total_validations

    @property
    def cache_hit_rate(self) -> float:
        """Get schema cache hit rate."""
        total_cache_operations = self.schema_cache_hits + self.schema_cache_misses
        if total_cache_operations == 0:
            return 0.0
        return self.schema_cache_hits / total_cache_operations

    def to_dict(self) -> dict[str, t.Any]:
        """Convert metrics to dictionary."""
        return {
            "total_validations": self.total_validations,
            "successful_validations": self.successful_validations,
            "failed_validations": self.failed_validations,
            "success_rate": self.success_rate,
            "average_validation_time_ms": self.average_validation_time_ms,
            "max_validation_time_ms": self.max_validation_time_ms,
            "total_validation_time_ms": self.total_validation_time_ms,
            "schema_cache_hits": self.schema_cache_hits,
            "schema_cache_misses": self.schema_cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
        }

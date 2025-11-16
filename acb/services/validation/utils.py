"""Validation utilities and helper functions.

This module provides utility functions and helpers for the validation system.
"""

from __future__ import annotations

import inspect
import time

import typing as t
from contextlib import asynccontextmanager

from acb.services.validation._base import (
    ValidationConfig,
    ValidationLevel,
    ValidationResult,
    ValidationSchema,
)


class ValidationTimer:
    """Timer for measuring validation performance."""

    def __init__(self) -> None:
        self._start_time: float | None = None
        self._end_time: float | None = None

    def start(self) -> ValidationTimer:
        """Start the timer."""
        self._start_time = time.perf_counter()
        return self

    def stop(self) -> float:
        """Stop the timer and return elapsed time in milliseconds."""
        if self._start_time is None:
            msg = "Timer not started"
            raise RuntimeError(msg)
        self._end_time = time.perf_counter()
        return (self._end_time - self._start_time) * 1000

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self._start_time is None:
            return 0.0
        end_time = self._end_time or time.perf_counter()
        return (end_time - self._start_time) * 1000

    @asynccontextmanager
    async def time_operation(self) -> t.AsyncGenerator[ValidationTimer]:
        """Async context manager for timing operations."""
        self.start()
        try:
            yield self
        finally:
            self.stop()


def create_validation_result(
    value: t.Any,
    field_name: str | None = None,
    is_valid: bool = True,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    validation_time_ms: float = 0.0,
    metadata: dict[str, t.Any] | None = None,
) -> ValidationResult:
    """Create a ValidationResult with provided parameters."""
    return ValidationResult(
        field_name=field_name,
        is_valid=is_valid,
        value=value,
        original_value=value,
        errors=errors or [],
        warnings=warnings or [],
        validation_time_ms=validation_time_ms,
        metadata=metadata or {},
    )


def combine_validation_results(
    results: list[ValidationResult],
    field_name: str | None = None,
) -> ValidationResult:
    """Combine multiple validation results into a single result."""
    if not results:
        return create_validation_result(None, field_name)

    combined_result = ValidationResult(
        field_name=field_name or "combined",
        value=[r.value for r in results],
        original_value=[r.original_value for r in results],
        validation_time_ms=sum(r.validation_time_ms for r in results),
    )

    # Combine errors and warnings
    for result in results:
        combined_result.errors.extend(result.errors)
        combined_result.warnings.extend(result.warnings)

    # Result is valid only if all results are valid
    combined_result.is_valid = all(r.is_valid for r in results)

    return combined_result


def is_validation_result_successful(
    result: ValidationResult,
    level: ValidationLevel = ValidationLevel.STRICT,
) -> bool:
    """Check if validation result is successful based on validation level."""
    if level == ValidationLevel.STRICT:
        return result.is_valid and not result.has_errors()
    if level == ValidationLevel.LENIENT:
        return not result.has_errors()  # Allow warnings
    if level == ValidationLevel.PERMISSIVE:
        return True  # Always pass, just collect information
    return result.is_valid


def get_validation_summary(results: list[ValidationResult]) -> dict[str, t.Any]:
    """Get a summary of validation results."""
    if not results:
        return {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "total_errors": 0,
            "total_warnings": 0,
            "total_time_ms": 0.0,
            "average_time_ms": 0.0,
        }

    successful = [r for r in results if r.is_valid]
    failed = [r for r in results if not r.is_valid]
    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)
    total_time_ms = sum(r.validation_time_ms for r in results)

    return {
        "total_validations": len(results),
        "successful_validations": len(successful),
        "failed_validations": len(failed),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "total_time_ms": total_time_ms,
        "average_time_ms": total_time_ms / len(results) if results else 0.0,
        "success_rate": len(successful) / len(results) if results else 0.0,
    }


class ValidationHelper:
    """Helper class for common validation operations."""

    @staticmethod
    def is_empty(value: t.Any) -> bool:
        """Check if a value is considered empty."""
        if value is None:
            return True
        if isinstance(value, str | list | dict | tuple | set):
            return len(value) == 0
        return False

    @staticmethod
    def is_numeric(value: t.Any) -> bool:
        """Check if a value is numeric."""
        return isinstance(value, int | float | complex)

    @staticmethod
    def is_string_like(value: t.Any) -> bool:
        """Check if a value is string-like."""
        return isinstance(value, str | bytes)

    @staticmethod
    def is_iterable(value: t.Any) -> bool:
        """Check if a value is iterable (but not string)."""
        try:
            iter(value)
            return not isinstance(value, str | bytes)
        except TypeError:
            return False

    @staticmethod
    def get_nested_value(
        data: dict[str, t.Any],
        path: str,
        default: t.Any = None,
    ) -> t.Any:
        """Get nested value from dictionary using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    @staticmethod
    def set_nested_value(data: dict[str, t.Any], path: str, value: t.Any) -> None:
        """Set nested value in dictionary using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    @staticmethod
    def flatten_dict(
        data: dict[str, t.Any],
        parent_key: str = "",
        separator: str = ".",
    ) -> dict[str, t.Any]:
        """Flatten a nested dictionary."""
        items = []
        for key, value in data.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key
            if isinstance(value, dict):
                items.extend(
                    ValidationHelper.flatten_dict(value, new_key, separator).items(),
                )
            else:
                items.append((new_key, value))
        return dict(items)


class SchemaValidator:
    """Utility class for schema validation operations."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

    async def validate_against_multiple_schemas(
        self,
        data: t.Any,
        schemas: list[ValidationSchema],
        require_all_pass: bool = True,
    ) -> list[ValidationResult]:
        """Validate data against multiple schemas."""
        results = []

        for schema in schemas:
            result = await schema.validate(data)
            results.append(result)

            # If require_all_pass is False and we found a passing schema, we can stop
            if not require_all_pass and result.is_valid:
                break

        return results

    async def find_best_matching_schema(
        self,
        data: t.Any,
        schemas: list[ValidationSchema],
    ) -> tuple[ValidationSchema | None, ValidationResult | None]:
        """Find the schema that best matches the data."""
        best_schema = None
        best_result = None
        best_score: float = -1.0

        for schema in schemas:
            result = await schema.validate(data)

            # Calculate a score based on validation success and warnings
            score: float = 0.0
            if result.is_valid:
                score += 100  # Base score for valid result
                score -= len(result.warnings)  # Subtract for warnings
                score -= result.validation_time_ms / 10  # Prefer faster validation

            if score > best_score:
                best_score = score
                best_schema = schema
                best_result = result

        return best_schema, best_result


class ValidationCache:
    """Simple in-memory cache for validation results."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        self._cache: dict[str, tuple[ValidationResult, float]] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def _generate_key(self, data: t.Any, schema_name: str | None = None) -> str:
        """Generate cache key for data and schema."""
        import hashlib

        data_str = str(data) + str(type(data)) + (schema_name or "")
        return hashlib.md5(data_str.encode(), usedforsecurity=False).hexdigest()

    def get(
        self,
        data: t.Any,
        schema_name: str | None = None,
    ) -> ValidationResult | None:
        """Get cached validation result."""
        key = self._generate_key(data, schema_name)

        if key in self._cache:
            result, timestamp = self._cache[key]

            # Check if result is still valid (TTL)
            if time.time() - timestamp < self._ttl_seconds:
                return result
            # Remove expired entry
            del self._cache[key]

        return None

    def set(
        self,
        data: t.Any,
        result: ValidationResult,
        schema_name: str | None = None,
    ) -> None:
        """Cache validation result."""
        key = self._generate_key(data, schema_name)

        # Remove oldest entries if cache is full
        if len(self._cache) >= self._max_size:
            # Remove 10% of oldest entries
            entries_to_remove = max(1, self._max_size // 10)
            oldest_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][1])[
                :entries_to_remove
            ]

            for old_key in oldest_keys:
                del self._cache[old_key]

        self._cache[key] = (result, time.time())

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


def inspect_function_parameters(func: t.Callable[..., t.Any]) -> dict[str, t.Any]:
    """Inspect function parameters for validation purposes."""
    sig = inspect.signature(func)
    parameters = {}

    for name, param in sig.parameters.items():
        param_info = {
            "name": name,
            "annotation": param.annotation,
            "default": param.default
            if param.default != inspect.Parameter.empty
            else None,
            "has_default": param.default != inspect.Parameter.empty,
            "kind": param.kind.name,
        }
        parameters[name] = param_info

    return {
        "parameters": parameters,
        "return_annotation": sig.return_annotation,
        "is_async": inspect.iscoroutinefunction(func),
    }


def create_validation_config_from_dict(
    config_dict: dict[str, t.Any],
) -> ValidationConfig:
    """Create ValidationConfig from dictionary."""
    # Map string level to enum
    if "level" in config_dict and isinstance(config_dict["level"], str):
        level_str = config_dict["level"].upper()
        try:
            config_dict["level"] = ValidationLevel[level_str]
        except KeyError:
            # Default to STRICT if unknown level
            config_dict["level"] = ValidationLevel.STRICT

    return ValidationConfig(**config_dict)


async def benchmark_validation(
    validation_func: t.Callable[..., t.Awaitable[ValidationResult]],
    test_data: list[t.Any],
    iterations: int = 100,
) -> dict[str, float]:
    """Benchmark validation function performance."""
    times = []

    for _ in range(iterations):
        for data in test_data:
            timer = ValidationTimer()
            timer.start()
            await validation_func(data)
            elapsed = timer.stop()
            times.append(elapsed)

    times.sort()

    return {
        "min_time_ms": min(times),
        "max_time_ms": max(times),
        "avg_time_ms": sum(times) / len(times),
        "median_time_ms": times[len(times) // 2],
        "p95_time_ms": times[int(len(times) * 0.95)],
        "p99_time_ms": times[int(len(times) * 0.99)],
        "total_validations": len(times),
    }

"""Validation schemas for the ACB validation system.

This module provides validation schema implementations that integrate
with the models adapter and provide high-performance validation capabilities.
"""

from __future__ import annotations

import re
import time

import typing as t

from acb.services.validation._base import (
    ValidationConfig,
    ValidationResult,
    ValidationSchema,
)


class BasicValidationSchema(ValidationSchema):
    """Basic validation schema for simple data types."""

    def __init__(
        self,
        name: str,
        data_type: type[t.Any] | None = None,
        required: bool = True,
        allow_none: bool = False,
        config: ValidationConfig | None = None,
    ) -> None:
        super().__init__(name, config)
        self.data_type = data_type
        self.required = required
        self.allow_none = allow_none

    async def compile(self) -> None:
        """Compile the schema (no-op for basic schema)."""
        # Basic schema requires no compilation

    async def validate(
        self,
        data: t.Any,
        field_name: str | None = None,
    ) -> ValidationResult:
        """Validate data against basic schema rules."""
        start_time = time.perf_counter()

        result = ValidationResult(
            field_name=field_name or self.name,
            value=data,
            original_value=data,
        )

        # Check if value is None
        if data is None:
            if not self.allow_none:
                result.add_error("Value cannot be None")
            return result

        # Check if required and missing
        if self.required and data in ("", [], {}, None):
            result.add_error("Required field is missing or empty")
            return result

        # Type validation
        if self.data_type is not None and not isinstance(data, self.data_type):
            try:
                # Attempt type coercion if enabled
                if self.config.enable_coercion:
                    result.value = self.data_type(data)
                    result.add_warning(
                        f"Value coerced from {type(data).__name__} to {self.data_type.__name__}",
                    )
                else:
                    result.add_error(
                        f"Expected {self.data_type.__name__}, got {type(data).__name__}",
                    )
            except (ValueError, TypeError):
                result.add_error(
                    f"Cannot convert {type(data).__name__} to {self.data_type.__name__}",
                )

        result.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return result


class StringValidationSchema(ValidationSchema):
    """Schema for string validation with length and pattern constraints."""

    def __init__(
        self,
        name: str,
        min_length: int = 0,
        max_length: int | None = None,
        pattern: str | None = None,
        strip_whitespace: bool = True,
        config: ValidationConfig | None = None,
    ) -> None:
        super().__init__(name, config)
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        self.strip_whitespace = strip_whitespace
        self._compiled_pattern: re.Pattern[str] | None = None

    async def compile(self) -> None:
        """Compile regex pattern for performance."""
        if self.pattern:
            self._compiled_pattern = re.compile(
                self.pattern,
            )  # REGEX OK: User-provided pattern validation

    async def validate(
        self,
        data: t.Any,
        field_name: str | None = None,
    ) -> ValidationResult:
        """Validate string data."""
        start_time = time.perf_counter()

        result = ValidationResult(
            field_name=field_name or self.name,
            value=data,
            original_value=data,
        )

        # Convert to string if possible
        if not isinstance(data, str):
            if self.config.enable_coercion:
                try:
                    result.value = str(data)
                    result.add_warning(
                        f"Value coerced from {type(data).__name__} to str",
                    )
                except Exception:
                    result.add_error("Cannot convert to string")
                    return result
            else:
                result.add_error(f"Expected string, got {type(data).__name__}")
                return result

        # Strip whitespace if enabled
        if self.strip_whitespace and isinstance(result.value, str):
            stripped = result.value.strip()
            if stripped != result.value:
                result.value = stripped
                result.add_warning("Leading/trailing whitespace removed")

        # Length validation
        value_length = len(result.value) if isinstance(result.value, str) else 0

        if value_length < self.min_length:
            result.add_error(f"String too short: {value_length} < {self.min_length}")

        if self.max_length is not None and value_length > self.max_length:
            result.add_error(f"String too long: {value_length} > {self.max_length}")

        # Pattern validation
        if (
            self._compiled_pattern is not None
            and isinstance(result.value, str)
            and not self._compiled_pattern.match(result.value)
        ):
            result.add_error(f"String does not match pattern: {self.pattern}")

        result.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return result


class EmailValidationSchema(ValidationSchema):
    """Schema for email validation."""

    def __init__(
        self,
        name: str = "email",
        config: ValidationConfig | None = None,
    ) -> None:
        super().__init__(name, config)
        # RFC 5322 compliant email regex (simplified)
        self._email_pattern = re.compile(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",  # REGEX OK: Email format validation
        )

    async def compile(self) -> None:
        """Compile email pattern (already compiled in __init__)."""

    async def validate(
        self,
        data: t.Any,
        field_name: str | None = None,
    ) -> ValidationResult:
        """Validate email address."""
        start_time = time.perf_counter()

        result = ValidationResult(
            field_name=field_name or self.name,
            value=data,
            original_value=data,
        )

        # Must be string
        if not isinstance(data, str):
            result.add_error(f"Email must be string, got {type(data).__name__}")
            return result

        # Strip and normalize
        email = data.strip().lower()
        if email != data:
            result.value = email
            result.add_warning("Email normalized")

        # Basic pattern validation
        if not self._email_pattern.match(email):
            result.add_error("Invalid email format")

        # Length validation
        if len(email) > 254:  # RFC 5321 limit
            result.add_error("Email address too long")

        result.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return result


class ModelValidationSchema(ValidationSchema):
    """Schema for validating data against model classes using the models adapter."""

    def __init__(
        self,
        name: str,
        model_class: type[t.Any],
        models_adapter: t.Any | None = None,
        config: ValidationConfig | None = None,
    ) -> None:
        super().__init__(name, config)
        self.model_class = model_class
        self.models_adapter = models_adapter
        self._adapter_instance: t.Any = None

    async def compile(self) -> None:
        """Compile model schema by preparing adapter instance."""
        if self.models_adapter is not None:
            self._adapter_instance = self.models_adapter.get_adapter_for_model(
                self.model_class,
            )

    async def validate(
        self,
        data: t.Any,
        field_name: str | None = None,
    ) -> ValidationResult:
        """Validate data against model class."""
        start_time = time.perf_counter()

        result = ValidationResult(
            field_name=field_name or self.name,
            value=data,
            original_value=data,
        )

        if self._adapter_instance is None:
            result.add_error("Model adapter not available")
            return result

        try:
            # Try to create instance using the adapter
            if isinstance(data, dict):
                instance = self._adapter_instance.create_instance(
                    self.model_class,
                    **data,
                )
            else:
                # For non-dict data, try direct instantiation
                instance = (
                    self.model_class(data) if data is not None else self.model_class()
                )

            result.value = instance

        except Exception as e:
            result.add_error(f"Model validation failed: {e}")

        result.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return result


class ListValidationSchema(ValidationSchema):
    """Schema for validating lists with item validation."""

    def __init__(
        self,
        name: str,
        item_schema: ValidationSchema | None = None,
        min_items: int = 0,
        max_items: int | None = None,
        unique_items: bool = False,
        config: ValidationConfig | None = None,
    ) -> None:
        super().__init__(name, config)
        self.item_schema = item_schema
        self.min_items = min_items
        self.max_items = max_items
        self.unique_items = unique_items

    async def compile(self) -> None:
        """Compile item schema if provided."""
        if self.item_schema:
            await self.item_schema._ensure_compiled()

    async def validate(
        self,
        data: t.Any,
        field_name: str | None = None,
    ) -> ValidationResult:
        """Validate list data."""
        start_time = time.perf_counter()

        result = ValidationResult(
            field_name=field_name or self.name,
            value=data,
            original_value=data,
        )

        # Convert to list if possible
        if not self._coerce_to_list(data, result):
            return result

        # Ensure we're working with a list
        items = (
            list(result.value) if not isinstance(result.value, list) else result.value
        )

        # Validate list constraints
        self._validate_list_length(items, result)
        self._validate_unique_items(items, result)

        # Validate individual items if schema provided
        if self.item_schema and result.is_valid:
            validated_items = await self._validate_list_items(items, field_name, result)
            if result.is_valid:
                result.value = validated_items

        result.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    def _coerce_to_list(self, data: t.Any, result: ValidationResult) -> bool:
        """Coerce data to list type. Returns False if coercion fails."""
        if isinstance(data, list | tuple):
            return True

        if self.config.enable_coercion:
            try:
                # Strings should be wrapped as single item, not split into characters
                if isinstance(data, str):
                    result.value = [data]
                elif hasattr(data, "__iter__"):
                    result.value = list(data)
                else:
                    result.value = [data]
                result.add_warning(
                    f"Value coerced from {type(data).__name__} to list",
                )
                return True
            except Exception:
                result.add_error("Cannot convert to list")
                return False

        result.add_error(f"Expected list, got {type(data).__name__}")
        return False

    def _validate_list_length(
        self,
        items: list[t.Any],
        result: ValidationResult,
    ) -> None:
        """Validate list length constraints."""
        if len(items) < self.min_items:
            result.add_error(f"List too short: {len(items)} < {self.min_items}")

        if self.max_items is not None and len(items) > self.max_items:
            result.add_error(f"List too long: {len(items)} > {self.max_items}")

    def _validate_unique_items(
        self,
        items: list[t.Any],
        result: ValidationResult,
    ) -> None:
        """Validate unique items constraint."""
        if self.unique_items and len(items) != len({str(item) for item in items}):
            result.add_error("List items must be unique")

    async def _validate_list_items(
        self,
        items: list[t.Any],
        field_name: str | None,
        result: ValidationResult,
    ) -> list[t.Any]:
        """Validate each item in the list."""
        validated_items = []
        for i, item in enumerate(items):
            item_result = await self.item_schema.validate(  # type: ignore[union-attr]
                item,
                f"{field_name or self.name}[{i}]",
            )
            if not item_result.is_valid:
                for error in item_result.errors:
                    result.add_error(f"Item {i}: {error}")
            else:
                validated_items.append(item_result.value)
                for warning in item_result.warnings:
                    result.add_warning(f"Item {i}: {warning}")

        return validated_items


class DictValidationSchema(ValidationSchema):
    """Schema for validating dictionaries with field validation."""

    def __init__(
        self,
        name: str,
        field_schemas: dict[str, ValidationSchema] | None = None,
        required_fields: list[str] | None = None,
        allow_extra_fields: bool = True,
        config: ValidationConfig | None = None,
    ) -> None:
        super().__init__(name, config)
        self.field_schemas = field_schemas or {}
        self.required_fields = set(required_fields or [])
        self.allow_extra_fields = allow_extra_fields

    async def compile(self) -> None:
        """Compile all field schemas."""
        for schema in self.field_schemas.values():
            await schema._ensure_compiled()

    def _check_required_fields(
        self,
        data: dict[str, t.Any],
        result: ValidationResult,
    ) -> None:
        """Check for missing required fields."""
        for field in self.required_fields:
            if field not in data:
                result.add_error(f"Required field '{field}' is missing")

    async def _validate_field_with_schema(
        self,
        field: str,
        value: t.Any,
        result: ValidationResult,
        validated_data: dict[str, t.Any],
    ) -> None:
        """Validate a field using its specific schema."""
        field_result = await self.field_schemas[field].validate(value, field)

        if not field_result.is_valid:
            for error in field_result.errors:
                result.add_error(f"Field '{field}': {error}")
        else:
            validated_data[field] = field_result.value
            for warning in field_result.warnings:
                result.add_warning(f"Field '{field}': {warning}")

    def _handle_extra_field(
        self,
        field: str,
        value: t.Any,
        result: ValidationResult,
        validated_data: dict[str, t.Any],
    ) -> None:
        """Handle a field without a specific schema."""
        if not self.allow_extra_fields:
            result.add_error(f"Unexpected field '{field}'")
        else:
            validated_data[field] = value

    async def validate(
        self,
        data: t.Any,
        field_name: str | None = None,
    ) -> ValidationResult:
        """Validate dictionary data."""
        start_time = time.perf_counter()

        result = ValidationResult(
            field_name=field_name or self.name,
            value=data,
            original_value=data,
        )

        # Must be dict-like
        if not isinstance(data, dict):
            result.add_error(f"Expected dict, got {type(data).__name__}")
            return result

        validated_data: dict[str, t.Any] = {}

        # Check required fields
        self._check_required_fields(data, result)

        # Validate each field
        for field, value in data.items():
            if field in self.field_schemas:
                await self._validate_field_with_schema(
                    field,
                    value,
                    result,
                    validated_data,
                )
            else:
                self._handle_extra_field(field, value, result, validated_data)

        if result.is_valid:
            result.value = validated_data

        result.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return result


class SchemaBuilder:
    """Builder for creating validation schemas."""

    def __init__(self) -> None:
        self._schemas: dict[str, ValidationSchema] = {}

    def add_basic(
        self,
        name: str,
        data_type: type[t.Any] | None = None,
        required: bool = True,
        allow_none: bool = False,
    ) -> SchemaBuilder:
        """Add a basic validation schema."""
        self._schemas[name] = BasicValidationSchema(
            name=name,
            data_type=data_type,
            required=required,
            allow_none=allow_none,
        )
        return self

    def add_string(
        self,
        name: str,
        min_length: int = 0,
        max_length: int | None = None,
        pattern: str | None = None,
    ) -> SchemaBuilder:
        """Add a string validation schema."""
        self._schemas[name] = StringValidationSchema(
            name=name,
            min_length=min_length,
            max_length=max_length,
            pattern=pattern,
        )
        return self

    def add_email(self, name: str = "email") -> SchemaBuilder:
        """Add an email validation schema."""
        self._schemas[name] = EmailValidationSchema(name=name)
        return self

    def add_list(
        self,
        name: str,
        item_schema: ValidationSchema | None = None,
        min_items: int = 0,
        max_items: int | None = None,
    ) -> SchemaBuilder:
        """Add a list validation schema."""
        self._schemas[name] = ListValidationSchema(
            name=name,
            item_schema=item_schema,
            min_items=min_items,
            max_items=max_items,
        )
        return self

    def add_dict(
        self,
        name: str,
        field_schemas: dict[str, ValidationSchema] | None = None,
        required_fields: list[str] | None = None,
    ) -> SchemaBuilder:
        """Add a dictionary validation schema."""
        self._schemas[name] = DictValidationSchema(
            name=name,
            field_schemas=field_schemas,
            required_fields=required_fields,
        )
        return self

    def build(self) -> dict[str, ValidationSchema]:
        """Build and return all schemas."""
        return self._schemas.copy()

    def get_schema(self, name: str) -> ValidationSchema | None:
        """Get a specific schema by name."""
        return self._schemas.get(name)

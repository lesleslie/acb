"""API Gateway Request/Response Validation.

This module provides comprehensive request and response validation for the ACB API Gateway,
supporting JSON Schema, Pydantic models, and custom validation rules with detailed error reporting.
"""

from __future__ import annotations

import asyncio
import re
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ValidationError


class ValidationType(str, Enum):
    """Types of validation supported by the gateway."""

    REQUEST_BODY = "request_body"
    REQUEST_HEADERS = "request_headers"
    REQUEST_QUERY = "request_query"
    REQUEST_PATH = "request_path"
    RESPONSE_BODY = "response_body"
    RESPONSE_HEADERS = "response_headers"


class ValidationSeverity(str, Enum):
    """Severity levels for validation errors."""

    ERROR = "error"  # Block request/response
    WARNING = "warning"  # Log but allow through
    INFO = "info"  # Informational only


class ValidationResult(BaseModel):
    """Result of a validation operation."""

    valid: bool
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    validation_id: str
    validation_type: ValidationType
    processing_time_ms: float


class ValidationRule(BaseModel):
    """A validation rule configuration."""

    name: str
    validation_type: ValidationType
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True

    # Schema validation
    json_schema: dict[str, Any] | None = None
    pydantic_model: str | None = None  # Class path for dynamic import

    # Custom validation
    custom_validator: str | None = None  # Function path for dynamic import

    # Field-specific rules
    required_fields: list[str] = []
    forbidden_fields: list[str] = []
    field_patterns: dict[str, str] = {}  # field_name -> regex pattern

    # Size limits
    max_size_bytes: int | None = None
    max_array_length: int | None = None
    max_string_length: int | None = None

    # Content type restrictions
    allowed_content_types: list[str] = []

    # Rate limiting for validation
    max_validations_per_second: int | None = None


class ValidatorProtocol(Protocol):
    """Protocol for custom validators."""

    async def validate(self, data: Any, context: dict[str, Any]) -> ValidationResult:
        """Validate data and return result."""
        ...


class BasicSchemaValidator:
    """Basic schema-based validator using built-in Python validation."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema

    async def validate(self, data: Any, context: dict[str, Any]) -> ValidationResult:
        """Validate data against basic schema."""
        validation_id = str(uuid4())
        start_time = asyncio.get_event_loop().time()

        errors = []
        warnings: list[Any] = []

        try:
            # Basic schema validation
            errors.extend(self._validate_type(data, self.schema, ""))

        except Exception as e:
            errors.append(
                {
                    "field": "__root__",
                    "message": f"Schema validation failed: {e!s}",
                    "invalid_value": data,
                    "error_type": "validation_error",
                },
            )

        end_time = asyncio.get_event_loop().time()
        processing_time = (end_time - start_time) * 1000

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validation_id=validation_id,
            validation_type=context.get("validation_type", ValidationType.REQUEST_BODY),
            processing_time_ms=processing_time,
        )

    def _validate_type(
        self,
        data: Any,
        schema: dict[str, Any],
        field_path: str,
    ) -> list[dict[str, Any]]:
        """Validate data type against schema."""
        errors: list[Any] = []

        if "type" not in schema:
            return errors

        expected_type = schema["type"]
        type_validators = {
            "string": lambda x: isinstance(x, str),
            "integer": lambda x: isinstance(x, int),
            "number": lambda x: isinstance(x, int | float),
            "boolean": lambda x: isinstance(x, bool),
            "array": lambda x: isinstance(x, list),
            "object": lambda x: isinstance(x, dict),
        }

        validator = type_validators.get(expected_type)
        if validator and not validator(data):
            errors.append(self._create_type_error(field_path, expected_type, data))

        # Additional validation constraints
        errors.extend(self._validate_constraints(data, schema, field_path))

        return errors

    def _create_type_error(
        self,
        field_path: str,
        expected_type: str,
        data: Any,
    ) -> dict[str, Any]:
        """Create a type validation error."""
        return {
            "field": field_path,
            "message": f"Expected {expected_type}, got {type(data).__name__}",
            "invalid_value": data,
            "error_type": "type_error",
        }

    def _validate_constraints(
        self,
        data: Any,
        schema: dict[str, Any],
        field_path: str,
    ) -> list[dict[str, Any]]:
        """Validate additional constraints."""
        errors = []

        # String constraints
        if isinstance(data, str):
            errors.extend(self._validate_string_constraints(data, schema, field_path))

        # Numeric constraints
        if isinstance(data, int | float):
            errors.extend(self._validate_numeric_constraints(data, schema, field_path))

        # Array constraints
        if isinstance(data, list):
            errors.extend(self._validate_array_constraints(data, schema, field_path))

        return errors

    def _validate_string_constraints(
        self,
        data: str,
        schema: dict[str, Any],
        field_path: str,
    ) -> list[dict[str, Any]]:
        """Validate string-specific constraints."""
        errors = []

        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(
                {
                    "field": field_path,
                    "message": f"String too short (min: {schema['minLength']})",
                    "invalid_value": data,
                    "error_type": "length_error",
                },
            )

        if "maxLength" in schema and len(data) > schema["maxLength"]:
            errors.append(
                {
                    "field": field_path,
                    "message": f"String too long (max: {schema['maxLength']})",
                    "invalid_value": data,
                    "error_type": "length_error",
                },
            )

        if "pattern" in schema:
            try:
                pattern = re.compile(
                    schema["pattern"]
                )  # REGEX OK: JSON schema pattern validation
                if not pattern.match(data):
                    errors.append(
                        {
                            "field": field_path,
                            "message": f"String does not match pattern: {schema['pattern']}",
                            "invalid_value": data,
                            "error_type": "pattern_error",
                        },
                    )
            except re.error:
                errors.append(
                    {
                        "field": field_path,
                        "message": f"Invalid regex pattern: {schema['pattern']}",
                        "error_type": "pattern_error",
                    },
                )

        return errors

    def _validate_numeric_constraints(
        self,
        data: float,
        schema: dict[str, Any],
        field_path: str,
    ) -> list[dict[str, Any]]:
        """Validate numeric constraints."""
        errors = []

        if "minimum" in schema and data < schema["minimum"]:
            errors.append(
                {
                    "field": field_path,
                    "message": f"Value too small (min: {schema['minimum']})",
                    "invalid_value": data,
                    "error_type": "range_error",
                },
            )

        if "maximum" in schema and data > schema["maximum"]:
            errors.append(
                {
                    "field": field_path,
                    "message": f"Value too large (max: {schema['maximum']})",
                    "invalid_value": data,
                    "error_type": "range_error",
                },
            )

        return errors

    def _validate_array_constraints(
        self,
        data: list[Any],
        schema: dict[str, Any],
        field_path: str,
    ) -> list[dict[str, Any]]:
        """Validate array constraints."""
        errors = []

        if "minItems" in schema and len(data) < schema["minItems"]:
            errors.append(
                {
                    "field": field_path,
                    "message": f"Array too short (min items: {schema['minItems']})",
                    "invalid_value": data,
                    "error_type": "length_error",
                },
            )

        if "maxItems" in schema and len(data) > schema["maxItems"]:
            errors.append(
                {
                    "field": field_path,
                    "message": f"Array too long (max items: {schema['maxItems']})",
                    "invalid_value": data,
                    "error_type": "length_error",
                },
            )

        return errors


class PydanticValidator:
    """Pydantic model-based validator."""

    def __init__(self, model_class: type[BaseModel]) -> None:
        self.model_class = model_class

    async def validate(self, data: Any, context: dict[str, Any]) -> ValidationResult:
        """Validate data against Pydantic model."""
        validation_id = str(uuid4())
        start_time = asyncio.get_event_loop().time()

        errors = []
        warnings: list[Any] = []

        try:
            # Validate with Pydantic
            if isinstance(data, dict):
                self.model_class(**data)
            else:
                self.model_class.model_validate(data)

        except ValidationError as e:
            for error in e.errors():
                error_detail = {
                    "field": ".".join(str(p) for p in error["loc"]),
                    "message": error["msg"],
                    "invalid_value": error.get("input"),
                    "error_type": error["type"],
                    "constraint": error.get("ctx", {}),
                }
                errors.append(error_detail)

        except Exception as e:
            errors.append(
                {
                    "field": "__root__",
                    "message": f"Pydantic validation failed: {e!s}",
                    "invalid_value": data,
                    "error_type": "validation_error",
                },
            )

        end_time = asyncio.get_event_loop().time()
        processing_time = (end_time - start_time) * 1000

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validation_id=validation_id,
            validation_type=context.get("validation_type", ValidationType.REQUEST_BODY),
            processing_time_ms=processing_time,
        )


class CustomValidator:
    """Custom function-based validator."""

    def __init__(self, validator_func: callable) -> None:
        self.validator_func = validator_func

    async def validate(self, data: Any, context: dict[str, Any]) -> ValidationResult:
        """Validate data using custom function."""
        validation_id = str(uuid4())
        start_time = asyncio.get_event_loop().time()

        try:
            if asyncio.iscoroutinefunction(self.validator_func):
                result = await self.validator_func(data, context)
            else:
                result = self.validator_func(data, context)

            # Handle different return types
            if isinstance(result, ValidationResult):
                return result
            if isinstance(result, bool):
                return ValidationResult(
                    valid=result,
                    validation_id=validation_id,
                    validation_type=context.get(
                        "validation_type",
                        ValidationType.REQUEST_BODY,
                    ),
                    processing_time_ms=(asyncio.get_event_loop().time() - start_time)
                    * 1000,
                )
            if isinstance(result, dict):
                return ValidationResult(
                    validation_id=validation_id,
                    validation_type=context.get(
                        "validation_type",
                        ValidationType.REQUEST_BODY,
                    ),
                    processing_time_ms=(asyncio.get_event_loop().time() - start_time)
                    * 1000,
                    **result,
                )
            msg = f"Invalid return type from custom validator: {type(result)}"
            raise ValueError(
                msg,
            )

        except Exception as e:
            end_time = asyncio.get_event_loop().time()
            processing_time = (end_time - start_time) * 1000

            return ValidationResult(
                valid=False,
                errors=[
                    {
                        "field": "__root__",
                        "message": f"Custom validation failed: {e!s}",
                        "invalid_value": data,
                        "error_type": "custom_validation_error",
                    },
                ],
                validation_id=validation_id,
                validation_type=context.get(
                    "validation_type",
                    ValidationType.REQUEST_BODY,
                ),
                processing_time_ms=processing_time,
            )


class RequestResponseValidator:
    """Main validator class for API Gateway requests and responses."""

    def __init__(self) -> None:
        self._rules: dict[str, ValidationRule] = {}
        self._validators: dict[str, ValidatorProtocol] = {}
        self._validation_stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "avg_processing_time_ms": 0.0,
        }

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        self._rules[rule.name] = rule

        # Create appropriate validator
        if rule.json_schema:
            self._validators[rule.name] = BasicSchemaValidator(rule.json_schema)
        elif rule.pydantic_model:
            # Import Pydantic model dynamically
            model_class = self._import_class(rule.pydantic_model)
            self._validators[rule.name] = PydanticValidator(model_class)
        elif rule.custom_validator:
            # Import custom validator function
            validator_func = self._import_function(rule.custom_validator)
            self._validators[rule.name] = CustomValidator(validator_func)

    def remove_rule(self, rule_name: str) -> None:
        """Remove a validation rule."""
        self._rules.pop(rule_name, None)
        self._validators.pop(rule_name, None)

    def get_rule(self, rule_name: str) -> ValidationRule | None:
        """Get a validation rule by name."""
        return self._rules.get(rule_name)

    def list_rules(
        self,
        validation_type: ValidationType | None = None,
    ) -> list[ValidationRule]:
        """List all validation rules, optionally filtered by type."""
        if validation_type:
            return [
                rule
                for rule in self._rules.values()
                if rule.validation_type == validation_type
            ]
        return list(self._rules.values())

    async def validate_request_body(
        self,
        body: Any,
        content_type: str = "application/json",
    ) -> ValidationResult:
        """Validate request body."""
        return await self._validate_data(
            data=body,
            validation_type=ValidationType.REQUEST_BODY,
            content_type=content_type,
        )

    async def validate_request_headers(
        self,
        headers: dict[str, str],
    ) -> ValidationResult:
        """Validate request headers."""
        return await self._validate_data(
            data=headers,
            validation_type=ValidationType.REQUEST_HEADERS,
        )

    async def validate_request_query(
        self,
        query_params: dict[str, Any],
    ) -> ValidationResult:
        """Validate request query parameters."""
        return await self._validate_data(
            data=query_params,
            validation_type=ValidationType.REQUEST_QUERY,
        )

    async def validate_request_path(
        self,
        path_params: dict[str, Any],
    ) -> ValidationResult:
        """Validate request path parameters."""
        return await self._validate_data(
            data=path_params,
            validation_type=ValidationType.REQUEST_PATH,
        )

    async def validate_response_body(
        self,
        body: Any,
        content_type: str = "application/json",
    ) -> ValidationResult:
        """Validate response body."""
        return await self._validate_data(
            data=body,
            validation_type=ValidationType.RESPONSE_BODY,
            content_type=content_type,
        )

    async def validate_response_headers(
        self,
        headers: dict[str, str],
    ) -> ValidationResult:
        """Validate response headers."""
        return await self._validate_data(
            data=headers,
            validation_type=ValidationType.RESPONSE_HEADERS,
        )

    async def _validate_data(
        self,
        data: Any,
        validation_type: ValidationType,
        content_type: str = "application/json",
    ) -> ValidationResult:
        """Internal method to validate data against all applicable rules."""
        applicable_rules = [
            rule
            for rule in self._rules.values()
            if rule.validation_type == validation_type and rule.enabled
        ]

        if not applicable_rules:
            # No rules to validate against
            return ValidationResult(
                valid=True,
                validation_id=str(uuid4()),
                validation_type=validation_type,
                processing_time_ms=0.0,
            )

        all_errors = []
        all_warnings = []
        total_processing_time = 0.0

        context = {
            "validation_type": validation_type,
            "content_type": content_type,
            "data_size": len(str(data)) if data else 0,
        }

        for rule in applicable_rules:
            # Check content type restrictions
            if (
                rule.allowed_content_types
                and content_type not in rule.allowed_content_types
            ):
                continue

            # Check size limits
            if rule.max_size_bytes and context["data_size"] > rule.max_size_bytes:
                all_errors.append(
                    {
                        "rule": rule.name,
                        "field": "__size__",
                        "message": f"Data size {context['data_size']} exceeds limit {rule.max_size_bytes}",
                        "error_type": "size_limit_exceeded",
                    },
                )
                continue

            # Perform basic field validation
            if isinstance(data, dict):
                field_errors = self._validate_fields(data, rule)
                all_errors.extend(field_errors)

            # Run validator if available
            validator = self._validators.get(rule.name)
            if validator:
                try:
                    result = await validator.validate(data, context)
                    total_processing_time += result.processing_time_ms

                    if rule.severity == ValidationSeverity.ERROR:
                        all_errors.extend(result.errors)
                    else:
                        all_warnings.extend(result.errors)

                    all_warnings.extend(result.warnings)

                except Exception as e:
                    all_errors.append(
                        {
                            "rule": rule.name,
                            "field": "__validator__",
                            "message": f"Validator execution failed: {e!s}",
                            "error_type": "validator_error",
                        },
                    )

        # Update statistics
        self._validation_stats["total_validations"] += 1
        if all_errors:
            self._validation_stats["failed_validations"] += 1
        else:
            self._validation_stats["successful_validations"] += 1

        # Update average processing time
        current_avg = self._validation_stats["avg_processing_time_ms"]
        total_validations = self._validation_stats["total_validations"]
        self._validation_stats["avg_processing_time_ms"] = (
            current_avg * (total_validations - 1) + total_processing_time
        ) / total_validations

        return ValidationResult(
            valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            validation_id=str(uuid4()),
            validation_type=validation_type,
            processing_time_ms=total_processing_time,
        )

    def _validate_fields(
        self,
        data: dict[str, Any],
        rule: ValidationRule,
    ) -> list[dict[str, Any]]:
        """Validate field-level rules."""
        errors = []

        # Check required fields
        for field in rule.required_fields:
            if field not in data:
                errors.append(
                    {
                        "rule": rule.name,
                        "field": field,
                        "message": f"Required field '{field}' is missing",
                        "error_type": "required_field_missing",
                    },
                )

        # Check forbidden fields
        for field in rule.forbidden_fields:
            if field in data:
                errors.append(
                    {
                        "rule": rule.name,
                        "field": field,
                        "message": f"Forbidden field '{field}' is present",
                        "error_type": "forbidden_field_present",
                    },
                )

        # Check field patterns
        for field, pattern_str in rule.field_patterns.items():
            if field in data:
                try:
                    pattern = re.compile(
                        pattern_str
                    )  # REGEX OK: field pattern validation
                    if not pattern.match(str(data[field])):
                        errors.append(
                            {
                                "rule": rule.name,
                                "field": field,
                                "message": f"Field '{field}' does not match pattern '{pattern_str}'",
                                "invalid_value": data[field],
                                "error_type": "pattern_mismatch",
                            },
                        )
                except re.error:
                    errors.append(
                        {
                            "rule": rule.name,
                            "field": field,
                            "message": f"Invalid regex pattern '{pattern_str}'",
                            "error_type": "invalid_pattern",
                        },
                    )

        # Check array length limits
        if rule.max_array_length:
            for field, value in data.items():
                if isinstance(value, list) and len(value) > rule.max_array_length:
                    errors.append(
                        {
                            "rule": rule.name,
                            "field": field,
                            "message": f"Array length {len(value)} exceeds limit {rule.max_array_length}",
                            "error_type": "array_too_long",
                        },
                    )

        # Check string length limits
        if rule.max_string_length:
            for field, value in data.items():
                if isinstance(value, str) and len(value) > rule.max_string_length:
                    errors.append(
                        {
                            "rule": rule.name,
                            "field": field,
                            "message": f"String length {len(value)} exceeds limit {rule.max_string_length}",
                            "error_type": "string_too_long",
                        },
                    )

        return errors

    def _import_class(self, class_path: str) -> type:
        """Dynamically import a class from a module path."""
        module_path, class_name = class_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)

    def _import_function(self, function_path: str) -> callable:
        """Dynamically import a function from a module path."""
        module_path, function_name = function_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[function_name])
        return getattr(module, function_name)

    def get_validation_stats(self) -> dict[str, Any]:
        """Get validation statistics."""
        return self._validation_stats.copy()

    def reset_stats(self) -> None:
        """Reset validation statistics."""
        self._validation_stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "avg_processing_time_ms": 0.0,
        }


# Common validation schemas and rules
COMMON_SCHEMAS = {
    "email": {"type": "string", "format": "email", "maxLength": 254},
    "uuid": {
        "type": "string",
        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    },
    "positive_integer": {"type": "integer", "minimum": 1},
    "non_empty_string": {"type": "string", "minLength": 1},
    "iso_datetime": {"type": "string", "format": "date-time"},
}

# Default validation rules for common scenarios
DEFAULT_REQUEST_BODY_RULE = ValidationRule(
    name="default_request_body",
    validation_type=ValidationType.REQUEST_BODY,
    severity=ValidationSeverity.ERROR,
    max_size_bytes=1024 * 1024,  # 1MB
    allowed_content_types=["application/json", "application/x-www-form-urlencoded"],
)

DEFAULT_RESPONSE_BODY_RULE = ValidationRule(
    name="default_response_body",
    validation_type=ValidationType.RESPONSE_BODY,
    severity=ValidationSeverity.WARNING,
    max_size_bytes=10 * 1024 * 1024,  # 10MB
)

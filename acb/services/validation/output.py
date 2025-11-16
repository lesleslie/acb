"""Output contract validation for API consistency.

This module provides validation for API outputs to ensure consistent
responses and contract compliance across applications.
"""

from __future__ import annotations

import time
from enum import Enum

import typing as t
from dataclasses import dataclass, field

from acb.services.validation._base import (
    ValidationConfig,
    ValidationResult,
)


class OutputType(Enum):
    """Types of output validation."""

    JSON_API = "json_api"  # JSON API response
    REST_API = "rest_api"  # REST API response
    MODEL = "model"  # Model instance
    DICT = "dict"  # Dictionary data
    LIST = "list"  # List data
    SCALAR = "scalar"  # Single value
    CUSTOM = "custom"  # Custom format


@dataclass
class OutputContract:
    """Contract definition for output validation."""

    name: str
    output_type: OutputType
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    field_types: dict[str, type[t.Any]] = field(default_factory=dict)
    allow_extra_fields: bool = True
    strict_types: bool = False
    min_length: int | None = None
    max_length: int | None = None
    custom_validators: list[t.Callable[[t.Any], bool]] = field(default_factory=list)


class OutputValidator:
    """Main output validation service."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()
        self._contracts: dict[str, OutputContract] = {}

    def register_contract(self, contract: OutputContract) -> None:
        """Register an output contract."""
        self._contracts[contract.name] = contract

    def get_contract(self, name: str) -> OutputContract | None:
        """Get a registered contract."""
        return self._contracts.get(name)

    async def validate_output(
        self,
        data: t.Any,
        contract: OutputContract | str | None = None,
        field_name: str | None = None,
    ) -> ValidationResult:
        """Validate output data against a contract."""
        start_time = time.perf_counter()

        result = ValidationResult(
            field_name=field_name or "output",
            value=data,
            original_value=data,
        )

        try:
            # Get contract if string name provided
            if isinstance(contract, str):
                contract = self.get_contract(contract)
                if contract is None:
                    result.add_error(f"Contract '{contract}' not found")
                    return result

            # Perform validation based on contract or data type
            if contract is not None:
                await self._validate_with_contract(data, contract, result)
            else:
                await self._validate_by_type(data, result)

        except Exception as e:
            result.add_error(f"Output validation failed: {e}")

        result.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    async def _validate_with_contract(
        self,
        data: t.Any,
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Validate data against a specific contract."""
        if contract.output_type == OutputType.DICT:
            await self._validate_dict_contract(data, contract, result)
        elif contract.output_type == OutputType.LIST:
            await self._validate_list_contract(data, contract, result)
        elif contract.output_type == OutputType.JSON_API:
            await self._validate_json_api_contract(data, contract, result)
        elif contract.output_type == OutputType.REST_API:
            await self._validate_rest_api_contract(data, contract, result)
        elif contract.output_type == OutputType.MODEL:
            await self._validate_model_contract(data, contract, result)
        elif contract.output_type == OutputType.SCALAR:
            await self._validate_scalar_contract(data, contract, result)
        else:
            await self._validate_custom_contract(data, contract, result)

    def _check_required_fields_contract(
        self,
        data: dict[str, t.Any],
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Check for missing required fields."""
        for field_name in contract.required_fields:
            if field_name not in data:
                result.add_error(f"Required field '{field_name}' missing")

    def _check_field_types_contract(
        self,
        data: dict[str, t.Any],
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Check field types match contract specifications."""
        for field_name, expected_type in contract.field_types.items():
            if field_name not in data:
                continue

            value = data[field_name]
            if contract.strict_types and not isinstance(value, expected_type):
                result.add_error(
                    f"Field '{field_name}' type mismatch: "
                    f"expected {expected_type.__name__}, got {type(value).__name__}",
                )

    def _check_extra_fields_contract(
        self,
        data: dict[str, t.Any],
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Check for unexpected extra fields."""
        if contract.allow_extra_fields:
            return

        allowed_fields = set(contract.required_fields + contract.optional_fields)
        for field_name in data:
            if field_name not in allowed_fields:
                result.add_error(f"Unexpected field '{field_name}'")

    async def _validate_dict_contract(
        self,
        data: t.Any,
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Validate dictionary output contract."""
        if not isinstance(data, dict):
            result.add_error(f"Expected dict, got {type(data).__name__}")
            return

        self._check_required_fields_contract(data, contract, result)
        self._check_field_types_contract(data, contract, result)
        self._check_extra_fields_contract(data, contract, result)

    async def _validate_list_contract(
        self,
        data: t.Any,
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Validate list output contract."""
        if not isinstance(data, list | tuple):
            result.add_error(f"Expected list, got {type(data).__name__}")
            return

        # Check length constraints
        if contract.min_length is not None and len(data) < contract.min_length:
            result.add_error(f"List too short: {len(data)} < {contract.min_length}")

        if contract.max_length is not None and len(data) > contract.max_length:
            result.add_error(f"List too long: {len(data)} > {contract.max_length}")

    async def _validate_json_api_contract(
        self,
        data: t.Any,
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Validate JSON API response contract."""
        if not isinstance(data, dict):
            result.add_error("JSON API response must be a dictionary")
            return

        # JSON API typically has 'data', 'meta', 'errors' structure
        if "data" not in data and "errors" not in data:
            result.add_error("JSON API response must contain 'data' or 'errors'")

        # Validate standard JSON API fields
        if "data" in data:
            if data["data"] is not None and not isinstance(data["data"], dict | list):
                result.add_error("JSON API 'data' must be object, array, or null")

        if "meta" in data and not isinstance(data["meta"], dict):
            result.add_error("JSON API 'meta' must be an object")

        if "errors" in data and not isinstance(data["errors"], list):
            result.add_error("JSON API 'errors' must be an array")

    async def _validate_rest_api_contract(
        self,
        data: t.Any,
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Validate REST API response contract."""
        # REST API validation is similar to dict validation but with
        # common patterns for status, message, data structure
        if isinstance(data, dict):
            # Common REST patterns: status, success, message, data
            common_fields = {"status", "success", "message", "data", "error", "errors"}
            found_common = any(field in data for field in common_fields)

            if not found_common:
                result.add_warning("REST API response doesn't follow common patterns")

        # Delegate to dict validation for detailed checks
        await self._validate_dict_contract(data, contract, result)

    async def _validate_model_contract(
        self,
        data: t.Any,
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Validate model instance contract."""
        # Check if data has expected model attributes
        for field_name in contract.required_fields:
            if not hasattr(data, field_name):
                result.add_error(f"Model missing required attribute '{field_name}'")

        # Type validation for model attributes
        for field_name, expected_type in contract.field_types.items():
            if hasattr(data, field_name):
                value = getattr(data, field_name)
                if contract.strict_types and not isinstance(value, expected_type):
                    result.add_error(
                        f"Model attribute '{field_name}' type mismatch: "
                        f"expected {expected_type.__name__}, got {type(value).__name__}",
                    )

    async def _validate_scalar_contract(
        self,
        data: t.Any,
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Validate scalar value contract."""
        # Type validation
        if contract.field_types.get("value"):
            expected_type = contract.field_types["value"]
            if contract.strict_types and not isinstance(data, expected_type):
                result.add_error(
                    f"Scalar type mismatch: "
                    f"expected {expected_type.__name__}, got {type(data).__name__}",
                )

        # Length validation for strings
        if isinstance(data, str):
            if contract.min_length is not None and len(data) < contract.min_length:
                result.add_error(
                    f"String too short: {len(data)} < {contract.min_length}",
                )

            if contract.max_length is not None and len(data) > contract.max_length:
                result.add_error(
                    f"String too long: {len(data)} > {contract.max_length}",
                )

    async def _validate_custom_contract(
        self,
        data: t.Any,
        contract: OutputContract,
        result: ValidationResult,
    ) -> None:
        """Validate using custom validators."""
        for validator in contract.custom_validators:
            try:
                if not validator(data):
                    result.add_error("Custom validation failed")
            except Exception as e:
                result.add_error(f"Custom validator error: {e}")

    async def _validate_by_type(self, data: t.Any, result: ValidationResult) -> None:
        """Validate based on data type when no contract is provided."""
        data_type = type(data)

        if data_type is dict:
            # Basic dict validation
            if not data:
                result.add_warning("Empty dictionary output")

        elif data_type in (list, tuple):
            # Basic list validation
            if not data:
                result.add_warning("Empty list output")

        elif data_type is str:
            # Basic string validation
            if not data.strip():
                result.add_warning("Empty or whitespace-only string output")

            # Check for very long strings (potential issue)
            if len(data) > self.config.max_string_length:
                result.add_warning(f"Very long string output: {len(data)} characters")

        # All outputs pass basic validation unless specific issues found
        # This allows for flexible output handling while flagging potential issues


class ResponseValidator:
    """Specialized validator for HTTP response-like structures."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()
        self.output_validator = OutputValidator(config)

    async def validate_http_response(
        self,
        data: t.Any,
        expected_status_codes: list[int] | None = None,
        require_body: bool = True,
    ) -> ValidationResult:
        """Validate HTTP response structure."""
        result = ValidationResult(
            field_name="http_response",
            value=data,
            original_value=data,
        )

        if not isinstance(data, dict):
            result.add_error("HTTP response must be a dictionary")
            return result

        # Check for standard HTTP response fields
        if "status" in data or "status_code" in data:
            status = data.get("status") or data.get("status_code")
            if expected_status_codes and status not in expected_status_codes:
                result.add_error(f"Unexpected status code: {status}")

        if require_body and "body" not in data and "data" not in data:
            result.add_error("HTTP response missing body/data")

        # Validate headers if present
        if "headers" in data and not isinstance(data["headers"], dict):
            result.add_error("HTTP response headers must be a dictionary")

        return result

    async def validate_api_error_response(self, data: t.Any) -> ValidationResult:
        """Validate API error response structure."""
        result = ValidationResult(
            field_name="error_response",
            value=data,
            original_value=data,
        )

        if not isinstance(data, dict):
            result.add_error("Error response must be a dictionary")
            return result

        # Check for error fields
        error_fields = {"error", "errors", "message", "detail"}
        found_error_field = any(field in data for field in error_fields)

        if not found_error_field:
            result.add_error("Error response missing error information")

        # Validate error structure
        if "errors" in data and not isinstance(data["errors"], list | dict):
            result.add_error("Errors field must be list or object")

        return result

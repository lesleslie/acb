"""Type coercion and data transformation helpers.

This module provides safe type coercion, data transformation utilities,
and format validation for the ACB validation system.
"""

from __future__ import annotations

import re
import time
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import UUID

import typing as t
from contextlib import suppress
from datetime import UTC, datetime

from acb.services.validation._base import ValidationConfig, ValidationResult


class CoercionStrategy(Enum):
    """Strategies for type coercion."""

    STRICT = "strict"  # No coercion, exact type match required
    SAFE = "safe"  # Safe coercion with validation
    PERMISSIVE = "permissive"  # Aggressive coercion, may lose precision
    SMART = "smart"  # Intelligent coercion based on data analysis


class TypeCoercer:
    """Main type coercion service."""

    def __init__(
        self,
        config: ValidationConfig | None = None,
        strategy: CoercionStrategy = CoercionStrategy.SAFE,
    ) -> None:
        self.config = config or ValidationConfig()
        self.strategy = strategy

    async def coerce_to_type(
        self,
        data: t.Any,
        target_type: type[t.Any],
        field_name: str | None = None,
    ) -> ValidationResult:
        """Coerce data to target type using configured strategy."""
        start_time = time.perf_counter()

        result = ValidationResult(
            field_name=field_name,
            value=data,
            original_value=data,
        )

        # Skip coercion if already correct type
        if isinstance(data, target_type):
            result.validation_time_ms = (time.perf_counter() - start_time) * 1000
            return result

        if self.strategy == CoercionStrategy.STRICT:
            result.add_error(
                f"Type mismatch: expected {target_type.__name__}, got {type(data).__name__}",
            )
            result.validation_time_ms = (time.perf_counter() - start_time) * 1000
            return result

        try:
            coerced_value = await self._perform_coercion(data, target_type)
            result.value = coerced_value
            result.add_warning(
                f"Value coerced from {type(data).__name__} to {target_type.__name__}",
            )

        except Exception as e:
            result.add_error(f"Coercion failed: {e}")

        result.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    async def _perform_coercion(self, data: t.Any, target_type: type[t.Any]) -> t.Any:
        """Perform the actual type coercion."""
        # Handle None values
        if data is None:
            if target_type in (str, list, dict, set, tuple):
                return target_type()
            return None

        # String coercion
        if target_type is str:
            return str(data)

        # Integer coercion
        if target_type is int:
            return await self._coerce_to_int(data)

        # Float coercion
        if target_type is float:
            return await self._coerce_to_float(data)

        # Boolean coercion
        if target_type is bool:
            return await self._coerce_to_bool(data)

        # List coercion
        if target_type is list:
            return await self._coerce_to_list(data)

        # Dict coercion
        if target_type is dict:
            return await self._coerce_to_dict(data)

        # Set coercion
        if target_type is set:
            return await self._coerce_to_set(data)

        # Tuple coercion
        if target_type is tuple:
            return await self._coerce_to_tuple(data)

        # Decimal coercion
        if target_type == Decimal:
            return await self._coerce_to_decimal(data)

        # Datetime coercion
        if target_type == datetime:
            return await self._coerce_to_datetime(data)

        # UUID coercion
        if target_type == UUID:
            return await self._coerce_to_uuid(data)

        # Generic coercion attempt
        return target_type(data)

    async def _coerce_to_int(self, data: t.Any) -> int:
        """Coerce data to integer."""
        if isinstance(data, bool):
            return int(data)

        if isinstance(data, int | float):
            return self._coerce_numeric_to_int(data)

        if isinstance(data, str):
            return self._coerce_string_to_int(data)

        if isinstance(data, Decimal):
            return self._coerce_decimal_to_int(data)

        return int(data)

    def _coerce_numeric_to_int(self, data: int | float) -> int:
        """Coerce numeric type to int."""
        if isinstance(data, float) and not data.is_integer():
            if self.strategy == CoercionStrategy.PERMISSIVE:
                return int(data)  # Truncate
            msg = f"Cannot coerce float {data} to int without precision loss"
            raise ValueError(msg)
        return int(data)

    def _coerce_string_to_int(self, data: str) -> int:
        """Coerce string to int."""
        data = data.strip()

        # Handle boolean-like strings
        if bool_int := self._try_bool_string_to_int(data):
            return bool_int

        # Handle decimal strings
        if "." in data:
            return self._convert_decimal_string_to_int(data)

        # Try direct conversion or with comma removal
        try:
            return int(data)
        except ValueError:
            clean_data = data.replace(",", "")
            return int(clean_data)

    def _try_bool_string_to_int(self, data: str) -> int | None:
        """Try to convert boolean-like string to int. Returns None if not boolean-like."""
        if data.lower() in ("true", "yes", "on", "1"):
            return 1
        if data.lower() in ("false", "no", "off", "0"):
            return 0
        return None

    def _convert_decimal_string_to_int(self, data: str) -> int:
        """Convert decimal string to int if it represents an integer value."""
        float_val = float(data)
        if float_val.is_integer():
            return int(float_val)
        msg = f"Cannot convert decimal string '{data}' to int"
        raise ValueError(msg)

    def _coerce_decimal_to_int(self, data: Decimal) -> int:
        """Coerce Decimal to int."""
        if data % 1 == 0:
            return int(data)
        msg = f"Cannot convert Decimal {data} to int without precision loss"
        raise ValueError(msg)

    async def _coerce_to_float(self, data: t.Any) -> float:
        """Coerce data to float."""
        if isinstance(data, int | float | bool):
            return float(data)
        if isinstance(data, str):
            data = data.strip()
            if data.lower() in ("true", "yes", "on"):
                return 1.0
            if data.lower() in ("false", "no", "off"):
                return 0.0
            # Handle common string representations
            clean_data = data.replace(",", "")  # Remove commas
            return float(clean_data)
        if isinstance(data, Decimal):
            return float(data)
        return float(data)

    async def _coerce_to_bool(self, data: t.Any) -> bool:
        """Coerce data to boolean."""
        if isinstance(data, bool):
            return data
        if isinstance(data, int | float):
            return bool(data)
        if isinstance(data, str):
            data = data.strip().lower()
            if data in ("true", "yes", "on", "1", "y", "t"):
                return True
            if data in ("false", "no", "off", "0", "n", "f", ""):
                return False
            # Try numeric conversion
            try:
                return bool(float(data))
            except ValueError:
                msg = f"Cannot convert string '{data}' to bool"
                raise ValueError(msg)
        elif data is None:
            return False
        else:
            return bool(data)

    async def _coerce_to_list(self, data: t.Any) -> list[t.Any]:
        """Coerce data to list."""
        if isinstance(data, list):
            return data
        if isinstance(data, tuple | set):
            return list(data)
        if isinstance(data, str):
            # Try to parse comma-separated values
            if "," in data:
                return [item.strip() for item in data.split(",")]
            return [data]
        if hasattr(data, "__iter__") and not isinstance(data, str | bytes | dict):
            return list(data)
        return [data]

    async def _coerce_to_dict(self, data: t.Any) -> dict[str, t.Any]:
        """Coerce data to dictionary."""
        if isinstance(data, dict):
            return data
        if hasattr(data, "__dict__"):
            return data.__dict__.copy()
        if isinstance(data, str):
            # Try to parse JSON-like string
            import json

            with suppress(json.JSONDecodeError, ValueError):
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed

            # Return single-item dict
            return {"value": data}
        return {"value": data}

    async def _coerce_to_set(self, data: t.Any) -> set[t.Any]:
        """Coerce data to set."""
        if isinstance(data, set):
            return data
        if isinstance(data, list | tuple):
            return set(data)
        if isinstance(data, str):
            if "," in data:
                return {item.strip() for item in data.split(",")}
            return {data}
        if hasattr(data, "__iter__") and not isinstance(data, str | bytes | dict):
            return set(data)
        return {data}

    async def _coerce_to_tuple(self, data: t.Any) -> tuple[t.Any, ...]:
        """Coerce data to tuple."""
        if isinstance(data, tuple):
            return data
        if isinstance(data, list | set):
            return tuple(data)
        if isinstance(data, str):
            if "," in data:
                return tuple(item.strip() for item in data.split(","))
            return (data,)
        if hasattr(data, "__iter__") and not isinstance(data, str | bytes | dict):
            return tuple(data)
        return (data,)

    async def _coerce_to_decimal(self, data: t.Any) -> Decimal:
        """Coerce data to Decimal."""
        if isinstance(data, Decimal):
            return data
        if isinstance(data, int | float):
            return Decimal(str(data))
        if isinstance(data, str):
            data = data.strip().replace(",", "")
            try:
                return Decimal(data)
            except InvalidOperation as e:
                msg = f"Cannot convert string '{data}' to Decimal: {e}"
                raise ValueError(msg)
        else:
            return Decimal(str(data))

    async def _coerce_to_datetime(self, data: t.Any) -> datetime:
        """Coerce data to datetime."""
        if isinstance(data, datetime):
            return data
        if isinstance(data, int | float):
            # Assume Unix timestamp
            return datetime.fromtimestamp(data, tz=UTC)
        if isinstance(data, str):
            # Try common datetime formats
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
            ]

            data = data.strip()
            for fmt in formats:
                try:
                    return datetime.strptime(data, fmt)
                except ValueError:
                    continue

            # Try parsing ISO format
            with suppress(ValueError):
                return datetime.fromisoformat(data)

            msg = f"Cannot parse datetime string: {data}"
            raise ValueError(msg)
        msg = f"Cannot convert {type(data).__name__} to datetime"
        raise ValueError(msg)

    async def _coerce_to_uuid(self, data: t.Any) -> UUID:
        """Coerce data to UUID."""
        if isinstance(data, UUID):
            return data
        if isinstance(data, str):
            return UUID(data.strip())
        return UUID(str(data))


class DataTransformer:
    """Data transformation utilities."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

    async def normalize_string(self, data: str) -> ValidationResult:
        """Normalize string data."""
        result = ValidationResult(value=data, original_value=data)

        try:
            normalized = data.strip()

            # Normalize whitespace
            normalized = re.sub(
                r"\s+",
                " ",
                normalized,
            )  # REGEX OK: String normalization

            # Unicode normalization
            import unicodedata

            normalized = unicodedata.normalize("NFKC", normalized)

            result.value = normalized

            if normalized != data:
                result.add_warning("String normalized")

        except Exception as e:
            result.add_error(f"String normalization failed: {e}")

        return result

    async def transform_case(
        self,
        data: str,
        case_type: str = "lower",
    ) -> ValidationResult:
        """Transform string case."""
        result = ValidationResult(value=data, original_value=data)

        try:
            if case_type == "lower":
                result.value = data.lower()
            elif case_type == "upper":
                result.value = data.upper()
            elif case_type == "title":
                result.value = data.title()
            elif case_type == "capitalize":
                result.value = data.capitalize()
            elif case_type == "snake":
                # Convert to snake_case
                result.value = (
                    re.sub(r"[A-Z]", r"_\g<0>", data).lower().lstrip("_")
                )  # REGEX OK: Case conversion
            elif case_type == "camel":
                # Convert to camelCase
                components = data.split("_")
                result.value = components[0] + "".join(
                    x.title() for x in components[1:]
                )
            elif case_type == "pascal":
                # Convert to PascalCase
                components = data.split("_")
                result.value = "".join(x.title() for x in components)
            else:
                result.add_error(f"Unknown case type: {case_type}")

            if result.value != data:
                result.add_warning(f"Case transformed to {case_type}")

        except Exception as e:
            result.add_error(f"Case transformation failed: {e}")

        return result


class FormatValidator:
    """Format validation utilities."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

        # Compiled regex patterns for performance
        self._email_pattern = re.compile(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",  # REGEX OK: Email format validation
        )
        self._phone_pattern = re.compile(
            r"^\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$",  # REGEX OK: Phone number format validation
        )
        self._url_pattern = re.compile(
            r"^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w)*))?$",  # REGEX OK: URL format validation
        )
        self._ipv4_pattern = re.compile(
            r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",  # REGEX OK: IPv4 address format validation
        )

    async def validate_email(self, data: str) -> ValidationResult:
        """Validate email format."""
        result = ValidationResult(value=data, original_value=data)

        if not isinstance(data, str):
            result.add_error("Email must be a string")
            return result

        email = data.strip().lower()
        if not self._email_pattern.match(email):
            result.add_error("Invalid email format")
        else:
            result.value = email
            if email != data:
                result.add_warning("Email normalized")

        return result

    async def validate_phone(self, data: str) -> ValidationResult:
        """Validate phone number format."""
        result = ValidationResult(value=data, original_value=data)

        if not isinstance(data, str):
            result.add_error("Phone number must be a string")
            return result

        if not self._phone_pattern.match(data):
            result.add_error("Invalid phone number format")

        return result

    async def validate_url(self, data: str) -> ValidationResult:
        """Validate URL format."""
        result = ValidationResult(value=data, original_value=data)

        if not isinstance(data, str):
            result.add_error("URL must be a string")
            return result

        if not self._url_pattern.match(data):
            result.add_error("Invalid URL format")

        return result

    async def validate_ipv4(self, data: str) -> ValidationResult:
        """Validate IPv4 address format."""
        result = ValidationResult(value=data, original_value=data)

        if not isinstance(data, str):
            result.add_error("IP address must be a string")
            return result

        if not self._ipv4_pattern.match(data):
            result.add_error("Invalid IPv4 address format")

        return result


class RangeValidator:
    """Range validation for numeric and date values."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

    async def validate_numeric_range(
        self,
        data: float | Decimal,
        min_value: float | Decimal | None = None,
        max_value: float | Decimal | None = None,
    ) -> ValidationResult:
        """Validate numeric range."""
        result = ValidationResult(value=data, original_value=data)

        if not isinstance(data, int | float | Decimal):
            result.add_error(f"Expected numeric type, got {type(data).__name__}")
            return result

        if min_value is not None and data < min_value:
            result.add_error(f"Value {data} below minimum {min_value}")

        if max_value is not None and data > max_value:
            result.add_error(f"Value {data} above maximum {max_value}")

        return result

    async def validate_date_range(
        self,
        data: datetime,
        min_date: datetime | None = None,
        max_date: datetime | None = None,
    ) -> ValidationResult:
        """Validate date range."""
        result = ValidationResult(value=data, original_value=data)

        if not isinstance(data, datetime):
            result.add_error(f"Expected datetime, got {type(data).__name__}")
            return result

        if min_date is not None and data < min_date:
            result.add_error(f"Date {data} before minimum {min_date}")

        if max_date is not None and data > max_date:
            result.add_error(f"Date {data} after maximum {max_date}")

        return result

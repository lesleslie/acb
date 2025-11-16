"""Validation decorators for easy integration with ACB applications.

This module provides decorators that make it easy to add validation
to functions and methods with minimal code changes.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable

from typing import Any

from acb.depends import depends
from acb.services.validation._base import ValidationConfig, ValidationSchema
from acb.services.validation.results import ValidationError, ValidationReport
from acb.services.validation.service import ValidationService

# Helper Functions for Complexity Reduction


def _create_wrapper(
    func: Callable[..., Any],
    async_handler: Callable[..., Any],
) -> Callable[..., Any]:
    """Create appropriate wrapper based on function type.

    Args:
        func: Original function to wrap
        async_handler: Async handler function

    Returns:
        Async or sync wrapper based on function type
    """
    if inspect.iscoroutinefunction(func):
        return async_handler

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        import asyncio

        return asyncio.run(async_handler(*args, **kwargs))

    return sync_wrapper


def _bind_function_arguments(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> inspect.BoundArguments:
    """Bind function arguments with defaults applied.

    Args:
        func: Function to bind arguments for
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Bound arguments with defaults applied
    """
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()
    return bound_args


def _check_validation_errors(
    results: list[Any],
    raise_on_error: bool,
) -> None:
    """Check validation results and raise error if needed.

    Args:
        results: List of validation results
        raise_on_error: Whether to raise on validation failure

    Raises:
        ValidationError: If validation failed and raise_on_error is True
    """
    if not results or not raise_on_error:
        return

    report = ValidationReport(results=results)
    if not report.is_valid:
        msg = f"Input validation failed: {'; '.join(report.get_all_errors())}"
        raise ValidationError(msg)


def _check_type_match(
    value: Any,
    expected_type: type,
    field_name: str,
    context: str,
) -> None:
    """Check if value matches expected type.

    Args:
        value: Value to check
        expected_type: Expected type
        field_name: Name of field being checked
        context: Context string (input/output)

    Raises:
        ValidationError: If type doesn't match
    """
    if not isinstance(value, expected_type):
        msg = (
            f"{context} contract violation: {field_name} "
            f"expected {expected_type.__name__}, got {type(value).__name__}"
        )
        raise ValidationError(msg)


async def _validate_dict_schema(
    service: ValidationService,
    schema_dict: dict[str, ValidationSchema],
    bound_args: inspect.BoundArguments,
    config: ValidationConfig | None,
) -> list[Any]:
    """Validate parameters using dictionary of schemas.

    Args:
        service: ValidationService instance
        schema_dict: Dictionary mapping parameter names to schemas
        bound_args: Bound function arguments
        config: Validation configuration

    Returns:
        List of validation results
    """
    results = []
    for param_name, param_schema in schema_dict.items():
        if param_name in bound_args.arguments:
            result = await service.validate(
                bound_args.arguments[param_name],
                param_schema,
                config,
                param_name,
            )
            results.append(result)
    return results


async def _validate_single_schema(
    service: ValidationService,
    schema: ValidationSchema,
    bound_args: inspect.BoundArguments,
    config: ValidationConfig | None,
) -> list[Any]:
    """Validate first parameter using single schema.

    Args:
        service: ValidationService instance
        schema: Validation schema
        bound_args: Bound function arguments
        config: Validation configuration

    Returns:
        List with single validation result
    """
    if not bound_args.arguments:
        return []

    first_param = next(iter(bound_args.arguments.values()))
    result = await service.validate(first_param, schema, config)
    return [result]


def _update_validated_arguments(
    bound_args: inspect.BoundArguments,
    results: list[Any],
    schema: ValidationSchema | dict[str, ValidationSchema] | None,
) -> None:
    """Update bound arguments with validated values.

    Args:
        bound_args: Bound arguments to update
        results: Validation results
        schema: Original schema (dict or single)
    """
    if not isinstance(schema, dict):
        return

    schema_keys = list(schema.keys())
    for i, result in enumerate(results):
        if result.is_valid and i < len(schema_keys):
            param_name = schema_keys[i]
            if param_name in bound_args.arguments:
                bound_args.arguments[param_name] = result.value


def validate_input(
    schema: ValidationSchema | dict[str, ValidationSchema] | None = None,
    config: ValidationConfig | None = None,
    raise_on_error: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to validate function input parameters.

    Args:
        schema: Validation schema(s) for parameters
        config: Validation configuration
        raise_on_error: Whether to raise ValidationError on validation failure

    Example:
        @validate_input({"name": StringValidationSchema("name", min_length=1)})
        async def create_user(name: str, email: str) -> User:
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            validation_service = await depends.get(ValidationService)
            bound_args = _bind_function_arguments(func, args, kwargs)

            # Execute appropriate validation strategy
            match schema:
                case dict():
                    results = await _validate_dict_schema(
                        validation_service,
                        schema,  # type: ignore[arg-type]
                        bound_args,
                        config,
                    )
                case ValidationSchema():
                    results = await _validate_single_schema(
                        validation_service,
                        schema,  # type: ignore[arg-type]
                        bound_args,
                        config,
                    )
                case _:
                    results = []

            _check_validation_errors(results, raise_on_error)
            _update_validated_arguments(bound_args, results, schema)

            return await func(**bound_args.arguments)

        return _create_wrapper(func, async_wrapper)

    return decorator


def validate_output(
    schema: ValidationSchema | None = None,
    config: ValidationConfig | None = None,
    raise_on_error: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to validate function output.

    Args:
        schema: Validation schema for output
        config: Validation configuration
        raise_on_error: Whether to raise ValidationError on validation failure

    Example:
        @validate_output(ModelValidationSchema("user", User))
        async def get_user(user_id: int) -> User:
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            if schema is None:
                return result

            validation_service = await depends.get(ValidationService)
            validation_result = await validation_service.validate(
                result,
                schema,
                config,
                "output",
            )

            if raise_on_error and not validation_result.is_valid:
                msg = f"Output validation failed: {'; '.join(validation_result.errors)}"
                raise ValidationError(msg)

            return validation_result.value

        return _create_wrapper(func, async_wrapper)

    return decorator


def _create_sanitize_config(
    config: ValidationConfig | None,
    enable_xss: bool,
    enable_sql: bool,
) -> ValidationConfig:
    """Create sanitization configuration.

    Args:
        config: Base configuration or None
        enable_xss: Enable XSS protection
        enable_sql: Enable SQL injection protection

    Returns:
        Configured ValidationConfig
    """
    sanitize_config = config or ValidationConfig()
    sanitize_config.enable_xss_protection = enable_xss
    sanitize_config.enable_sql_injection_protection = enable_sql
    sanitize_config.enable_sanitization = True
    return sanitize_config


async def _sanitize_parameters(
    service: ValidationService,
    bound_args: inspect.BoundArguments,
    fields: list[str] | None,
    sanitize_config: ValidationConfig,
) -> None:
    """Sanitize string parameters.

    Args:
        service: ValidationService instance
        bound_args: Bound arguments to sanitize
        fields: Fields to sanitize (None = all strings)
        sanitize_config: Sanitization configuration
    """
    for param_name, value in bound_args.arguments.items():
        should_sanitize = fields is None or param_name in fields
        if should_sanitize and isinstance(value, str):
            result = await service.validate(
                value,
                None,
                sanitize_config,
                param_name,
            )
            bound_args.arguments[param_name] = result.value


def sanitize_input(
    fields: list[str] | None = None,
    enable_xss_protection: bool = True,
    enable_sql_protection: bool = True,
    config: ValidationConfig | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to sanitize input parameters for security.

    Args:
        fields: List of parameter names to sanitize (None = all string params)
        enable_xss_protection: Enable XSS protection
        enable_sql_protection: Enable SQL injection protection
        config: Custom validation configuration

    Example:
        @sanitize_input(fields=["content", "title"])
        async def create_post(title: str, content: str) -> Post:
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            validation_service = await depends.get(ValidationService)
            bound_args = _bind_function_arguments(func, args, kwargs)

            sanitize_config = _create_sanitize_config(
                config,
                enable_xss_protection,
                enable_sql_protection,
            )

            await _sanitize_parameters(
                validation_service,
                bound_args,
                fields,
                sanitize_config,
            )

            return await func(**bound_args.arguments)

        return _create_wrapper(func, async_wrapper)

    return decorator


def _get_validation_data(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any | None:
    """Extract data to validate from args or kwargs.

    Args:
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Data to validate or None
    """
    if kwargs:
        return kwargs
    if args:
        return args[0]
    return None


def _update_validated_data(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    validated_value: Any,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Update args/kwargs with validated value.

    Args:
        args: Original positional arguments
        kwargs: Original keyword arguments
        validated_value: Validated value to use

    Returns:
        Tuple of (updated_args, updated_kwargs)
    """
    if kwargs:
        updated_kwargs = kwargs.copy()
        if isinstance(validated_value, dict):
            updated_kwargs.update(validated_value)
        return args, updated_kwargs

    if args:
        return (validated_value, *args[1:]), kwargs

    return args, kwargs


def validate_schema(
    schema_name: str,
    config: ValidationConfig | None = None,
    raise_on_error: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to validate using a registered schema.

    Args:
        schema_name: Name of registered schema
        config: Validation configuration
        raise_on_error: Whether to raise ValidationError on validation failure

    Example:
        @validate_schema("user_creation")
        async def create_user(**user_data) -> User:
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            validation_service = await depends.get(ValidationService)

            schema = await validation_service.get_schema(schema_name)
            if schema is None:
                if raise_on_error:
                    msg = f"Schema '{schema_name}' not found"
                    raise ValidationError(msg)
                return await func(*args, **kwargs)

            data_to_validate = _get_validation_data(args, kwargs)
            if data_to_validate is None:
                return await func(*args, **kwargs)

            result = await validation_service.validate(
                data_to_validate,
                schema,
                config,
            )

            if raise_on_error and not result.is_valid:
                msg = f"Schema validation failed: {'; '.join(result.errors)}"
                raise ValidationError(msg)

            updated_args, updated_kwargs = _update_validated_data(
                args,
                kwargs,
                result.value,
            )

            return await func(*updated_args, **updated_kwargs)

        return _create_wrapper(func, async_wrapper)

    return decorator


def _validate_input_contract(
    bound_args: inspect.BoundArguments,
    contract: dict[str, type],
) -> None:
    """Validate input parameters against contract.

    Args:
        bound_args: Bound function arguments
        contract: Expected parameter types

    Raises:
        ValidationError: If any parameter violates contract
    """
    for param_name, expected_type in contract.items():
        if param_name not in bound_args.arguments:
            continue

        value = bound_args.arguments[param_name]
        _check_type_match(value, expected_type, param_name, "Input")


def _validate_output_contract(
    result: Any,
    contract: dict[str, type],
) -> None:
    """Validate output result against contract.

    Args:
        result: Function result to validate
        contract: Expected output field types

    Raises:
        ValidationError: If any field violates contract
    """
    if not isinstance(result, dict):
        return

    for field_name, expected_type in contract.items():
        if field_name not in result:
            continue

        value = result[field_name]
        _check_type_match(value, expected_type, field_name, "Output")


def validate_contracts(
    input_contract: dict[str, Any] | None = None,
    output_contract: dict[str, Any] | None = None,
    config: ValidationConfig | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to validate API contracts for input and output.

    Args:
        input_contract: Expected input format/types
        output_contract: Expected output format/types
        config: Validation configuration

    Example:
        @validate_contracts(
            input_contract={"name": str, "email": str},
            output_contract={"id": int, "name": str, "email": str}
        )
        async def create_user(name: str, email: str) -> dict:
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            await depends.get(ValidationService)

            if input_contract is not None:
                bound_args = _bind_function_arguments(func, args, kwargs)
                _validate_input_contract(bound_args, input_contract)

            result = await func(*args, **kwargs)

            if output_contract is not None:
                _validate_output_contract(result, output_contract)

            return result

        return _create_wrapper(func, async_wrapper)

    return decorator


def _filter_method_params(
    bound_args: inspect.BoundArguments,
) -> dict[str, Any]:
    """Filter out 'self' parameter from bound arguments.

    Args:
        bound_args: Bound method arguments

    Returns:
        Parameters dictionary without 'self'
    """
    params = dict(bound_args.arguments)
    params.pop("self", None)
    return params


async def _validate_method_inputs(
    service: ValidationService,
    schemas: dict[str, ValidationSchema],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Validate method input parameters.

    Args:
        service: ValidationService instance
        schemas: Input validation schemas
        params: Method parameters to validate

    Returns:
        Validated parameters

    Raises:
        ValidationError: If validation fails
    """
    validated_params = params.copy()

    for param_name, schema in schemas.items():
        if param_name not in params:
            continue

        result = await service.validate(
            params[param_name],
            schema,
            None,
            param_name,
        )

        if not result.is_valid:
            msg = (
                f"Method input validation failed for {param_name}: "
                f"{'; '.join(result.errors)}"
            )
            raise ValidationError(msg)

        validated_params[param_name] = result.value

    return validated_params


async def _validate_method_output(
    service: ValidationService,
    result: Any,
    schema: ValidationSchema,
) -> Any:
    """Validate method output.

    Args:
        service: ValidationService instance
        result: Method result to validate
        schema: Output validation schema

    Returns:
        Validated result

    Raises:
        ValidationError: If validation fails
    """
    validation_result = await service.validate(
        result,
        schema,
        None,
        "output",
    )

    if not validation_result.is_valid:
        msg = f"Method output validation failed: {'; '.join(validation_result.errors)}"
        raise ValidationError(msg)

    return validation_result.value


class ValidationDecorators:
    """Class-based validation decorators for more complex scenarios."""

    def __init__(self, validation_service: ValidationService | None = None) -> None:
        self._validation_service = validation_service

    @property
    def validation_service(self) -> ValidationService:
        """Get ValidationService instance."""
        if self._validation_service is None:
            self._validation_service = depends.get_sync(ValidationService)
        return self._validation_service

    def method_validator(
        self,
        input_schemas: dict[str, ValidationSchema] | None = None,
        output_schema: ValidationSchema | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator for class method validation.

        Example:
            class UserService:
                @validators.method_validator(
                    input_schemas={"name": StringValidationSchema("name")},
                    output_schema=ModelValidationSchema("user", User)
                )
                async def create_user(self, name: str) -> User:
                    ...
        """

        def decorator(method: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(method)
            async def async_wrapper(
                instance: Any,
                *args: Any,
                **kwargs: Any,
            ) -> Any:
                if input_schemas:
                    sig = inspect.signature(method)
                    bound_args = sig.bind(instance, *args, **kwargs)
                    bound_args.apply_defaults()

                    params = _filter_method_params(bound_args)
                    validated_params = await _validate_method_inputs(
                        self.validation_service,
                        input_schemas,
                        params,
                    )

                    bound_args.arguments.update(validated_params)
                    result = await method(**bound_args.arguments)
                else:
                    result = await method(instance, *args, **kwargs)

                if output_schema:
                    return await _validate_method_output(
                        self.validation_service,
                        result,
                        output_schema,
                    )

                return result

            return _create_wrapper(method, async_wrapper)

        return decorator


# Create a default instance for convenience
validators = ValidationDecorators()

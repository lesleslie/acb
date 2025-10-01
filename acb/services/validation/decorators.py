"""Validation decorators for easy integration with ACB applications.

This module provides decorators that make it easy to add validation
to functions and methods with minimal code changes.
"""

from __future__ import annotations

import functools
import inspect
import typing as t

from acb.depends import depends
from acb.services.validation._base import ValidationConfig, ValidationSchema
from acb.services.validation.results import ValidationError, ValidationReport
from acb.services.validation.service import ValidationService


def validate_input(
    schema: ValidationSchema | dict[str, ValidationSchema] | None = None,
    config: ValidationConfig | None = None,
    raise_on_error: bool = True,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
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

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            # Get ValidationService
            validation_service = depends.get(ValidationService)

            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Validate parameters
            validation_results = []

            if isinstance(schema, dict):
                # Validate specific parameters
                for param_name, param_schema in schema.items():
                    if param_name in bound_args.arguments:
                        result = await validation_service.validate(
                            bound_args.arguments[param_name],
                            param_schema,
                            config,
                            param_name,
                        )
                        validation_results.append(result)
            elif schema is not None:
                # Single schema validation for first parameter
                if bound_args.arguments:
                    first_param = next(iter(bound_args.arguments.values()))
                    result = await validation_service.validate(
                        first_param,
                        schema,
                        config,
                    )
                    validation_results.append(result)

            # Check validation results
            if validation_results and raise_on_error:
                report = ValidationReport(results=validation_results)
                if not report.is_valid:
                    msg = (
                        f"Input validation failed: {'; '.join(report.get_all_errors())}"
                    )
                    raise ValidationError(
                        msg,
                    )

            # Update arguments with validated values
            for i, result in enumerate(validation_results):
                if result.is_valid and isinstance(schema, dict):
                    param_name = list(schema.keys())[i]
                    if param_name in bound_args.arguments:
                        bound_args.arguments[param_name] = result.value

            return await func(**bound_args.arguments)

        @functools.wraps(func)
        def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            import asyncio

            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def validate_output(
    schema: ValidationSchema | None = None,
    config: ValidationConfig | None = None,
    raise_on_error: bool = True,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
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

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            # Execute original function
            result = await func(*args, **kwargs)

            if schema is not None:
                # Get ValidationService
                validation_service = depends.get(ValidationService)

                # Validate output
                validation_result = await validation_service.validate(
                    result,
                    schema,
                    config,
                    "output",
                )

                if raise_on_error and not validation_result.is_valid:
                    msg = f"Output validation failed: {'; '.join(validation_result.errors)}"
                    raise ValidationError(
                        msg,
                    )

                # Return validated output
                return validation_result.value

            return result

        @functools.wraps(func)
        def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            import asyncio

            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def sanitize_input(
    fields: list[str] | None = None,
    enable_xss_protection: bool = True,
    enable_sql_protection: bool = True,
    config: ValidationConfig | None = None,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
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

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            # Get ValidationService
            validation_service = depends.get(ValidationService)

            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Create sanitization config
            sanitize_config = config or ValidationConfig()
            sanitize_config.enable_xss_protection = enable_xss_protection
            sanitize_config.enable_sql_injection_protection = enable_sql_protection
            sanitize_config.enable_sanitization = True

            # Sanitize parameters
            for param_name, value in bound_args.arguments.items():
                if fields is None or param_name in fields:
                    if isinstance(value, str):
                        result = await validation_service.validate(
                            value,
                            None,  # Use basic validation
                            sanitize_config,
                            param_name,
                        )
                        bound_args.arguments[param_name] = result.value

            return await func(**bound_args.arguments)

        @functools.wraps(func)
        def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            import asyncio

            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def validate_schema(
    schema_name: str,
    config: ValidationConfig | None = None,
    raise_on_error: bool = True,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
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

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            # Get ValidationService
            validation_service = depends.get(ValidationService)

            # Get registered schema
            schema = await validation_service.get_schema(schema_name)
            if schema is None:
                if raise_on_error:
                    msg = f"Schema '{schema_name}' not found"
                    raise ValidationError(msg)
                return await func(*args, **kwargs)

            # Validate first argument or kwargs
            data_to_validate = kwargs if kwargs else (args[0] if args else None)

            if data_to_validate is not None:
                result = await validation_service.validate(
                    data_to_validate,
                    schema,
                    config,
                )

                if raise_on_error and not result.is_valid:
                    msg = f"Schema validation failed: {'; '.join(result.errors)}"
                    raise ValidationError(
                        msg,
                    )

                # Update data with validated values
                if kwargs:
                    kwargs.update(
                        result.value if isinstance(result.value, dict) else kwargs,
                    )
                elif args:
                    args = (result.value, *args[1:])

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            import asyncio

            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def validate_contracts(
    input_contract: dict[str, t.Any] | None = None,
    output_contract: dict[str, t.Any] | None = None,
    config: ValidationConfig | None = None,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
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

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            depends.get(ValidationService)

            # Validate input contract
            if input_contract is not None:
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                for param_name, expected_type in input_contract.items():
                    if param_name in bound_args.arguments:
                        value = bound_args.arguments[param_name]
                        if not isinstance(value, expected_type):
                            msg = (
                                f"Input contract violation: {param_name} "
                                f"expected {expected_type.__name__}, got {type(value).__name__}"
                            )
                            raise ValidationError(
                                msg,
                            )

            # Execute function
            result = await func(*args, **kwargs)

            # Validate output contract
            if output_contract is not None:
                if isinstance(result, dict):
                    for field_name, expected_type in output_contract.items():
                        if field_name in result:
                            value = result[field_name]
                            if not isinstance(value, expected_type):
                                msg = (
                                    f"Output contract violation: {field_name} "
                                    f"expected {expected_type.__name__}, got {type(value).__name__}"
                                )
                                raise ValidationError(
                                    msg,
                                )

            return result

        @functools.wraps(func)
        def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            import asyncio

            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class ValidationDecorators:
    """Class-based validation decorators for more complex scenarios."""

    def __init__(self, validation_service: ValidationService | None = None) -> None:
        self._validation_service = validation_service

    @property
    def validation_service(self) -> ValidationService:
        """Get ValidationService instance."""
        if self._validation_service is None:
            self._validation_service = depends.get(ValidationService)
        return self._validation_service

    def method_validator(
        self,
        input_schemas: dict[str, ValidationSchema] | None = None,
        output_schema: ValidationSchema | None = None,
    ) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
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

        def decorator(method: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            @functools.wraps(method)
            async def async_wrapper(
                instance: t.Any,
                *args: t.Any,
                **kwargs: t.Any,
            ) -> t.Any:
                # Input validation
                if input_schemas:
                    sig = inspect.signature(method)
                    bound_args = sig.bind(instance, *args, **kwargs)
                    bound_args.apply_defaults()

                    # Skip 'self' parameter
                    params = dict(bound_args.arguments)
                    params.pop("self", None)

                    for param_name, schema in input_schemas.items():
                        if param_name in params:
                            result = await self.validation_service.validate(
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
                                raise ValidationError(
                                    msg,
                                )
                            params[param_name] = result.value

                    # Update bound arguments
                    bound_args.arguments.update(params)
                    result = await method(**bound_args.arguments)
                else:
                    result = await method(instance, *args, **kwargs)

                # Output validation
                if output_schema:
                    validation_result = await self.validation_service.validate(
                        result,
                        output_schema,
                        None,
                        "output",
                    )
                    if not validation_result.is_valid:
                        msg = (
                            f"Method output validation failed: "
                            f"{'; '.join(validation_result.errors)}"
                        )
                        raise ValidationError(
                            msg,
                        )
                    return validation_result.value

                return result

            @functools.wraps(method)
            def sync_wrapper(instance: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
                import asyncio

                return asyncio.run(async_wrapper(instance, *args, **kwargs))

            # Return appropriate wrapper based on method type
            if inspect.iscoroutinefunction(method):
                return async_wrapper
            return sync_wrapper

        return decorator


# Create a default instance for convenience
validators = ValidationDecorators()

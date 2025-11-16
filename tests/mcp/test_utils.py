"""Tests for the ACB MCP utils module."""

import pytest

from acb.mcp.utils import (
    async_retry,
    format_tool_response,
    get_parameter,
    serialize_component_info,
    validate_parameters,
)


class MockComponent:
    """Mock component for testing serialization."""

    def __init__(self) -> None:
        self.attribute1 = "value1"
        self._private_attr = "private"

    def public_method(self) -> str:
        return "public"

    def _private_method(self) -> str:
        return "private"


class TestSerializeComponentInfo:
    """Test the serialize_component_info function."""

    def test_serialize_component_info_basic(self) -> None:
        """Test basic component serialization."""
        component = MockComponent()
        result = serialize_component_info(component)

        assert result["type"] == "MockComponent"
        # The module name might vary depending on how the test is run
        assert "test_utils" in result["module"]
        assert "public_method" in result["methods"]
        assert "attribute1" in result["attributes"]
        assert "_private_attr" not in result["attributes"]
        assert "_private_method" not in result["methods"]

    def test_serialize_component_info_with_exception(self) -> None:
        """Test serialization when an exception occurs."""

        class ReallyBadComponent:
            def __getattribute__(self, name):
                # This will cause issues even when trying to get the class name
                raise RuntimeError("Really bad component")

        result = serialize_component_info(ReallyBadComponent())
        assert result["type"] == "Unknown"
        assert "error" in result


class TestFormatToolResponse:
    """Test the format_tool_response function."""

    def test_format_dict_response(self) -> None:
        """Test formatting a dictionary response."""
        response = {"key": "value"}
        result = format_tool_response(response)
        assert result == {"key": "value"}

    def test_format_list_response(self) -> None:
        """Test formatting a list response."""
        response = ["item1", "item2"]
        result = format_tool_response(response)
        assert result == {"items": ["item1", "item2"]}

    def test_format_tuple_response(self) -> None:
        """Test formatting a tuple response."""
        response = ("item1", "item2")
        result = format_tool_response(response)
        assert result == {"items": ["item1", "item2"]}

    def test_format_primitive_response(self) -> None:
        """Test formatting primitive responses."""
        assert format_tool_response("string") == {"value": "string"}
        assert format_tool_response(42) == {"value": 42}
        assert format_tool_response(3.14) == {"value": 3.14}
        assert format_tool_response(True) == {"value": True}

    def test_format_other_response(self) -> None:
        """Test formatting other types of responses."""

        class CustomClass:
            def __str__(self) -> str:
                return "Custom"

        result = format_tool_response(CustomClass())
        assert result == {"value": "Custom"}


class TestValidateParameters:
    """Test the validate_parameters function."""

    def test_validate_parameters_all_present(self) -> None:
        """Test validation when all required parameters are present."""
        parameters = {"param1": "value1", "param2": "value2"}
        required = ["param1", "param2"]
        assert validate_parameters(parameters, required)

    def test_validate_parameters_missing_one(self) -> None:
        """Test validation when one required parameter is missing."""
        parameters = {"param1": "value1", "param3": "value3"}
        required = ["param1", "param2", "param3"]
        assert not validate_parameters(parameters, required)

    def test_validate_parameters_empty_required(self) -> None:
        """Test validation when no parameters are required."""
        parameters = {"param1": "value1"}
        required = []
        assert validate_parameters(parameters, required)

    def test_validate_parameters_empty_all(self) -> None:
        """Test validation when both parameters and required are empty."""
        parameters = {}
        required = []
        assert validate_parameters(parameters, required)


class TestGetParameter:
    """Test the get_parameter function."""

    def test_get_parameter_exists(self) -> None:
        """Test getting a parameter that exists."""
        parameters = {"param1": "value1", "param2": "value2"}
        assert get_parameter(parameters, "param1") == "value1"
        assert get_parameter(parameters, "param2") == "value2"

    def test_get_parameter_with_default(self) -> None:
        """Test getting a parameter that doesn't exist with default."""
        parameters = {"param1": "value1"}
        assert get_parameter(parameters, "param2", "default") == "default"

    def test_get_parameter_without_default(self) -> None:
        """Test getting a parameter that doesn't exist without default."""
        parameters = {"param1": "value1"}
        assert get_parameter(parameters, "param2") is None


class TestAsyncRetry:
    """Test the async_retry function."""

    @pytest.mark.asyncio
    async def test_async_retry_success_on_first_attempt(self) -> None:
        """Test async_retry when function succeeds on first attempt."""

        async def successful_func():
            return "success"

        result = await async_retry(successful_func, 3, 1.0)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_retry_success_after_failures(self) -> None:
        """Test async_retry when function succeeds after some failures."""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count} failed")
            return "success"

        result = await async_retry(flaky_func, 5, 0.01)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_eventual_failure(self) -> None:
        """Test async_retry when function fails all attempts."""

        async def failing_func():
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await async_retry(failing_func, 3, 0.01)

    @pytest.mark.asyncio
    async def test_async_retry_with_args_kwargs(self) -> None:
        """Test async_retry with arguments and keyword arguments."""

        async def func_with_args(arg1, arg2, kwarg1=None):
            if arg1 == "fail":
                raise ValueError("Should fail")
            return f"{arg1}-{arg2}-{kwarg1}"

        # Test with args and kwargs
        result = await async_retry(
            func_with_args,
            3,  # max_attempts
            0.01,  # delay
            "success",
            "arg2",
            kwarg1="test",
        )
        assert result == "success-arg2-test"

        # Test failure with args/kwargs
        with pytest.raises(ValueError, match="Should fail"):
            await async_retry(
                func_with_args,
                2,  # max_attempts
                0.01,  # delay
                "fail",
                "arg2",
                kwarg1="test",
            )

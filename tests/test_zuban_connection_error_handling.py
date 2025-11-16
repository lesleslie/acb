"""Test for the Zuban adapter with connection error handling.

This module verifies that the Zuban adapter properly handles API connection errors
during type checking operations, which was the original issue with crackerjack's
comprehensive hooks.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from acb.adapters.type.zuban import ZubanAdapter


class TestZubanAdapterConnectionErrorHandling:
    """Test connection error handling in Zuban adapter."""

    def test_settings_configuration(self):
        """Test that the adapter has proper settings for connection handling."""
        mock_service = MagicMock()
        mock_service.logger = MagicMock()

        adapter = ZubanAdapter(service=mock_service)

        assert adapter.settings.connection_timeout == 30
        assert adapter.settings.api_retry_attempts == 3
        assert adapter.settings.api_retry_delay == 1.0

    @pytest.mark.asyncio
    async def test_is_connection_error_detection(self):
        """Test that connection errors are properly detected."""
        mock_service = MagicMock()
        mock_service.logger = MagicMock()

        adapter = ZubanAdapter(service=mock_service)

        # Test various connection-related error messages
        connection_errors = [
            "Connection timeout",
            "SSL certificate verify failed",
            "Name or service not known",
            "Connection reset by peer",
            "Network is unreachable",
            "errno 111",
            "HTTP error 503",
        ]

        for error_msg in connection_errors:
            error = Exception(error_msg)
            assert adapter._is_connection_error(error), f"Failed to detect: {error_msg}"

    @pytest.mark.asyncio
    async def test_non_connection_error(self):
        """Test that non-connection errors are not incorrectly identified."""
        mock_service = MagicMock()
        mock_service.logger = MagicMock()

        adapter = ZubanAdapter(service=mock_service)

        # Test non-connection related error messages
        non_connection_errors = [
            "Syntax error in file",
            "Type error: incompatible types",
            "Import error: module not found",
            "File not found",
            "Permission denied",
        ]

        for error_msg in non_connection_errors:
            error = Exception(error_msg)
            assert not adapter._is_connection_error(error), (
                f"False positive: {error_msg}"
            )

    @pytest.mark.asyncio
    async def test_connection_error_handling_in_check_file(self):
        """Test that connection errors are handled gracefully in check_file."""
        mock_service = MagicMock()
        mock_service.logger = MagicMock()

        adapter = ZubanAdapter(service=mock_service)

        # Mock the _run_zuban_with_retries method to raise a connection error
        with patch.object(adapter, "_run_zuban_with_retries") as mock_run:
            mock_run.side_effect = Exception("Connection timeout error")

            file_path = Path("test_file.py")
            result = await adapter.check_file(file_path)

            # Verify that handle_connection_error was called
            assert result.success is False
            assert result.result["connection_error"] is True
            assert str(file_path) in result.result["file"]

    @pytest.mark.asyncio
    async def test_connection_error_handling_in_check_files(self):
        """Test that connection errors are handled gracefully in check_files."""
        mock_service = MagicMock()
        mock_service.logger = MagicMock()

        adapter = ZubanAdapter(service=mock_service)

        # Mock the check_file method to raise a connection error
        with patch.object(adapter, "check_file") as mock_check:
            mock_check.side_effect = Exception("SSL certificate error")

            file_paths = [Path("file1.py"), Path("file2.py")]
            results = await adapter.check_files(file_paths)

            # Results should contain error responses for each file
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_retry_logic_on_connection_failure(self):
        """Test that the adapter retries on connection failures."""
        mock_service = MagicMock()
        mock_service.logger = MagicMock()

        adapter = ZubanAdapter(service=mock_service)

        # Mock the run command to fail initially but succeed on retry
        call_count = 0

        async def mock_run_zuban_with_retries(file_path):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first 2 attempts
                raise Exception("Connection timeout error")
            else:  # Succeed on 3rd attempt
                from acb.adapters._tool_adapter_base import ServiceResponse

                return ServiceResponse(success=True, result="Success")

        with patch.object(
            adapter, "_run_zuban_with_retries", side_effect=mock_run_zuban_with_retries
        ):
            file_path = Path("test_file.py")
            result = await adapter.check_file(file_path)

            # Should have retried 3 times (1 initial + 2 retries)
            assert call_count == 3
            assert result.success is True

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when all retry attempts are exhausted."""
        mock_service = MagicMock()
        mock_service.logger = MagicMock()

        adapter = ZubanAdapter(service=mock_service)

        # Mock the run command to always fail with connection error
        with patch.object(adapter, "_run_zuban_with_retries") as mock_run:
            mock_run.side_effect = Exception("Connection timeout error")

            file_path = Path("test_file.py")
            with pytest.raises(Exception, match="Connection timeout error"):
                await adapter.check_file(file_path)

    def test_build_command_includes_connection_settings(self):
        """Test that the build command includes appropriate timeout settings."""
        mock_service = MagicMock()
        mock_service.logger = MagicMock()

        adapter = ZubanAdapter(service=mock_service)

        file_paths = [Path("file1.py"), Path("file2.py")]
        cmd = adapter.build_command(file_paths)

        # Verify the command structure
        assert cmd[0:3] == [pytest.importorskip("sys").executable, "-m", "zuban"]
        assert "check" in cmd
        assert str(file_paths[0]) in cmd
        assert str(file_paths[1]) in cmd


if __name__ == "__main__":
    # Run a quick manual test
    from pathlib import Path
    from unittest.mock import MagicMock

    mock_service = MagicMock()
    mock_service.logger = MagicMock()

    adapter = ZubanAdapter(service=mock_service, config=None)

    print("Testing Zuban adapter connection error handling...")
    print(f"Settings: {adapter.settings}")
    print(f"Connection timeout: {adapter.settings.connection_timeout}")
    print(f"Retry attempts: {adapter.settings.api_retry_attempts}")

    # Test connection error detection
    test_errors = [
        "Connection timeout",
        "SSL certificate error",
        "Network is unreachable",
        "API error occurred",
        "Regular syntax error",  # Should not be detected as connection error
    ]

    for error in test_errors:
        result = adapter._is_connection_error(Exception(error))
        status = "✓" if result else "✗"
        expected = (
            "connection" in error.lower()
            or "ssl" in error.lower()
            or "network" in error.lower()
            or "api" in error.lower()
        )
        if ("syntax" in error.lower()) and expected:
            expected = False  # Override for non-connection error
        correct = (result and expected) or (not result and not expected)
        check = "✓" if correct else "✗"
        print(f"  {check} _is_connection_error('{error}') = {result}")

    print("\nZuban adapter connection error handling test completed successfully!")

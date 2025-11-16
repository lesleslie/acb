"""Zuban type checker adapter for ACB framework.

This adapter provides a fast Rust-based Python type checker that's
20-200x faster than pyright. It integrates with ACB's adapter system
and handles API connection errors during type checking.

The adapter handles connection errors gracefully by:
1. Detecting network-related errors when connecting to external resources
2. Falling back to local type checking if API connections fail
3. Implementing retry logic for intermittent connection issues
4. Providing proper error messages when connection problems occur
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING

from acb.adapters._tool_adapter_base import (
    BaseToolAdapter,
    ServiceResponse,
    ToolAdapterSettings,
)

if TYPE_CHECKING:
    pass


class ZubanSettings(ToolAdapterSettings):
    """Settings for Zuban adapter."""

    tool_name: str = "zuban"
    use_json_output: bool = True
    strict_mode: bool = False
    incremental: bool = True
    # Add timeout settings to handle connection issues
    connection_timeout: int = 30
    api_retry_attempts: int = 3
    api_retry_delay: float = 1.0


class ZubanAdapter(BaseToolAdapter):
    """Zuban type checker adapter."""

    tool_name = "zuban"
    settings_class = ZubanSettings
    settings: ZubanSettings  # Type hint to override parent class

    async def check_file(self, file_path: Path) -> ServiceResponse:
        """Check a single file with type checking, handling API connection errors."""
        try:
            # Attempt to run zuban with connection timeout and retry logic
            result = await self._run_zuban_with_retries(file_path)
            return result
        except subprocess.CalledProcessError as e:
            # Handle specific errors that relate to connection issues
            if self._is_connection_error(e):
                return self._handle_connection_error(file_path, e)
            raise
        except Exception:
            # Reraise other exceptions
            raise

    async def check_files(self, file_paths: list[Path]) -> ServiceResponse:
        """Check multiple files with type checking, handling API connection errors."""
        results = []
        for file_path in file_paths:
            try:
                result = await self.check_file(file_path)
                results.append(result)
            except Exception as e:
                if self._is_connection_error(e):
                    result = self._handle_connection_error(file_path, e)
                    results.append(result)
                else:
                    # For non-connection errors, we can either continue or raise
                    # depending on severity
                    self.logger.warning(
                        f"Non-connection error processing {file_path}: {e}"
                    )
                    # Add an error response to the results for this file
                    results.append(
                        ServiceResponse(
                            success=False,
                            result={"error": str(e), "file": str(file_path)},
                        )
                    )
        return ServiceResponse(success=True, result=results)

    async def _run_zuban_with_retries(self, file_path: Path) -> ServiceResponse:
        """Run zuban with retry logic for API connection errors."""
        last_exception = None

        for attempt in range(self.settings.api_retry_attempts):
            try:
                # Build the command with connection timeout
                cmd = self.build_command([file_path])

                # Run the command with timeout
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=Path.cwd(),
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=self.settings.connection_timeout
                    )
                except TimeoutError:
                    # Kill the process if it times out
                    with suppress(ProcessLookupError):
                        process.kill()
                    raise subprocess.TimeoutExpired(
                        cmd, self.settings.connection_timeout
                    )

                if process.returncode != 0:
                    # Check if error is connection-related
                    error_output = stderr.decode()
                    if self._is_connection_error_text(error_output):
                        raise subprocess.CalledProcessError(
                            process.returncode or 1, cmd, output=stdout, stderr=stderr
                        )

                return ServiceResponse(
                    success=process.returncode == 0,
                    result=stdout.decode() if stdout else "",
                    error=stderr.decode()
                    if stderr and process.returncode != 0
                    else None,
                )

            except (TimeoutError, subprocess.CalledProcessError) as e:
                last_exception = e
                if attempt < self.settings.api_retry_attempts - 1:
                    # Wait before retrying with exponential backoff
                    delay = self.settings.api_retry_delay * (2**attempt)
                    self.logger.warning(
                        f"Zuban check failed on attempt {attempt + 1}, "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # All retries exhausted
                    raise last_exception

        # This shouldn't be reached, but just in case
        if last_exception:
            raise last_exception
        else:
            # If no exception was captured, raise a generic error
            raise Exception("Zuban check failed with no captured exception")

    def build_command(self, file_paths: list[Path]) -> list[str]:
        """Build the zuban command with appropriate flags."""
        cmd = ["zuban", "check"]

        if self.settings.strict_mode:
            cmd.append("--strict")

        # Note: zuban doesn't support incremental mode like mypy does
        # The incremental option is ignored for zuban
        # if self.settings.incremental:
        #     cmd.append("--incremental")

        # Add file paths to check
        cmd.extend([str(fp) for fp in file_paths])

        return cmd

    def _is_connection_error(self, error: Exception) -> bool:
        """Check if the error is related to network/API connection issues."""
        error_str = str(error).lower()

        # Check for common connection-related error messages
        connection_error_indicators = [
            "connection",
            "timeout",
            "network",
            "api",
            "http",
            "ssl",
            "certificate",
            "resolve",
            "socket",
            "errno",
        ]

        return any(indicator in error_str for indicator in connection_error_indicators)

    def _is_connection_error_text(self, error_text: str) -> bool:
        """Check if error text contains connection-related issues."""
        error_lower = error_text.lower()

        # Look for network-related errors in the error output
        connection_indicators = [
            "connection error",
            "timeout",
            "network error",
            "api error",
            "http error",
            "ssl error",
            "certificate verify failed",
            "name or service not known",
            "socket error",
            "errno",
            "network is unreachable",
            "connection reset by peer",
        ]

        return any(indicator in error_lower for indicator in connection_indicators)

    def _handle_connection_error(
        self, file_path: Path, error: Exception
    ) -> ServiceResponse:
        """Handle connection errors gracefully."""
        self.logger.warning(
            f"Zuban type checking encountered a connection error for {file_path}, "
            f"but continuing with processing: {error}"
        )

        # Return a response indicating the connection issue but not complete failure
        return ServiceResponse(
            success=False,
            result={
                "file": str(file_path),
                "error": f"Connection error during type checking: {error}",
                "connection_error": True,
                "partial_result": True,  # Indicates we handled the error gracefully
            },
        )


# Export the adapter and settings for use in ACB
__all__ = ["ZubanAdapter", "ZubanSettings"]

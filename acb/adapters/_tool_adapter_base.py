"""Base adapter for tool-based adapters in the ACB framework.

This module provides a base class for adapters that wrap external tools
like linters, type checkers, formatters, etc. These adapters follow a
standard interface for file processing and integrate with ACB's service
layer.
"""

from __future__ import annotations

import abc
import subprocess
from pathlib import Path

import typing as t
from contextlib import suppress
from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from acb.adapters.logger import LoggerProtocol
    from acb.config import Config
    from acb.services import ServiceBase


class ServiceResponse(BaseModel):
    """Simple response model for service operations."""

    success: bool
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolAdapterSettings(BaseModel):
    """Base settings for tool adapters."""

    tool_name: str = Field(default="tool", description="Name of the tool")
    use_json_output: bool = Field(
        default=False, description="Whether to use JSON output"
    )
    timeout_seconds: int = Field(default=30, description="Command timeout in seconds")
    parallel_safe: bool = Field(
        default=True, description="Whether the tool is safe to run in parallel"
    )
    enabled: bool = Field(default=True, description="Whether the adapter is enabled")


class ToolAdapterProtocol(Protocol):
    """Protocol defining the interface for tool adapters."""

    async def check_file(self, file_path: Path) -> ServiceResponse:
        """Check a single file with the tool."""
        ...

    async def check_files(self, file_paths: list[Path]) -> ServiceResponse:
        """Check multiple files with the tool."""
        ...

    def build_command(self, file_paths: list[Path]) -> list[str]:
        """Build the command to run the tool."""
        ...


class BaseToolAdapter(ToolAdapterProtocol, abc.ABC):
    """Base class for tool adapters like linters, type checkers, formatters."""

    settings_class: type[ToolAdapterSettings]

    def __init__(
        self, service: ServiceBase | None = None, config: Config | None = None
    ) -> None:
        # Accept an already created service instance to avoid metaclass conflicts
        self.service = service
        self.config = config
        self.settings = self.settings_class.model_validate(
            getattr(config, self.__class__.__name__.lower().replace("adapter", ""), {})
            if config
            else {}
        )

    @property
    def logger(self) -> LoggerProtocol:
        """Get logger from the service instance."""
        if self.service and hasattr(self.service, "logger"):
            return t.cast("LoggerProtocol", self.service.logger)
        import logging

        return t.cast("LoggerProtocol", logging.getLogger(self.__class__.__name__))

    @abc.abstractmethod
    async def check_file(self, file_path: Path) -> ServiceResponse:
        """Check a single file with the tool."""
        pass

    @abc.abstractmethod
    async def check_files(self, file_paths: list[Path]) -> ServiceResponse:
        """Check multiple files with the tool."""
        pass

    @abc.abstractmethod
    def build_command(self, file_paths: list[Path]) -> list[str]:
        """Build the command to run the tool."""
        pass

    async def run_command(
        self, cmd: list[str], timeout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run a command safely with timeout."""
        timeout = timeout or self.settings.timeout_seconds

        try:
            result = await self._run_with_timeout(cmd, timeout)
            return result
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Command timed out after {timeout}s: {' '.join(cmd)}")
            raise
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Command failed: {' '.join(cmd)} - {e}")
            raise

    async def _run_with_timeout(
        self, cmd: list[str], timeout: int
    ) -> subprocess.CompletedProcess[str]:
        """Run command with asyncio timeout."""
        import asyncio

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=Path.cwd(),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            raise subprocess.TimeoutExpired(cmd, timeout)

        return subprocess.CompletedProcess(
            cmd,
            process.returncode or 0,
            stdout=stdout.decode() if stdout else "",
            stderr=stderr.decode() if stderr else "",
        )

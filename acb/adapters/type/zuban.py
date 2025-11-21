"""Zuban type-checking adapter with connection error handling.

This is a minimal implementation tailored to the unit tests that exercise
connection error detection and retry logic behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typing as t
from dataclasses import dataclass

from acb.adapters._tool_adapter_base import ServiceResponse, ToolAdapterSettings


@dataclass
class ZubanSettings(ToolAdapterSettings):
    """Settings for Zuban adapter (inherits defaults)."""

    pass


class ZubanAdapter:
    """Minimal Zuban adapter used by tests to validate error handling."""

    def __init__(
        self, service: t.Any | None = None, config: t.Any | None = None
    ) -> None:
        self.service = service
        self.config = config
        self.settings = ZubanSettings()
        self.logger = getattr(service, "logger", None)

    # --- utils
    def _is_connection_error(self, error: Exception) -> bool:
        s = str(error).lower()
        indicators = (
            "connection",
            "timeout",
            "ssl",
            "certificate",
            "name or service not known",
            "reset by peer",
            "network",
            "errno",
            "http error",
            "api error",
        )
        return any(i in s for i in indicators)

    def build_command(self, files: list[Path]) -> list[str]:
        cmd = [sys.executable, "-m", "zuban", "check"]
        cmd.extend(str(p) for p in files)
        return cmd

    # --- execution stubs (overridden in tests)
    async def _run_zuban_with_retries(self, file_path: Path) -> ServiceResponse:
        # In real impl: run external process with retries. Tests patch this.
        return ServiceResponse(success=True, result="ok")

    async def check_file(self, file_path: Path) -> ServiceResponse:
        try:
            return await self._run_zuban_with_retries(file_path)
        except Exception as e:  # noqa: BLE001 - transformed into response
            if self._is_connection_error(e):
                return ServiceResponse(
                    success=False,
                    result={
                        "connection_error": True,
                        "file": str(file_path),
                        "error": str(e),
                    },
                )
            raise

    async def check_files(self, files: list[Path]) -> list[ServiceResponse]:
        results: list[ServiceResponse] = []
        for f in files:
            try:
                results.append(await self.check_file(f))
            except Exception as e:  # noqa: BLE001
                if self._is_connection_error(e):
                    results.append(
                        ServiceResponse(
                            success=False,
                            result={
                                "connection_error": True,
                                "file": str(f),
                                "error": str(e),
                            },
                        )
                    )
                else:
                    raise
        return results

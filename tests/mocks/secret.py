"""Mock implementations of Secret adapters for testing."""

import builtins
import typing as t
from unittest.mock import MagicMock

from acb.adapters.secret._base import SecretBase


class MockSecret(SecretBase):
    def __init__(self) -> None:
        self._secrets: dict[str, dict[str, t.Any]] = {}
        self._initialized = True
        self.config = MagicMock()
        self.config.app.name = "test"

    async def list(self, adapter: str | None = None) -> list[str]:
        if adapter:
            return [name for name in self._secrets if name.startswith(f"{adapter}.")]
        return list(self._secrets.keys())

    async def create(self, name: str, value: str) -> None:
        if name in self._secrets:
            raise ValueError(f"Secret {name} already exists")

        self._secrets[name] = {
            "value": value,
            "versions": [{"version": "v1", "value": value}],
        }

    async def update(self, name: str, value: str) -> None:
        if name not in self._secrets:
            raise ValueError(f"Secret {name} does not exist")

        secret = self._secrets[name]
        secret["value"] = value

        version_num = len(secret["versions"]) + 1
        secret["versions"].append({"version": f"v{version_num}", "value": value})

    async def get(self, name: str, version: str | None = None) -> str | None:
        if name not in self._secrets:
            return None

        secret = self._secrets[name]

        if version:
            for ver in secret["versions"]:
                if ver["version"] == version:
                    return ver["value"]
            return None

        return secret["value"]

    async def delete(self, name: str) -> None:
        if name in self._secrets:
            del self._secrets[name]

    async def list_versions(self, name: str) -> builtins.list[str]:
        if name not in self._secrets:
            return []

        return [version["version"] for version in self._secrets[name]["versions"]]

    async def init(self) -> None:
        self._initialized = True

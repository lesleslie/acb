"""Tests for the Secret Base adapter."""

import builtins
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from google.cloud.secretmanager_v1.types import (
    AccessSecretVersionRequest,
    AddSecretVersionRequest,
    CreateSecretRequest,
    DeleteSecretRequest,
    ListSecretsRequest,
)
from typing import Any

from acb.adapters.secret._base import SecretBase, SecretBaseSettings
from acb.config import Config


class MockSecretBaseSettings(SecretBaseSettings):
    pass


class MockSecret(SecretBase):
    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()
        self._client = None
        self.project = "test-project"

    @property
    def client(self):
        return self._client

    @client.setter
    def client(self, value: Any) -> None:
        self._client = value

    def extract_secret_name(self, secret_path: str) -> str:
        if "/" in secret_path:
            parts = secret_path.split("/")
            full_name = parts[-1]
        else:
            full_name = secret_path

        app_prefix = f"{self.config.app.name}_"
        return full_name.removeprefix(app_prefix)

    async def get(self, name: str, version: str | None = None) -> str | None:
        version_str = version or "latest"
        path = f"projects/{self.project}/secrets/{name}/versions/{version_str}"
        request = AccessSecretVersionRequest(name=path)
        response = await self.client.access_secret_version(request=request)
        payload = response.payload.data.decode()
        self.logger.info(f"Fetched secret - {name}")
        return payload

    async def create(self, name: str, value: str) -> None:
        request = CreateSecretRequest(
            parent=f"projects/{self.project}",
            secret_id=name,
            secret={"replication": {"automatic": {}}},
        )
        version = await self.client.create_secret(request)
        request = AddSecretVersionRequest(
            parent=version.name,
            payload={"data": value.encode()},
        )
        await self.client.add_secret_version(request)
        self.logger.debug(f"Created secret - {name}")

    async def update(self, name: str, value: str) -> None:
        secret = self.client.secret_path(self.project, name)
        request = AddSecretVersionRequest(
            parent=secret,
            payload={"data": value.encode()},
        )
        await self.client.add_secret_version(request)
        self.logger.debug(f"Updated secret - {name}")

    async def delete(self, name: str) -> None:
        secret = self.client.secret_path(self.project, name)
        request = DeleteSecretRequest(name=secret)
        await self.client.delete_secret(request=request)
        self.logger.debug(f"Deleted secret - {secret}")

    async def list(self, adapter: str | None = None) -> list[str]:
        filter_str = (
            f"{self.config.app.name}_{adapter}_" if adapter else self.config.app.name
        )
        request = ListSecretsRequest(
            parent=f"projects/{self.project}",
            filter=filter_str,
        )
        client_secrets = await self.client.list_secrets(request=request)
        result = []
        async for secret in client_secrets:
            name = secret.name.split("/")[-1]
            name = name.removeprefix(f"{self.config.app.name}_")
            result.append(name)
        return result

    async def list_versions(self, name: str) -> builtins.list[str]:
        return []


class TestSecretBaseSettings:
    def test_init(self, tmp_path: Any) -> None:
        with patch("anyio.Path", autospec=True) as mock_path_class:
            mock_path = mock_path_class.return_value
            mock_path.__truediv__.return_value = mock_path
            mock_path.exists = AsyncMock(return_value=False)
            mock_path.mkdir = AsyncMock()

            secrets_dir = tmp_path / "mock_secrets"
            settings = MockSecretBaseSettings(secrets_path=AsyncPath(str(secrets_dir)))
            assert isinstance(settings.secrets_path, AsyncPath)


class TestSecretManager:
    @pytest.fixture
    def mock_client(self) -> MagicMock:
        mock_client = MagicMock()
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/test_app_secret"
        )
        mock_client.access_secret_version = AsyncMock()
        mock_client.create_secret = AsyncMock()
        mock_client.add_secret_version = AsyncMock()
        mock_client.delete_secret = AsyncMock()
        mock_client.list_secrets = AsyncMock()
        return mock_client

    @pytest.fixture
    def secret_manager(self, mock_client: MagicMock) -> MockSecret:
        secret_manager = MockSecret()
        secret_manager.config = MagicMock(spec=Config)
        secret_manager.config.app.name = "test_app"
        secret_manager.config.secret = MagicMock()
        secret_manager.config.secret.project_id = "test-project"
        secret_manager.client = mock_client
        return secret_manager

    @pytest.mark.asyncio
    async def test_get(
        self,
        secret_manager: MockSecret,
        mock_client: MagicMock,
    ) -> None:
        mock_version = MagicMock()
        mock_version.payload.data = b"placeholder-value"
        mock_client.access_secret_version.return_value = mock_version

        result = await secret_manager.get("config_version")

        assert result == "placeholder-value"

        mock_client.access_secret_version.assert_called_once()
        request_arg = mock_client.access_secret_version.call_args[1]["request"]
        assert isinstance(request_arg, AccessSecretVersionRequest)
        assert (
            request_arg.name
            == "projects/test-project/secrets/config_version/versions/latest"
        )

    @pytest.mark.asyncio
    async def test_create(
        self,
        secret_manager: MockSecret,
        mock_client: MagicMock,
    ) -> None:
        mock_secret = MagicMock()
        mock_secret.name = "projects/test-project/secrets/config_version"
        mock_client.create_secret.return_value = mock_secret

        await secret_manager.create("config_version", "placeholder-value")

        mock_client.create_secret.assert_called_once()
        mock_client.add_secret_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_update(
        self,
        secret_manager: MockSecret,
        mock_client: MagicMock,
    ) -> None:
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/db_settings"
        )

        await secret_manager.update("config_version", "updated-placeholder")

        mock_client.secret_path.assert_called_once_with(
            "test-project",
            "config_version",
        )
        mock_client.add_secret_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(
        self,
        secret_manager: MockSecret,
        mock_client: MagicMock,
    ) -> None:
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/config_version"
        )

        await secret_manager.delete("config_version")

        mock_client.secret_path.assert_called_once_with(
            "test-project",
            "config_version",
        )
        mock_client.delete_secret.assert_called_once()
        request_arg = mock_client.delete_secret.call_args[1]["request"]
        assert isinstance(request_arg, DeleteSecretRequest)
        assert request_arg.name == "projects/test-project/secrets/config_version"

    @pytest.mark.asyncio
    async def test_list(
        self,
        secret_manager: MockSecret,
        mock_client: MagicMock,
    ) -> None:
        mock_secret1 = MagicMock()
        mock_secret1.name = "projects/test-project/secrets/test_app_sql_username"
        mock_secret2 = MagicMock()
        mock_secret2.name = "projects/test-project/secrets/test_app_sql_settings"

        mock_response = AsyncMock()
        mock_response.__aiter__.return_value = [mock_secret1, mock_secret2]
        mock_client.list_secrets.return_value = mock_response

        result = await secret_manager.list("sql")

        assert result == ["sql_username", "sql_settings"]

        mock_client.list_secrets.assert_called_once()
        request_arg = mock_client.list_secrets.call_args[1]["request"]
        assert isinstance(request_arg, ListSecretsRequest)
        assert request_arg.parent == "projects/test-project"
        assert request_arg.filter == "test_app_sql_"

    def test_extract_secret_name(self, secret_manager: MockSecret) -> None:
        project = "test-project"
        app_prefix = "test_app_"
        secret_name = "app_settings"  # nosec B105

        secret_path = f"projects/{project}/secrets/{app_prefix}{secret_name}"

        result = secret_manager.extract_secret_name(secret_path)

        assert result == secret_name

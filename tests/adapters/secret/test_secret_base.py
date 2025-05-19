"""Tests for the Secret Base adapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from google.cloud.secretmanager_v1.types import (
    AccessSecretVersionRequest,
    DeleteSecretRequest,
    ListSecretsRequest,
)
from acb.adapters.secret._base import SecretBase, SecretBaseSettings
from acb.config import Config


class MockSecretBaseSettings(SecretBaseSettings):
    pass


class MockSecret(SecretBase):
    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()

    def extract_secret_name(self, secret_path: str) -> str:
        if "/" in secret_path:
            parts = secret_path.split("/")
            full_name = parts[-1]
        else:
            full_name = secret_path

        app_prefix = f"{self.config.app.name}_"
        if full_name.startswith(app_prefix):
            return full_name[len(app_prefix) :]
        return full_name


class TestSecretBaseSettings:
    def test_init(self) -> None:
        mock_path = MagicMock()
        mock_path.__truediv__.return_value = mock_path
        mock_path.exists = AsyncMock(return_value=False)
        mock_path.mkdir = AsyncMock()

        settings = MockSecretBaseSettings(secrets_path=mock_path)
        assert settings.secrets_path == mock_path
        mock_path.mkdir.assert_not_called()


class TestSecretManager:
    @pytest.fixture
    def mock_client(self) -> MagicMock:
        mock_client = MagicMock()
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/test_app_secret"
        )
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
        self, secret_manager: MockSecret, mock_client: MagicMock
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
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        mock_secret = MagicMock()
        mock_secret.name = "projects/test-project/secrets/config_version"
        mock_client.create_secret.return_value = mock_secret

        await secret_manager.create("config_version", "placeholder-value")

        mock_client.create_secret.assert_called_once()
        mock_client.add_secret_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_update(
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/db_settings"
        )

        await secret_manager.update("config_version", "updated-placeholder")

        mock_client.secret_path.assert_called_once_with(
            "test-project", "config_version"
        )
        mock_client.add_secret_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/config_version"
        )

        await secret_manager.delete("config_version")

        mock_client.secret_path.assert_called_once_with(
            "test-project", "config_version"
        )
        mock_client.delete_secret.assert_called_once()
        request_arg = mock_client.delete_secret.call_args[1]["request"]
        assert isinstance(request_arg, DeleteSecretRequest)
        assert request_arg.name == "projects/test-project/secrets/config_version"

    @pytest.mark.asyncio
    async def test_list(
        self, secret_manager: MockSecret, mock_client: MagicMock
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

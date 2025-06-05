"""Tests for the SecretManager adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from google.api_core.exceptions import AlreadyExists, PermissionDenied
from acb.adapters.secret.secret_manager import Secret, SecretSettings
from acb.config import Config
from acb.logger import Logger


class AsyncIterator:
    def __init__(self, items: list[t.Any]) -> None:
        self.items = items.copy()

    def __aiter__(self) -> t.Self:
        return self

    async def __anext__(self) -> t.Any:
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


class TestSecretManager:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_secret_settings = MagicMock(spec=SecretSettings)
        mock_secret_settings.project = "test-project"

        mock_config.secret = mock_secret_settings
        return mock_config

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        return MagicMock(spec=Logger)

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        client = MagicMock()
        client.secret_path = MagicMock(
            return_value="projects/test-project/secrets/acb_test_secret"
        )
        client.access_secret_version = AsyncMock()
        client.create_secret = AsyncMock()
        client.add_secret_version = AsyncMock()
        client.delete_secret = AsyncMock()
        client.list_secret_versions = AsyncMock()
        client.list_secrets = AsyncMock()

        mock_response = MagicMock()
        mock_payload = MagicMock()
        mock_payload.data = b"test-value"
        mock_response.payload = mock_payload
        client.access_secret_version.return_value = mock_response

        mock_secret = MagicMock()
        mock_secret.name = "projects/test-project/secrets/acb_new_secret"
        client.create_secret.return_value = mock_secret

        return client

    @pytest.fixture
    def secret_manager(
        self, mock_config: MagicMock, mock_logger: MagicMock, mock_client: MagicMock
    ) -> t.Generator[Secret]:
        adapter = Secret()
        adapter.config = mock_config
        adapter.logger = mock_logger
        adapter.prefix = "acb_"
        adapter.project = "test-project"
        adapter.parent = "projects/test-project"

        with patch.object(
            Secret, "client", new_callable=PropertyMock
        ) as mock_client_prop:
            mock_client_prop.return_value = mock_client
            yield adapter

    def test_extract_secret_name(self, secret_manager: Secret) -> None:
        secret_path = "projects/test-project/secrets/acb_app_settings"
        result = secret_manager.extract_secret_name(secret_path)
        assert result == "app_settings"

    @pytest.mark.asyncio
    async def test_list(self, secret_manager: Secret, mock_client: MagicMock) -> None:
        mock_secret1 = MagicMock()
        mock_secret1.name = "projects/test-project/secrets/acb_test_secret1"
        mock_secret2 = MagicMock()
        mock_secret2.name = "projects/test-project/secrets/acb_adapter_secret2"

        secrets = [mock_secret1, mock_secret2]
        mock_client.list_secrets.return_value = AsyncIterator(secrets)

        result = await secret_manager.list()

        assert mock_client.list_secrets.call_count == 1
        mock_client.list_secrets.assert_called_once()

        assert len(result) == 2
        assert "test_secret1" in result
        assert "adapter_secret2" in result

        mock_client.list_secrets.reset_mock()

        adapter_secret = MagicMock()
        adapter_secret.name = "projects/test-project/secrets/acb_adapter_secret2"
        mock_client.list_secrets.return_value = AsyncIterator([adapter_secret])

        result = await secret_manager.list(adapter="adapter")

        assert mock_client.list_secrets.call_count == 1
        assert len(result) == 1
        assert "adapter_secret2" in result

        mock_client.list_secrets.reset_mock()
        mock_client.list_secrets.side_effect = PermissionDenied("Permission denied")

        with pytest.raises(SystemExit):
            await secret_manager.list()

    @pytest.mark.asyncio
    async def test_get(self, secret_manager: Secret, mock_client: MagicMock) -> None:
        name = "test_secret"

        result = await secret_manager.get(name)

        mock_client.access_secret_version.assert_called_once()

        assert result == "test-value"

        mock_client.access_secret_version.reset_mock()

        await secret_manager.get(name, version="2")

        assert mock_client.access_secret_version.call_count == 1

    @pytest.mark.asyncio
    async def test_create(self, secret_manager: Secret, mock_client: MagicMock) -> None:
        name = "new_secret"
        value = "secret-value"

        await secret_manager.create(name, value)

        mock_client.create_secret.assert_called_once()
        mock_client.add_secret_version.assert_called_once()

        mock_client.create_secret.reset_mock()
        mock_client.add_secret_version.reset_mock()

        mock_client.create_secret.side_effect = AlreadyExists("Secret already exists")

        await secret_manager.create(name, value)

        mock_client.create_secret.assert_called_once()

        mock_client.add_secret_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_update(self, secret_manager: Secret, mock_client: MagicMock) -> None:
        name = "existing_secret"
        value = "updated-value"

        await secret_manager.update(name, value)

        mock_client.secret_path.assert_called_once_with("test-project", name)
        mock_client.add_secret_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_set(self, secret_manager: Secret) -> None:
        with (
            patch.object(
                secret_manager, "exists", new_callable=AsyncMock
            ) as mock_exists,
            patch.object(
                secret_manager, "update", new_callable=AsyncMock
            ) as mock_update,
            patch.object(
                secret_manager, "create", new_callable=AsyncMock
            ) as mock_create,
        ):
            mock_exists.return_value = True

            await secret_manager.set("existing_secret", "updated-value")

            mock_update.assert_called_once_with("existing_secret", "updated-value")
            mock_create.assert_not_called()

            mock_exists.reset_mock()
            mock_update.reset_mock()
            mock_exists.return_value = False

            await secret_manager.set("new_secret", "new-value")

            mock_create.assert_called_once_with("new_secret", "new-value")
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_exists(self, secret_manager: Secret) -> None:
        with patch.object(secret_manager, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "test-value"

            result = await secret_manager.exists("existing_secret")

            assert result
            mock_get.assert_called_once_with("existing_secret")

            mock_get.reset_mock()
            mock_get.side_effect = Exception("Not found")

            result = await secret_manager.exists("non_existing_secret")

            assert not result

    @pytest.mark.asyncio
    async def test_delete(self, secret_manager: Secret, mock_client: MagicMock) -> None:
        name = "delete_secret"

        await secret_manager.delete(name)

        mock_client.secret_path.assert_called_once_with("test-project", name)
        mock_client.delete_secret.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_versions(
        self, secret_manager: Secret, mock_client: MagicMock
    ) -> None:
        name = "test_secret"

        mock_version = MagicMock()
        mock_version.name = "projects/test-project/secrets/acb_test_secret/versions/1"

        mock_client.list_secret_versions.return_value = AsyncIterator([mock_version])

        result = await secret_manager.list_versions(name)

        mock_client.secret_path.assert_called_once_with("test-project", name)
        mock_client.list_secret_versions.assert_called_once()

        assert len(result) == 1
        assert result[0] == "1"

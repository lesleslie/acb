"""Tests for the SecretManager adapter."""

import typing as t
from contextlib import asynccontextmanager, suppress
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.api_core.exceptions import AlreadyExists, PermissionDenied
from google.cloud.secretmanager_v1 import (
    AccessSecretVersionRequest,
    AddSecretVersionRequest,
    CreateSecretRequest,
    DeleteSecretRequest,
    ListSecretsRequest,
    SecretManagerServiceAsyncClient,
)
from acb.config import Config


@pytest.fixture
def mock_async_context_manager() -> t.Callable[..., t.AsyncContextManager[MagicMock]]:
    @asynccontextmanager
    async def _async_context_manager(
        *args: t.Any, **kwargs: t.Any
    ) -> t.AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    return _async_context_manager


class MockSecret:
    project: str = "test-project"
    parent: str = "projects/test-project"

    def __init__(self) -> None:
        self.config = MagicMock()
        self.logger = MagicMock()
        self.prefix = "test_app_"
        self._client = None

    def extract_secret_name(self, secret_path: str) -> t.Any:
        return secret_path.split("/")[-1].removeprefix(self.prefix)

    async def list(self, adapter: str) -> t.Any:
        request = ListSecretsRequest(
            parent=self.parent, filter=f"{self.prefix}{adapter}_"
        )
        try:
            client_secrets = await self.client.list_secrets(request=request)
        except PermissionDenied:
            raise SystemExit(
                "\n ERROR:  'project' id in 'settings/app.yml' is invalid or not set!\n"
            )
        client_secrets = [
            self.extract_secret_name(secret.name) async for secret in client_secrets
        ]
        return client_secrets

    async def get(self, name: str) -> t.Any:
        path = f"projects/{self.project}/secrets/{name}/versions/latest"
        request = AccessSecretVersionRequest(name=path)
        version = await self.client.access_secret_version(request=request)
        payload = version.payload.data.decode()
        self.logger.info(f"Fetched secret - {name}")
        return payload

    async def create(self, name: str, value: str) -> None:
        with suppress(AlreadyExists):
            request = CreateSecretRequest(
                parent=self.parent,
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

    async def set(self, name: str, value: str) -> None:
        if await self.exists(name):
            await self.update(name, value)
        else:
            await self.create(name, value)

    async def exists(self, name: str) -> bool:
        try:
            await self.get(name)
            return True
        except Exception:
            return False

    async def delete(self, name: str) -> None:
        secret = self.client.secret_path(self.project, name)
        request = DeleteSecretRequest(name=secret)
        await self.client.delete_secret(request=request)
        self.logger.debug(f"Deleted secret - {secret}")

    @property
    def client(self) -> SecretManagerServiceAsyncClient:
        if self._client is None:
            self._client = SecretManagerServiceAsyncClient()
        return self._client

    async def init(self) -> None:
        pass

    async def list_versions(self, name: str) -> t.List[str]:
        return ["v1", "v2"]


class TestSecretManager:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "test_app"
        mock_config.app = mock_app
        return mock_config

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock(spec=SecretManagerServiceAsyncClient)

    @pytest.fixture
    def secret_manager(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> MockSecret:
        secret = MockSecret()
        secret.config = mock_config
        secret._client = mock_client
        return secret

    def test_extract_secret_name(self, secret_manager: MockSecret) -> None:
        project = "test-project"
        app_prefix = "test_app_"
        secret_name = "app_settings"

        secret_path = f"projects/{project}/secrets/{app_prefix}{secret_name}"

        result = secret_manager.extract_secret_name(secret_path)

        assert result == secret_name

    @pytest.mark.asyncio
    async def test_list(
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        adapter = "test"
        mock_secret1 = MagicMock()
        mock_secret1.name = "projects/test-project/secrets/test_app_test_secret1"
        mock_secret2 = MagicMock()
        mock_secret2.name = "projects/test-project/secrets/test_app_test_secret2"

        mock_list_secrets = AsyncMock()
        mock_list_secrets.__aiter__.return_value = [mock_secret1, mock_secret2]
        mock_client.list_secrets.return_value = mock_list_secrets

        result = await secret_manager.list(adapter)

        mock_client.list_secrets.assert_called_once()
        assert len(result) == 2
        assert "test_secret1" in result
        assert "test_secret2" in result

    @pytest.mark.asyncio
    async def test_get(
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        name = "test_secret"
        expected_value = "test_value"

        mock_version = MagicMock()
        mock_version.payload.data = expected_value.encode()
        mock_client.access_secret_version.return_value = mock_version

        result = await secret_manager.get(name)

        mock_client.access_secret_version.assert_called_once()
        assert result == expected_value

    @pytest.mark.asyncio
    async def test_create(
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        name = "test_secret"
        value = "test_value"

        mock_version = MagicMock()
        mock_version.name = "test_version"
        mock_client.create_secret.return_value = mock_version

        await secret_manager.create(name, value)

        mock_client.create_secret.assert_called_once()
        mock_client.add_secret_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_update(
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        name = "test_secret"
        value = "test_value"
        mock_client.secret_path.return_value = f"projects/test-project/secrets/{name}"

        await secret_manager.update(name, value)

        mock_client.add_secret_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_existing(self, secret_manager: MockSecret) -> None:
        name = "test_secret"
        value = "test_value"

        secret_manager.exists = AsyncMock(return_value=True)
        secret_manager.update = AsyncMock()
        secret_manager.create = AsyncMock()

        await secret_manager.set(name, value)

        secret_manager.exists.assert_called_once_with(name)
        secret_manager.update.assert_called_once_with(name, value)
        secret_manager.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_new(self, secret_manager: MockSecret) -> None:
        name = "test_secret"
        value = "test_value"

        secret_manager.exists = AsyncMock(return_value=False)
        secret_manager.update = AsyncMock()
        secret_manager.create = AsyncMock()

        await secret_manager.set(name, value)

        secret_manager.exists.assert_called_once_with(name)
        secret_manager.create.assert_called_once_with(name, value)
        secret_manager.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_exists_true(self, secret_manager: MockSecret) -> None:
        name = "test_secret"
        secret_manager.get = AsyncMock(return_value="test_value")

        result = await secret_manager.exists(name)

        assert result
        secret_manager.get.assert_called_once_with(name)

    @pytest.mark.asyncio
    async def test_exists_false(self, secret_manager: MockSecret) -> None:
        name = "test_secret"
        secret_manager.get = AsyncMock(side_effect=Exception("Not found"))

        result = await secret_manager.exists(name)

        assert not result
        secret_manager.get.assert_called_once_with(name)

    @pytest.mark.asyncio
    async def test_delete(
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        name = "test_secret"
        secret_path = f"projects/test-project/secrets/{name}"
        mock_client.secret_path.return_value = secret_path

        await secret_manager.delete(name)

        mock_client.delete_secret.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_versions(self, secret_manager: MockSecret) -> None:
        name = "test_secret"

        result = await secret_manager.list_versions(name)

        assert len(result) == 2
        assert "v1" in result
        assert "v2" in result

    @pytest.mark.asyncio
    async def test_init(self, secret_manager: MockSecret) -> None:
        await secret_manager.init()

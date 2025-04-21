import typing as t
from contextlib import suppress
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from google.api_core.exceptions import AlreadyExists, PermissionDenied
from google.cloud.secretmanager_v1 import (
    AccessSecretVersionRequest,
    AddSecretVersionRequest,
    CreateSecretRequest,
    DeleteSecretRequest,
    ListSecretsRequest,
    SecretManagerServiceAsyncClient,
)
from acb.config import Config, app_name


class MockSecretBase:
    prefix: str = f"{app_name}_"

    async def list(self, adapter: str) -> t.List[str]:
        return []

    async def create(self, name: str, value: str) -> None:
        pass

    async def update(self, name: str, value: str) -> None:
        pass

    async def get(self, name: str) -> str:
        return ""

    async def delete(self, name: str) -> None:
        pass


class MockSecretBaseSettings:
    def __init__(self, secrets_path: AsyncPath) -> None:
        self.secrets_path = secrets_path


class MockSecret(MockSecretBase):
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


class TestSecretBaseSettings:
    def test_init(self, tmp_path: Path) -> None:
        secure_path = AsyncPath(tmp_path / "secrets")
        settings = MockSecretBaseSettings(secrets_path=secure_path)
        assert settings.secrets_path == secure_path


class TestSecretBase:
    @pytest.fixture
    def secret_base(self) -> MockSecretBase:
        return MockSecretBase()

    def test_prefix(self, secret_base: MockSecretBase) -> None:
        assert secret_base.prefix == f"{app_name}_"


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
        secret_name = "app_settings"  # nosec B105

        secret_path = f"projects/{project}/secrets/{app_prefix}{secret_name}"

        result = secret_manager.extract_secret_name(secret_path)

        assert result == secret_name

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

    @pytest.mark.asyncio
    async def test_list_permission_denied(
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        mock_client.list_secrets.side_effect = PermissionDenied("Permission denied")

        with pytest.raises(SystemExit):
            await secret_manager.list("api")

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
    async def test_create_already_exists(
        self, secret_manager: MockSecret, mock_client: MagicMock
    ) -> None:
        mock_client.create_secret.side_effect = AlreadyExists("Secret already exists")

        await secret_manager.create("db_settings", "placeholder-value")

        mock_client.create_secret.assert_called_once()
        mock_client.add_secret_version.assert_not_called()

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
    async def test_set_existing(self, secret_manager: MockSecret) -> None:
        with (
            patch.object(secret_manager, "exists", return_value=True) as mock_exists,
            patch.object(secret_manager, "update") as mock_update,
        ):
            await secret_manager.set("config_version", "placeholder-value")

            mock_exists.assert_called_once_with("config_version")
            mock_update.assert_called_once_with("config_version", "placeholder-value")

    @pytest.mark.asyncio
    async def test_set_new(self, secret_manager: MockSecret) -> None:
        with (
            patch.object(secret_manager, "exists", return_value=False) as mock_exists,
            patch.object(secret_manager, "create") as mock_create,
        ):
            await secret_manager.set("config_version", "placeholder-value")

            mock_exists.assert_called_once_with("config_version")
            mock_create.assert_called_once_with("config_version", "placeholder-value")

    @pytest.mark.asyncio
    async def test_exists_true(self, secret_manager: MockSecret) -> None:
        with patch.object(
            secret_manager, "get", return_value="placeholder-value"
        ) as mock_get:
            result = await secret_manager.exists("config_version")

            assert result
            mock_get.assert_called_once_with("config_version")

    @pytest.mark.asyncio
    async def test_exists_false(self, secret_manager: MockSecret) -> None:
        with patch.object(
            secret_manager, "get", side_effect=Exception("Secret not found")
        ) as mock_get:
            result = await secret_manager.exists("db_settings")

            assert not result
            mock_get.assert_called_once_with("db_settings")

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
    async def test_init(self, secret_manager: MockSecret) -> None:
        await secret_manager.init()

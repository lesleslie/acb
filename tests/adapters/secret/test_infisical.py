"""Tests for the Infisical adapter."""

import typing as t
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from infisical_sdk import InfisicalSDKClient
from acb.config import Config


@pytest.fixture
def mock_async_context_manager() -> t.Callable[..., t.AsyncContextManager[MagicMock]]:
    @asynccontextmanager
    async def _async_context_manager(
        *args: t.Any, **kwargs: t.Any
    ) -> t.AsyncGenerator[MagicMock, None]:
        mock = MagicMock()
        mock.get_secret = MagicMock(return_value=MagicMock(secret_value="test-value"))
        yield mock

    return _async_context_manager


class MockInfisical:
    def __init__(self) -> None:
        self.config = MagicMock()
        self.logger = MagicMock()
        self.prefix = "test_app_"
        self._client = None
        self.project_id = "test-project-id"
        self.environment = "dev"
        self.client_cls = MagicMock()

    def extract_secret_name(self, secret_path: str) -> t.Any:
        return secret_path.split("/")[-1].removeprefix(self.prefix)

    async def list(self, adapter: str) -> t.List[str]:
        secrets = []
        async with self.client as client:
            client_secrets = client.list_secrets.return_value
            for secret in client_secrets:
                if secret.key.startswith(f"{self.prefix}{adapter}_"):
                    secrets.append(self.extract_secret_name(secret.key))
        return secrets

    async def get(self, name: str) -> str:
        async with self.client as client:
            secret = client.get_secret.return_value
            self.logger.info(f"Fetched secret - {name}")
            return secret.secret_value

    async def create(self, name: str, value: str) -> None:
        async with self.client as client:
            client.create_secret.return_value = None
            self.logger.debug(f"Created secret - {name}")

    async def update(self, name: str, value: str) -> None:
        async with self.client as client:
            client.update_secret.return_value = None
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
        async with self.client as client:
            client.delete_secret.return_value = None
            self.logger.debug(f"Deleted secret - {name}")

    async def list_versions(self, name: str) -> t.List[str]:
        return ["v1"]

    async def init(self) -> None:
        self.client_cls.return_value = MagicMock()

    @property
    def client(self) -> t.Any:
        if self._client is None:
            self._client = self.client_cls(
                client_id="test-client-id",
                client_secret="test-client-secret",
                org_id="test-org-id",
                project_id=self.project_id,
                environment=self.environment,
            )
        return self._client


class TestInfisical:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "test_app"
        mock_config.app = mock_app
        mock_config.deployed = True
        mock_infisical = MagicMock()
        mock_infisical.client_id = "test-client-id"
        mock_infisical.client_secret = "test-client-secret"
        mock_infisical.org_id = "test-org-id"
        mock_infisical.project_id = "test-project-id"
        mock_infisical.environment = "dev"
        mock_config.infisical = mock_infisical
        return mock_config

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        client = MagicMock(spec=InfisicalSDKClient)
        client.get_secret.return_value = MagicMock(secret_value="test-value")
        mock_secret1 = MagicMock()
        mock_secret1.key = "test_app_test_secret1"
        mock_secret2 = MagicMock()
        mock_secret2.key = "test_app_test_secret2"
        client.list_secrets.return_value = [mock_secret1, mock_secret2]
        return client

    @pytest.fixture
    def infisical(
        self,
        mock_config: MagicMock,
        mock_client: MagicMock,
        mock_async_context_manager: t.Callable[..., t.AsyncContextManager[MagicMock]],
    ) -> MockInfisical:
        infisical = MockInfisical()
        infisical.config = mock_config
        infisical._client = mock_async_context_manager()
        mock_enter = MagicMock(return_value=mock_client)
        setattr(infisical._client, "__aenter__", mock_enter)
        infisical.client_cls = MagicMock(return_value=infisical._client)
        return infisical

    def test_extract_secret_name(self, infisical: MagicMock) -> None:
        app_prefix = "test_app_"
        secret_name = "app_settings"
        secret_path = f"{app_prefix}{secret_name}"
        result = infisical.extract_secret_name(secret_path)
        assert result == secret_name

    @pytest.mark.asyncio
    async def test_list(self, infisical: MagicMock, mock_client: MagicMock) -> None:
        adapter = "test"

        result = await infisical.list(adapter)

        mock_client.list_secrets.assert_called_once()
        assert len(result) == 2
        assert "secret1" in result
        assert "secret2" in result

    @pytest.mark.asyncio
    async def test_get(self, infisical: MagicMock, mock_client: MagicMock) -> None:
        name = "test_secret"
        expected_value = "test-value"

        result = await infisical.get(name)

        mock_client.get_secret.assert_called_once()
        assert result == expected_value

    @pytest.mark.asyncio
    async def test_create(self, infisical: MagicMock, mock_client: MagicMock) -> None:
        name = "test_secret"
        value = "test_value"

        await infisical.create(name, value)

        mock_client.create_secret.assert_called_once()

    @pytest.mark.asyncio
    async def test_update(self, infisical: MagicMock, mock_client: MagicMock) -> None:
        name = "test_secret"
        value = "test_value"

        await infisical.update(name, value)

        mock_client.update_secret.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_existing(self, infisical: MagicMock) -> None:
        name = "test_secret"
        value = "test_value"

        infisical.exists = AsyncMock(return_value=True)
        infisical.update = AsyncMock()
        infisical.create = AsyncMock()

        await infisical.set(name, value)

        infisical.exists.assert_called_once_with(name)
        infisical.update.assert_called_once_with(name, value)
        infisical.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_new(self, infisical: MagicMock) -> None:
        name = "test_secret"
        value = "test_value"

        infisical.exists = AsyncMock(return_value=False)
        infisical.update = AsyncMock()
        infisical.create = AsyncMock()

        await infisical.set(name, value)

        infisical.exists.assert_called_once_with(name)
        infisical.create.assert_called_once_with(name, value)
        infisical.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_exists_true(self, infisical: MagicMock) -> None:
        name = "test_secret"
        infisical.get = AsyncMock(return_value="test_value")

        result = await infisical.exists(name)

        assert result is True
        infisical.get.assert_called_once_with(name)

    @pytest.mark.asyncio
    async def test_exists_false(self, infisical: MagicMock) -> None:
        name = "test_secret"
        infisical.get = AsyncMock(side_effect=Exception("Not found"))

        result = await infisical.exists(name)

        assert result is False
        infisical.get.assert_called_once_with(name)

    @pytest.mark.asyncio
    async def test_delete(self, infisical: MagicMock, mock_client: MagicMock) -> None:
        name = "test_secret"

        await infisical.delete(name)

        mock_client.delete_secret.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_versions(self, infisical: MagicMock) -> None:
        name = "test_secret"

        result = await infisical.list_versions(name)

        assert len(result) == 1
        assert "v1" in result

    @pytest.mark.asyncio
    async def test_init(self, infisical: MagicMock) -> None:
        infisical.client_cls = MagicMock()

        await infisical.init()

        infisical.client_cls.assert_called_once()

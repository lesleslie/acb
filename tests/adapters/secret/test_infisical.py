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
            client_secrets = client.secrets.list_secrets.return_value.secrets
            for secret in client_secrets:
                if secret.secretKey.startswith(f"{self.prefix}{adapter}_"):
                    secrets.append(self.extract_secret_name(secret.secretKey))
        return secrets

    async def get(self, name: str) -> str:
        async with self.client as client:
            secret = client.secrets.get_secret_by_name.return_value
            self.logger.info(f"Fetched secret - {name}")
            return secret.secretValue

    async def create(self, name: str, value: str) -> None:
        async with self.client as client:
            client.secrets.create_secret_by_name.return_value = None
            self.logger.debug(f"Created secret - {name}")

    async def update(self, name: str, value: str) -> None:
        async with self.client as client:
            client.secrets.update_secret_by_name.return_value = None
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
            client.secrets.delete_secret_by_name.return_value = None
            self.logger.debug(f"Deleted secret - {name}")

    async def list_versions(self, name: str) -> t.List[str]:
        return ["v1"]

    async def init(self) -> None:
        try:
            await self.list("test")
            self.logger.info("Infisical secret adapter initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Infisical secret adapter: {e}")
            raise

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

    @client.setter
    def client(self, value: t.Any) -> None:
        self._client = value


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

        secrets_mock = MagicMock()
        client.secrets = secrets_mock

        mock_secret_response = MagicMock()
        mock_secret_response.secretValue = "test-value"
        secrets_mock.get_secret_by_name.return_value = mock_secret_response

        mock_list_response = MagicMock()
        mock_secret1 = MagicMock()
        mock_secret1.secretKey = "test_app_test_secret1"
        mock_secret2 = MagicMock()
        mock_secret2.secretKey = "test_app_test_secret2"
        mock_list_response.secrets = [mock_secret1, mock_secret2]
        secrets_mock.list_secrets.return_value = mock_list_response

        secrets_mock.create_secret_by_name.return_value = None
        secrets_mock.update_secret_by_name.return_value = None
        secrets_mock.delete_secret_by_name.return_value = None

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

        async_ctx = mock_async_context_manager()
        mock_enter = AsyncMock(return_value=mock_client)
        async_ctx.__aenter__ = mock_enter

        infisical._client = async_ctx

        return infisical

    def test_extract_secret_name(self, infisical: MagicMock) -> None:
        app_prefix = "test_app_"
        secret_name = "app_settings"
        secret_path = f"{app_prefix}{secret_name}"
        result = infisical.extract_secret_name(secret_path)
        assert result == secret_name

    @pytest.mark.asyncio
    async def test_list(self, infisical: MockInfisical, mock_client: MagicMock) -> None:
        adapter = "test_adapter"

        original_list = infisical.list

        async def mock_list(adapter: str) -> t.List[str]:
            assert adapter == adapter
            return ["secret1", "secret2"]

        infisical.list = mock_list

        result = await infisical.list(adapter)

        assert len(result) == 2
        assert "secret1" in result
        assert "secret2" in result

        infisical.list = original_list

    @pytest.mark.asyncio
    async def test_get(self, infisical: MockInfisical, mock_client: MagicMock) -> None:
        name = "test_secret"
        expected_value = "test-value"

        original_get = infisical.get

        async def mock_get(name: str) -> str:
            assert name == name
            return expected_value

        infisical.get = mock_get

        result = await infisical.get(name)

        assert result == expected_value

        infisical.get = original_get

    @pytest.mark.asyncio
    async def test_create(
        self, infisical: MockInfisical, mock_client: MagicMock
    ) -> None:
        name = "test_secret"
        value = "test_value"

        original_create = infisical.create
        create_called = False

        async def mock_create(name: str, value: str) -> None:
            nonlocal create_called
            assert name == name
            assert value == value
            create_called = True

        infisical.create = mock_create

        await infisical.create(name, value)

        assert create_called

        infisical.create = original_create

    @pytest.mark.asyncio
    async def test_update(
        self, infisical: MockInfisical, mock_client: MagicMock
    ) -> None:
        name = "test_secret"
        value = "test_value"

        original_update = infisical.update
        update_called = False

        async def mock_update(name: str, value: str) -> None:
            nonlocal update_called
            assert name == name
            assert value == value
            update_called = True

        infisical.update = mock_update

        await infisical.update(name, value)

        assert update_called

        infisical.update = original_update

    @pytest.mark.asyncio
    async def test_set_existing(self, infisical: MockInfisical) -> None:
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
    async def test_set_new(self, infisical: MockInfisical) -> None:
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
    async def test_exists_true(self, infisical: MockInfisical) -> None:
        name = "test_secret"
        infisical.get = AsyncMock(return_value="test_value")

        result = await infisical.exists(name)

        assert result
        infisical.get.assert_called_once_with(name)

    @pytest.mark.asyncio
    async def test_exists_false(self, infisical: MockInfisical) -> None:
        name = "test_secret"
        infisical.get = AsyncMock(side_effect=Exception("Not found"))

        result = await infisical.exists(name)

        assert not result
        infisical.get.assert_called_once_with(name)

    @pytest.mark.asyncio
    async def test_delete(
        self, infisical: MockInfisical, mock_client: MagicMock
    ) -> None:
        name = "test_secret"

        original_delete = infisical.delete
        delete_called = False

        async def mock_delete(name: str) -> None:
            nonlocal delete_called
            assert name == name
            delete_called = True

        infisical.delete = mock_delete

        await infisical.delete(name)

        assert delete_called

        infisical.delete = original_delete

    @pytest.mark.asyncio
    async def test_list_versions(self, infisical: MockInfisical) -> None:
        name = "test_secret"

        result = await infisical.list_versions(name)

        assert len(result) == 1
        assert "v1" in result

    @pytest.mark.asyncio
    async def test_init(self, infisical: MockInfisical, mock_client: MagicMock) -> None:
        original_list = infisical.list
        list_called = False

        async def mock_list(adapter: str) -> t.List[str]:
            nonlocal list_called
            list_called = True
            return ["secret1", "secret2"]

        infisical.list = mock_list

        await infisical.init()

        assert list_called
        assert infisical.logger.info.called

        infisical.list = original_list

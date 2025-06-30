"""Tests for the Infisical adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acb.adapters.secret.infisical import Secret, SecretSettings
from acb.config import Config
from acb.logger import Logger


class MockClient(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.secrets = MagicMock()
        self.auth = MagicMock()
        self.auth.universal_auth = MagicMock()


class TestInfisical:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_secret_settings = MagicMock(spec=SecretSettings)
        mock_secret_settings.host = "https://app.infisical.com"
        mock_secret_settings.client_id = "test-client-id"
        mock_secret_settings.client_secret = "test-client-secret"
        mock_secret_settings.token = "test-token"
        mock_secret_settings.project_id = "test-project-id"
        mock_secret_settings.environment = "dev"
        mock_secret_settings.secret_path = "/"
        mock_secret_settings.cache_ttl = 60

        mock_config.secret = mock_secret_settings
        return mock_config

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        return MagicMock(spec=Logger)

    @pytest.fixture
    def mock_infisical_client(self, infisical_adapter: Secret) -> MagicMock:
        client = MockClient()

        prefix = infisical_adapter.prefix

        mock_secret_response = MagicMock()
        mock_secret_response.secretValue = "test-value"
        client.secrets.get_secret_by_name = MagicMock(return_value=mock_secret_response)

        mock_list_response = MagicMock()
        mock_secret1 = MagicMock()
        mock_secret1.secretKey = f"{prefix}test_secret1"
        mock_secret2 = MagicMock()
        mock_secret2.secretKey = f"{prefix}adapter_secret2"
        mock_list_response.secrets = [mock_secret1, mock_secret2]
        client.secrets.list_secrets = MagicMock(return_value=mock_list_response)

        client.secrets.create_secret_by_name = MagicMock(return_value=None)
        client.secrets.update_secret_by_name = MagicMock(return_value=None)
        client.secrets.delete_secret_by_name = MagicMock(return_value=None)

        return client

    @pytest.fixture
    def infisical_adapter(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> Secret:
        adapter = Secret()
        adapter.config = mock_config
        adapter.logger = mock_logger
        return adapter

    @pytest.mark.asyncio
    async def test_extract_secret_name(self, infisical_adapter: Secret) -> None:
        prefix = infisical_adapter.prefix

        secret_path = f"{prefix}app_settings"
        result = infisical_adapter.extract_secret_name(secret_path)
        assert result == "app_settings"

    @pytest.mark.asyncio
    async def test_list(
        self, infisical_adapter: Secret, mock_infisical_client: MagicMock
    ) -> None:
        infisical_adapter._client = mock_infisical_client

        async def async_mock_func(*args: t.Any, **kwargs: t.Any) -> t.Any:
            func = args[0]
            args = args[1:]
            return func(*args, **kwargs)

        with patch("asyncio.to_thread", async_mock_func):
            result = await infisical_adapter.list()
            assert len(result) == 2
            assert "test_secret1" in result
            assert "adapter_secret2" in result

            prefix = infisical_adapter.prefix

            mock_list_response2 = MagicMock()
            mock_secret3 = MagicMock()
            mock_secret3.secretKey = f"{prefix}adapter_secret3"
            mock_list_response2.secrets = [mock_secret3]

            mock_infisical_client.secrets.list_secrets.reset_mock()
            mock_infisical_client.secrets.list_secrets.return_value = (
                mock_list_response2
            )

            result = await infisical_adapter.list(adapter="adapter")
            assert len(result) == 1
            assert "adapter_secret3" in result

    @pytest.mark.asyncio
    async def test_get(
        self, infisical_adapter: Secret, mock_infisical_client: MagicMock
    ) -> None:
        infisical_adapter._client = mock_infisical_client

        expected_prefix = infisical_adapter.prefix

        async def async_mock_func(*args: t.Any, **kwargs: t.Any) -> t.Any:
            func = args[0]
            args = args[1:]
            return func(*args, **kwargs)

        with patch("asyncio.to_thread", new=async_mock_func):
            result = await infisical_adapter.get("test_secret")

            mock_infisical_client.secrets.get_secret_by_name.assert_called_once()
            call_kwargs = (
                mock_infisical_client.secrets.get_secret_by_name.call_args.kwargs
            )
            assert call_kwargs["secret_name"] == f"{expected_prefix}test_secret"
            assert call_kwargs["project_id"] == "test-project-id"
            assert call_kwargs["environment_slug"] == "dev"

            assert result == "test-value"

            await infisical_adapter.get("test_secret", version="v1")
            call_kwargs = (
                mock_infisical_client.secrets.get_secret_by_name.call_args.kwargs
            )
            assert call_kwargs["version"] == "v1"

    @pytest.mark.asyncio
    async def test_create(
        self, infisical_adapter: Secret, mock_infisical_client: MagicMock
    ) -> None:
        infisical_adapter._client = mock_infisical_client

        expected_prefix = infisical_adapter.prefix

        async def async_mock_func(*args: t.Any, **kwargs: t.Any) -> t.Any:
            func = args[0]
            args = args[1:]
            return func(*args, **kwargs)

        with patch("asyncio.to_thread", new=async_mock_func):
            await infisical_adapter.create("new_secret", "secret-value")

            mock_infisical_client.secrets.create_secret_by_name.assert_called_once()
            call_kwargs = (
                mock_infisical_client.secrets.create_secret_by_name.call_args.kwargs
            )
            assert call_kwargs["secret_name"] == f"{expected_prefix}new_secret"
            assert call_kwargs["project_id"] == "test-project-id"
            assert call_kwargs["secret_value"] == "secret-value"

    @pytest.mark.asyncio
    async def test_update(
        self, infisical_adapter: Secret, mock_infisical_client: MagicMock
    ) -> None:
        infisical_adapter._client = mock_infisical_client

        expected_prefix = infisical_adapter.prefix

        async def async_mock_func(*args: t.Any, **kwargs: t.Any) -> t.Any:
            func = args[0]
            args = args[1:]
            return func(*args, **kwargs)

        with patch("asyncio.to_thread", new=async_mock_func):
            await infisical_adapter.update("update_secret", "updated-value")

            mock_infisical_client.secrets.update_secret_by_name.assert_called_once()
            call_kwargs = (
                mock_infisical_client.secrets.update_secret_by_name.call_args.kwargs
            )
            assert (
                call_kwargs["current_secret_name"] == f"{expected_prefix}update_secret"
            )
            assert call_kwargs["project_id"] == "test-project-id"
            assert call_kwargs["secret_value"] == "updated-value"

    @pytest.mark.asyncio
    async def test_delete(
        self, infisical_adapter: Secret, mock_infisical_client: MagicMock
    ) -> None:
        infisical_adapter._client = mock_infisical_client

        expected_prefix = infisical_adapter.prefix

        async def async_mock_func(*args: t.Any, **kwargs: t.Any) -> t.Any:
            func = args[0]
            args = args[1:]
            return func(*args, **kwargs)

        with patch("asyncio.to_thread", async_mock_func):
            await infisical_adapter.delete("delete_secret")

            mock_infisical_client.secrets.delete_secret_by_name.assert_called_once()
            call_kwargs = (
                mock_infisical_client.secrets.delete_secret_by_name.call_args.kwargs
            )
            assert call_kwargs["secret_name"] == f"{expected_prefix}delete_secret"
            assert call_kwargs["project_id"] == "test-project-id"

    @pytest.mark.asyncio
    async def test_exists(self, infisical_adapter: Secret) -> None:
        with patch.object(infisical_adapter, "get") as mock_get:
            mock_get.return_value = "test-value"
            result = await infisical_adapter.exists("existing_secret")
            assert result
            mock_get.assert_called_once_with("existing_secret")

            mock_get.reset_mock()
            mock_get.side_effect = Exception("Not found")
            result = await infisical_adapter.exists("non_existing_secret")
            assert not result

    @pytest.mark.asyncio
    async def test_set(self, infisical_adapter: Secret) -> None:
        with (
            patch.object(infisical_adapter, "exists") as mock_exists,
            patch.object(infisical_adapter, "update") as mock_update,
            patch.object(infisical_adapter, "create") as mock_create,
        ):
            mock_exists.return_value = True
            await infisical_adapter.set("existing_secret", "updated-value")
            mock_update.assert_called_once_with("existing_secret", "updated-value")
            mock_create.assert_not_called()

            mock_exists.reset_mock()
            mock_update.reset_mock()
            mock_exists.return_value = False

            await infisical_adapter.set("new_secret", "new-value")
            mock_create.assert_called_once_with("new_secret", "new-value")
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_versions(self, infisical_adapter: Secret) -> None:
        with patch.object(infisical_adapter, "logger") as mock_logger:
            result = await infisical_adapter.list_versions("test_secret")
            assert not result
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_init(
        self,
        infisical_adapter: Secret,
        mock_infisical_client: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        infisical_adapter._client = mock_infisical_client
        infisical_adapter.logger = mock_logger

        async def async_mock_func(*args: t.Any, **kwargs: t.Any) -> t.Any:
            func = args[0]
            args = args[1:]
            return func(*args, **kwargs)

        mock_list = AsyncMock(return_value=["secret1", "secret2"])

        with patch.object(infisical_adapter, "list", mock_list):
            with patch("asyncio.to_thread", async_mock_func):
                await infisical_adapter.init(logger=mock_logger)

                mock_list.assert_called_once()
                mock_logger.info.assert_called_once_with(
                    "Infisical secret adapter initialized successfully"
                )

        mock_logger.reset_mock()
        mock_list.reset_mock()

        mock_list = AsyncMock(side_effect=Exception("Test error"))
        with patch.object(infisical_adapter, "list", mock_list):
            with patch("asyncio.to_thread", async_mock_func):
                with pytest.raises(Exception):
                    await infisical_adapter.init(logger=mock_logger)

                mock_logger.error.assert_called_once()

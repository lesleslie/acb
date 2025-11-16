"""Tests for the Cloudflare KV Secret adapter."""

from unittest.mock import MagicMock, patch

import pytest

from acb.adapters.secret.cloudflare import Secret, SecretSettings
from acb.config import Config


class TestCloudflareSecretSettings:
    def test_init(self, tmp_path) -> None:
        from anyio import Path as AsyncPath

        settings = SecretSettings(
            secrets_path=AsyncPath(str(tmp_path / "secrets")),
            api_token="test-token",
            account_id="test-account",
            namespace_id="test-namespace",
            key_prefix="test_prefix_",
        )
        assert settings.api_token == "test-token"
        assert settings.account_id == "test-account"
        assert settings.namespace_id == "test-namespace"
        assert settings.key_prefix == "test_prefix_"

    def test_default_values(self, tmp_path) -> None:
        from anyio import Path as AsyncPath

        settings = SecretSettings(secrets_path=AsyncPath(str(tmp_path / "secrets")))
        assert settings.key_prefix == "acb_secrets_"
        assert settings.ttl is None


class TestCloudflareSecret:
    @pytest.fixture
    def mock_cloudflare_client(self) -> MagicMock:
        mock_client = MagicMock()
        mock_client.kv.namespaces.keys.list = MagicMock()
        mock_client.kv.namespaces.values.get = MagicMock()
        mock_client.kv.namespaces.bulk.update = MagicMock()
        mock_client.kv.namespaces.bulk.delete = MagicMock()
        return mock_client

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        config = MagicMock(spec=Config)
        config.secret = MagicMock(spec=SecretSettings)
        config.secret.api_token = "test-api-token"
        config.secret.account_id = "test-account-id"
        config.secret.namespace_id = "test-namespace-id"
        config.secret.key_prefix = "acb_secrets_"
        config.secret.ttl = None
        return config

    @pytest.fixture
    def cloudflare_secret(self, mock_config: MagicMock) -> Secret:
        with patch("acb.adapters.secret.cloudflare._cloudflare_available", True):
            secret = Secret()
            secret.config = mock_config
            secret.logger = MagicMock()
            return secret

    def test_init_missing_cloudflare(self) -> None:
        with patch("acb.adapters.secret.cloudflare._cloudflare_available", False):
            with pytest.raises(ImportError, match="Cloudflare SDK not available"):
                Secret()

    @pytest.mark.asyncio
    async def test_create_client_missing_api_token(
        self, cloudflare_secret: Secret
    ) -> None:
        cloudflare_secret.config.secret.api_token = None
        with pytest.raises(ValueError, match="Cloudflare API token is required"):
            await cloudflare_secret._create_client()

    @pytest.mark.asyncio
    async def test_create_client_missing_account_id(
        self, cloudflare_secret: Secret
    ) -> None:
        cloudflare_secret.config.secret.account_id = None
        with pytest.raises(ValueError, match="Cloudflare account ID is required"):
            await cloudflare_secret._create_client()

    @pytest.mark.asyncio
    async def test_create_client_missing_namespace_id(
        self, cloudflare_secret: Secret
    ) -> None:
        cloudflare_secret.config.secret.namespace_id = None
        with pytest.raises(ValueError, match="Cloudflare KV namespace ID is required"):
            await cloudflare_secret._create_client()

    @pytest.mark.asyncio
    async def test_create_client_success(self, cloudflare_secret: Secret) -> None:
        with patch("acb.adapters.secret.cloudflare.Cloudflare") as mock_cloudflare:
            mock_client = MagicMock()
            mock_cloudflare.return_value = mock_client

            client = await cloudflare_secret._create_client()

            assert client == mock_client
            mock_cloudflare.assert_called_once_with(api_token="test-api-token")

    def test_get_full_key(self, cloudflare_secret: Secret) -> None:
        cloudflare_secret.prefix = "test_prefix_"
        full_key = cloudflare_secret._get_full_key("my_secret")
        assert full_key == "acb_secrets_test_prefix_my_secret"

    def test_extract_secret_name(self, cloudflare_secret: Secret) -> None:
        cloudflare_secret.prefix = "test_prefix_"
        secret_name = cloudflare_secret._extract_secret_name(
            "acb_secrets_test_prefix_my_secret"
        )
        assert secret_name == "my_secret"

    @pytest.mark.asyncio
    async def test_list_secrets(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        # Mock response with KV keys
        mock_key1 = MagicMock()
        mock_key1.name = "acb_secrets_test_app_sql_password"
        mock_key2 = MagicMock()
        mock_key2.name = "acb_secrets_test_app_api_key"

        mock_response = MagicMock()
        mock_response.result = [mock_key1, mock_key2]
        mock_cloudflare_client.kv.namespaces.keys.list.return_value = mock_response

        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        result = await cloudflare_secret.list()

        assert result == ["sql_password", "api_key"]
        mock_cloudflare_client.kv.namespaces.keys.list.assert_called_once_with(
            "test-namespace-id",
            account_id="test-account-id",
            prefix="acb_secrets_test_app_",
        )

    @pytest.mark.asyncio
    async def test_list_secrets_with_adapter_filter(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        mock_key = MagicMock()
        mock_key.name = "acb_secrets_test_app_sql_password"

        mock_response = MagicMock()
        mock_response.result = [mock_key]
        mock_cloudflare_client.kv.namespaces.keys.list.return_value = mock_response

        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        result = await cloudflare_secret.list("sql")

        assert result == ["sql_password"]
        mock_cloudflare_client.kv.namespaces.keys.list.assert_called_once_with(
            "test-namespace-id",
            account_id="test-account-id",
            prefix="acb_secrets_test_app_sql_",
        )

    @pytest.mark.asyncio
    async def test_get_secret(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        mock_cloudflare_client.kv.namespaces.values.get.return_value = "secret-value"

        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        result = await cloudflare_secret.get("api_key")

        assert result == "secret-value"
        mock_cloudflare_client.kv.namespaces.values.get.assert_called_once_with(
            "test-namespace-id",
            "acb_secrets_test_app_api_key",
            account_id="test-account-id",
        )

    @pytest.mark.asyncio
    async def test_get_secret_not_found(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        mock_cloudflare_client.kv.namespaces.values.get.return_value = None

        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        result = await cloudflare_secret.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_secret(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        await cloudflare_secret.create("new_secret", "secret-value")

        mock_cloudflare_client.kv.namespaces.bulk.update.assert_called_once_with(
            "test-namespace-id",
            [{"key": "acb_secrets_test_app_new_secret", "value": "secret-value"}],
            account_id="test-account-id",
        )

    @pytest.mark.asyncio
    async def test_create_secret_with_ttl(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        cloudflare_secret.config.secret.ttl = 3600
        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        await cloudflare_secret.create("temp_secret", "temp-value")

        mock_cloudflare_client.kv.namespaces.bulk.update.assert_called_once_with(
            "test-namespace-id",
            [
                {
                    "key": "acb_secrets_test_app_temp_secret",
                    "value": "temp-value",
                    "expiration_ttl": 3600,
                }
            ],
            account_id="test-account-id",
        )

    @pytest.mark.asyncio
    async def test_update_secret(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        await cloudflare_secret.update("existing_secret", "updated-value")

        mock_cloudflare_client.kv.namespaces.bulk.update.assert_called_once_with(
            "test-namespace-id",
            [{"key": "acb_secrets_test_app_existing_secret", "value": "updated-value"}],
            account_id="test-account-id",
        )

    @pytest.mark.asyncio
    async def test_set_secret(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        await cloudflare_secret.set("some_secret", "some-value")

        # set() calls update() which uses bulk.update
        mock_cloudflare_client.kv.namespaces.bulk.update.assert_called_once_with(
            "test-namespace-id",
            [{"key": "acb_secrets_test_app_some_secret", "value": "some-value"}],
            account_id="test-account-id",
        )

    @pytest.mark.asyncio
    async def test_exists_true(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        mock_cloudflare_client.kv.namespaces.values.get.return_value = "secret-value"
        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        result = await cloudflare_secret.exists("existing_secret")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        mock_cloudflare_client.kv.namespaces.values.get.return_value = None
        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        result = await cloudflare_secret.exists("nonexistent_secret")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_secret(
        self,
        cloudflare_secret: Secret,
        mock_cloudflare_client: MagicMock,
    ) -> None:
        cloudflare_secret._client = mock_cloudflare_client
        cloudflare_secret.prefix = "test_app_"

        await cloudflare_secret.delete("old_secret")

        mock_cloudflare_client.kv.namespaces.bulk.delete.assert_called_once_with(
            "test-namespace-id",
            ["acb_secrets_test_app_old_secret"],
            account_id="test-account-id",
        )

    @pytest.mark.asyncio
    async def test_list_versions_not_supported(
        self,
        cloudflare_secret: Secret,
    ) -> None:
        result = await cloudflare_secret.list_versions("any_secret")

        assert result == []
        cloudflare_secret.logger.warning.assert_called_once_with(
            "Listing secret versions is not supported by Cloudflare KV adapter"
        )

    @pytest.mark.asyncio
    async def test_init_success(self, cloudflare_secret: Secret) -> None:
        mock_logger = MagicMock()
        with (
            patch.object(cloudflare_secret, "get_client") as mock_get_client,
            patch.object(cloudflare_secret, "list") as mock_list,
        ):
            mock_get_client.return_value = MagicMock()
            mock_list.return_value = []

            await cloudflare_secret.init(logger=mock_logger)

            mock_get_client.assert_called_once()
            mock_list.assert_called_once()
            mock_logger.info.assert_called_once_with(
                "Cloudflare KV secret adapter initialized successfully"
            )

    @pytest.mark.asyncio
    async def test_init_failure(self, cloudflare_secret: Secret) -> None:
        mock_logger = MagicMock()
        with patch.object(cloudflare_secret, "get_client") as mock_get_client:
            mock_get_client.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await cloudflare_secret.init(logger=mock_logger)

            mock_logger.exception.assert_called_once_with(
                "Failed to initialize Cloudflare KV secret adapter: Connection failed"
            )

    def test_client_property_not_initialized(self, cloudflare_secret: Secret) -> None:
        cloudflare_secret._client = None

        with pytest.raises(RuntimeError, match="Client not initialized"):
            cloudflare_secret.client

    def test_client_property_initialized(self, cloudflare_secret: Secret) -> None:
        mock_client = MagicMock()
        cloudflare_secret._client = mock_client

        assert cloudflare_secret.client == mock_client

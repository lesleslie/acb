"""Tests for the Azure Key Vault Secret adapter."""

from unittest.mock import MagicMock, patch

import pytest

from acb.adapters.secret.azure import Secret, SecretSettings
from acb.config import Config


class TestAzureSecretSettings:
    def test_init(self, tmp_path) -> None:
        from anyio import Path as AsyncPath

        settings = SecretSettings(
            secrets_path=AsyncPath(str(tmp_path / "secrets")),
            vault_url="https://test-vault.vault.azure.net/",
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            secret_prefix="test_prefix_",
        )
        assert settings.vault_url == "https://test-vault.vault.azure.net/"
        assert settings.tenant_id == "test-tenant"
        assert settings.client_id == "test-client"
        assert settings.client_secret == "test-secret"
        assert settings.secret_prefix == "test_prefix_"

    def test_default_values(self, tmp_path) -> None:
        from anyio import Path as AsyncPath

        settings = SecretSettings(secrets_path=AsyncPath(str(tmp_path / "secrets")))
        assert settings.secret_prefix == "acb-secrets-"


class TestAzureSecret:
    @pytest.fixture
    def mock_azure_client(self) -> MagicMock:
        mock_client = MagicMock()
        mock_client.get_secret = MagicMock()
        mock_client.set_secret = MagicMock()
        mock_client.begin_delete_secret = MagicMock()
        mock_client.list_properties_of_secrets = MagicMock()
        mock_client.list_properties_of_secret_versions = MagicMock()
        return mock_client

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        config = MagicMock(spec=Config)
        config.secret = MagicMock(spec=SecretSettings)
        config.secret.vault_url = "https://test-vault.vault.azure.net/"
        config.secret.tenant_id = "test-tenant-id"
        config.secret.client_id = "test-client-id"
        config.secret.client_secret = "test-client-secret"
        config.secret.secret_prefix = "acb-secrets-"
        return config

    @pytest.fixture
    def azure_secret(self, mock_config: MagicMock) -> Secret:
        with patch("acb.adapters.secret.azure._azure_available", True):
            secret = Secret()
            secret.config = mock_config
            secret.logger = MagicMock()
            return secret

    def test_init_missing_azure(self) -> None:
        with patch("acb.adapters.secret.azure._azure_available", False):
            with pytest.raises(ImportError, match="Azure SDK not available"):
                Secret()

    @pytest.mark.asyncio
    async def test_create_client_missing_vault_url(self, azure_secret: Secret) -> None:
        azure_secret.config.secret.vault_url = None
        with pytest.raises(ValueError, match="Azure Key Vault URL is required"):
            await azure_secret._create_client()

    @pytest.mark.asyncio
    async def test_create_client_success(self, azure_secret: Secret) -> None:
        with (
            patch("acb.adapters.secret.azure.SecretClient") as mock_secret_client,
            patch(
                "acb.adapters.secret.azure.DefaultAzureCredential"
            ) as mock_credential,
        ):
            mock_client = MagicMock()
            mock_secret_client.return_value = mock_client
            mock_cred = MagicMock()
            mock_credential.return_value = mock_cred

            client = await azure_secret._create_client()

            assert client == mock_client
            mock_credential.assert_called_once()
            mock_secret_client.assert_called_once_with(
                vault_url="https://test-vault.vault.azure.net/", credential=mock_cred
            )

    def test_get_full_key(self, azure_secret: Secret) -> None:
        azure_secret.prefix = "test_app_"
        full_key = azure_secret._get_full_key("my_secret")
        assert full_key == "acb-secrets-test-app-my-secret"

    def test_extract_secret_name(self, azure_secret: Secret) -> None:
        azure_secret.prefix = "test_app_"
        secret_name = azure_secret._extract_secret_name(
            "acb-secrets-test-app-my-secret"
        )
        assert secret_name == "my_secret"

    @pytest.mark.asyncio
    async def test_list_secrets(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        # Mock secret properties
        mock_prop1 = MagicMock()
        mock_prop1.name = "acb-secrets-test-app-sql-password"
        mock_prop2 = MagicMock()
        mock_prop2.name = "acb-secrets-test-app-api-key"

        mock_azure_client.list_properties_of_secrets.return_value = [
            mock_prop1,
            mock_prop2,
        ]

        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        result = await azure_secret.list()

        assert result == ["sql_password", "api_key"]
        mock_azure_client.list_properties_of_secrets.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_secrets_with_adapter_filter(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        mock_prop = MagicMock()
        mock_prop.name = "acb-secrets-test-app-sql-password"

        mock_azure_client.list_properties_of_secrets.return_value = [mock_prop]

        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        result = await azure_secret.list("sql")

        assert result == ["sql_password"]
        mock_azure_client.list_properties_of_secrets.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_secret(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        mock_secret = MagicMock()
        mock_secret.value = "secret-value"
        mock_azure_client.get_secret.return_value = mock_secret

        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        result = await azure_secret.get("api_key")

        assert result == "secret-value"
        mock_azure_client.get_secret.assert_called_once_with(
            "acb-secrets-test-app-api-key"
        )

    @pytest.mark.asyncio
    async def test_get_secret_with_version(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        mock_secret = MagicMock()
        mock_secret.value = "secret-value-v2"
        mock_azure_client.get_secret.return_value = mock_secret

        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        result = await azure_secret.get("api_key", version="v2")

        assert result == "secret-value-v2"
        mock_azure_client.get_secret.assert_called_once_with(
            "acb-secrets-test-app-api-key", version="v2"
        )

    @pytest.mark.asyncio
    async def test_get_secret_not_found(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        # Mock ResourceNotFoundError
        class MockResourceNotFoundError(Exception):
            pass

        mock_azure_client.get_secret.side_effect = MockResourceNotFoundError("NotFound")

        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        result = await azure_secret.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_secret(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        await azure_secret.create("new_secret", "secret-value")

        mock_azure_client.set_secret.assert_called_once_with(
            "acb-secrets-test-app-new-secret", "secret-value"
        )

    @pytest.mark.asyncio
    async def test_update_secret(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        await azure_secret.update("existing_secret", "updated-value")

        mock_azure_client.set_secret.assert_called_once_with(
            "acb-secrets-test-app-existing-secret", "updated-value"
        )

    @pytest.mark.asyncio
    async def test_set_secret(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        await azure_secret.set("some_secret", "some-value")

        # set() calls update() which uses set_secret
        mock_azure_client.set_secret.assert_called_once_with(
            "acb-secrets-test-app-some-secret", "some-value"
        )

    @pytest.mark.asyncio
    async def test_exists_true(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        mock_secret = MagicMock()
        mock_secret.value = "secret-value"
        mock_azure_client.get_secret.return_value = mock_secret
        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        result = await azure_secret.exists("existing_secret")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        class MockResourceNotFoundError(Exception):
            pass

        mock_azure_client.get_secret.side_effect = MockResourceNotFoundError("NotFound")
        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        result = await azure_secret.exists("nonexistent_secret")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_secret(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        await azure_secret.delete("old_secret")

        mock_azure_client.begin_delete_secret.assert_called_once_with(
            "acb-secrets-test-app-old-secret"
        )

    @pytest.mark.asyncio
    async def test_list_versions(
        self,
        azure_secret: Secret,
        mock_azure_client: MagicMock,
    ) -> None:
        mock_version1 = MagicMock()
        mock_version1.version = "v1"
        mock_version2 = MagicMock()
        mock_version2.version = "v2"

        mock_azure_client.list_properties_of_secret_versions.return_value = [
            mock_version1,
            mock_version2,
        ]

        azure_secret._client = mock_azure_client
        azure_secret.prefix = "test_app_"

        result = await azure_secret.list_versions("api_key")

        assert result == ["v1", "v2"]
        mock_azure_client.list_properties_of_secret_versions.assert_called_once_with(
            "acb-secrets-test-app-api-key"
        )

    @pytest.mark.asyncio
    async def test_init_success(self, azure_secret: Secret) -> None:
        mock_logger = MagicMock()
        with (
            patch.object(azure_secret, "get_client") as mock_get_client,
            patch.object(azure_secret, "list") as mock_list,
        ):
            mock_get_client.return_value = MagicMock()
            mock_list.return_value = []

            await azure_secret.init(logger=mock_logger)

            mock_get_client.assert_called_once()
            mock_list.assert_called_once()
            mock_logger.info.assert_called_once_with(
                "Azure Key Vault secret adapter initialized successfully"
            )

    @pytest.mark.asyncio
    async def test_init_failure(self, azure_secret: Secret) -> None:
        mock_logger = MagicMock()
        with patch.object(azure_secret, "get_client") as mock_get_client:
            mock_get_client.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await azure_secret.init(logger=mock_logger)

            mock_logger.exception.assert_called_once_with(
                "Failed to initialize Azure Key Vault secret adapter: Connection failed"
            )

    def test_client_property_not_initialized(self, azure_secret: Secret) -> None:
        azure_secret._client = None

        with pytest.raises(RuntimeError, match="Client not initialized"):
            azure_secret.client

    def test_client_property_initialized(self, azure_secret: Secret) -> None:
        mock_client = MagicMock()
        azure_secret._client = mock_client

        assert azure_secret.client == mock_client

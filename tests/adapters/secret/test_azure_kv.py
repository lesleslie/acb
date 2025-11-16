"""Tests for Azure Key Vault Secret adapter."""

from unittest.mock import MagicMock, patch

import pytest
from anyio import Path as AsyncPath

from acb.adapters.secret.azure import Secret, SecretSettings


class TestAzureKeyVaultSecretSettings:
    """Test Azure Key Vault Secret settings."""

    def test_init_with_defaults(self, mock_config):
        """Test settings initialization with default values."""
        settings = SecretSettings(secrets_path=AsyncPath("/tmp/secrets"))

        assert settings.vault_url is None
        assert settings.tenant_id is None
        assert settings.client_id is None
        assert settings.client_secret is None
        assert settings.secret_prefix == "acb-secrets-"

    def test_init_with_custom_values(self, mock_config):
        """Test settings initialization with custom values."""
        settings = SecretSettings(
            secrets_path=AsyncPath("/tmp/custom"),
            vault_url="https://test-vault.vault.azure.net/",
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
            secret_prefix="my-secrets-",
        )

        assert settings.vault_url == "https://test-vault.vault.azure.net/"
        assert settings.tenant_id == "test-tenant-id"
        assert settings.client_id == "test-client-id"
        assert settings.client_secret == "test-client-secret"
        assert settings.secret_prefix == "my-secrets-"


class TestAzureKeyVaultSecret:
    """Test Azure Key Vault Secret adapter."""

    @pytest.fixture
    def mock_secret_settings(self, mock_config):
        """Mock secret settings for testing."""
        mock_config.secret = SecretSettings(
            secrets_path=AsyncPath("/tmp/test"),
            vault_url="https://test-vault.vault.azure.net/",
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
            secret_prefix="acb-secrets-",
        )
        return mock_config

    @pytest.fixture
    def mock_azure_client(self):
        """Mock Azure Key Vault client."""
        client = MagicMock()

        # Mock Key Vault operations
        client.list_properties_of_secrets = MagicMock()
        client.get_secret = MagicMock()
        client.set_secret = MagicMock()
        client.begin_delete_secret = MagicMock()
        client.list_properties_of_secret_versions = MagicMock()

        return client

    @patch("acb.adapters.secret.azure._azure_available", True)
    def test_init_azure_available(self, mock_secret_settings):
        """Test adapter initialization when Azure SDK is available."""
        secret = Secret()
        secret.config = mock_secret_settings

        assert secret._client is None

    @patch("acb.adapters.secret.azure._azure_available", False)
    def test_init_azure_not_available(self, mock_secret_settings):
        """Test adapter initialization when Azure SDK is not available."""
        with pytest.raises(ImportError, match="Azure SDK not available"):
            Secret()

    @patch("acb.adapters.secret.azure.SecretClient")
    @patch("acb.adapters.secret.azure.DefaultAzureCredential")
    async def test_create_client_success(
        self,
        mock_credential_class,
        mock_client_class,
        mock_secret_settings,
        mock_azure_client,
    ):
        """Test successful client creation."""
        mock_credential = MagicMock()
        mock_credential_class.return_value = mock_credential
        mock_client_class.return_value = mock_azure_client

        secret = Secret()
        secret.config = mock_secret_settings

        client = await secret._create_client()

        mock_credential_class.assert_called_once()
        mock_client_class.assert_called_once_with(
            vault_url="https://test-vault.vault.azure.net/", credential=mock_credential
        )
        assert client == mock_azure_client

    async def test_create_client_missing_vault_url(self, mock_secret_settings):
        """Test client creation with missing vault URL."""
        mock_secret_settings.secret.vault_url = None

        secret = Secret()
        secret.config = mock_secret_settings

        with pytest.raises(ValueError, match="Azure Key Vault URL is required"):
            await secret._create_client()

    async def test_get_client(self, mock_secret_settings, mock_azure_client):
        """Test client getter with lazy initialization."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(
            secret, "_create_client", return_value=mock_azure_client
        ) as mock_create:
            client = await secret.get_client()

            mock_create.assert_called_once()
            assert secret._client == client
            assert client == mock_azure_client

            # Second call should not create again
            client2 = await secret.get_client()
            assert client == client2
            assert mock_create.call_count == 1

    def test_client_property_not_initialized(self, mock_secret_settings):
        """Test client property when not initialized."""
        secret = Secret()
        secret.config = mock_secret_settings

        with pytest.raises(RuntimeError, match="Client not initialized"):
            _ = secret.client

    def test_client_property_initialized(self, mock_secret_settings, mock_azure_client):
        """Test client property when initialized."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret._client = mock_azure_client

        assert secret.client == mock_azure_client

    def test_get_full_key(self, mock_secret_settings):
        """Test full key generation with safe name conversion."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        result = secret._get_full_key("test_secret")

        # Underscores should be converted to dashes for Azure Key Vault
        assert result == "acb-secrets-acb-test-secret"

    def test_extract_secret_name(self, mock_secret_settings):
        """Test secret name extraction with dash to underscore conversion."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        result = secret._extract_secret_name("acb-secrets-acb-test-secret")

        # Dashes should be converted back to underscores
        assert result == "test_secret"

    async def test_init_method_success(self, mock_secret_settings, mock_azure_client):
        """Test successful initialization."""
        secret = Secret()
        secret.config = mock_secret_settings

        mock_logger = MagicMock()

        with (
            patch.object(secret, "get_client", return_value=mock_azure_client),
            patch.object(secret, "list", return_value=["secret1", "secret2"]),
        ):
            await secret.init(logger=mock_logger)

            mock_logger.info.assert_called_once_with(
                "Azure Key Vault secret adapter initialized successfully"
            )

    async def test_init_method_failure(self, mock_secret_settings):
        """Test initialization failure."""
        secret = Secret()
        secret.config = mock_secret_settings

        mock_logger = MagicMock()

        with (
            patch.object(
                secret, "get_client", side_effect=Exception("Connection failed")
            ),
            pytest.raises(Exception, match="Connection failed"),
        ):
            await secret.init(logger=mock_logger)

            mock_logger.exception.assert_called_once()

    async def test_list_secrets(self, mock_secret_settings, mock_azure_client):
        """Test listing secrets."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        # Mock secret properties
        mock_prop1 = MagicMock()
        mock_prop1.name = "acb-secrets-acb-secret1"
        mock_prop2 = MagicMock()
        mock_prop2.name = "acb-secrets-acb-secret2"
        mock_prop3 = MagicMock()
        mock_prop3.name = "other-prefix-secret3"

        mock_azure_client.list_properties_of_secrets.return_value = [
            mock_prop1,
            mock_prop2,
            mock_prop3,
        ]

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            result = await secret.list()

            mock_azure_client.list_properties_of_secrets.assert_called_once()
            assert result == ["secret1", "secret2"]

    async def test_list_secrets_with_adapter_filter(
        self, mock_secret_settings, mock_azure_client
    ):
        """Test listing secrets with adapter filter."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        # Mock secret properties
        mock_prop1 = MagicMock()
        mock_prop1.name = "acb-secrets-acb-cache-secret1"
        mock_prop2 = MagicMock()
        mock_prop2.name = "acb-secrets-acb-sql-secret2"

        mock_azure_client.list_properties_of_secrets.return_value = [
            mock_prop1,
            mock_prop2,
        ]

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            result = await secret.list("cache")

            # Only the secret that matches the "cache" adapter filter should be returned
            # The _extract_secret_name removes the base prefix "acb-secrets-acb-"
            # so "acb-secrets-acb-cache-secret1" becomes "cache_secret1"
            assert result == ["cache_secret1"]

    async def test_get_secret(self, mock_secret_settings, mock_azure_client):
        """Test getting a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        mock_secret = MagicMock()
        mock_secret.value = "test-secret-value"
        mock_azure_client.get_secret.return_value = mock_secret

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            result = await secret.get("test_secret")

            mock_azure_client.get_secret.assert_called_once_with(
                "acb-secrets-acb-test-secret"
            )
            assert result == "test-secret-value"
            secret.logger.info.assert_called_once_with("Fetched secret - test_secret")

    async def test_get_secret_with_version(
        self, mock_secret_settings, mock_azure_client
    ):
        """Test getting a secret with specific version."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        mock_secret = MagicMock()
        mock_secret.value = "test-secret-value-v2"
        mock_azure_client.get_secret.return_value = mock_secret

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            result = await secret.get("test_secret", version="v2")

            mock_azure_client.get_secret.assert_called_once_with(
                "acb-secrets-acb-test-secret", version="v2"
            )
            assert result == "test-secret-value-v2"

    async def test_get_secret_not_found_none_value(
        self, mock_secret_settings, mock_azure_client
    ):
        """Test getting a secret that returns None."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        mock_secret = MagicMock()
        mock_secret.value = None
        mock_azure_client.get_secret.return_value = mock_secret

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            result = await secret.get("nonexistent_secret")

            assert result is None

    async def test_get_secret_not_found_exception(
        self, mock_secret_settings, mock_azure_client
    ):
        """Test getting a secret that raises NotFound exception."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        # Create a mock exception that simulates Azure's ResourceNotFoundError
        class MockResourceNotFoundError(Exception):
            pass

        MockResourceNotFoundError.__name__ = "ResourceNotFoundError"
        mock_azure_client.get_secret.side_effect = MockResourceNotFoundError(
            "Secret not found"
        )

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            result = await secret.get("nonexistent_secret")

            assert result is None

    async def test_create_secret(self, mock_secret_settings, mock_azure_client):
        """Test creating a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            await secret.create("new_secret", "new-secret-value")

            mock_azure_client.set_secret.assert_called_once_with(
                "acb-secrets-acb-new-secret", "new-secret-value"
            )

            secret.logger.debug.assert_called_once_with("Created secret - new_secret")

    async def test_update_secret(self, mock_secret_settings, mock_azure_client):
        """Test updating a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            await secret.update("existing_secret", "updated-value")

            mock_azure_client.set_secret.assert_called_once_with(
                "acb-secrets-acb-existing-secret", "updated-value"
            )

            secret.logger.debug.assert_called_once_with(
                "Updated secret - existing_secret"
            )

    async def test_set_secret(self, mock_secret_settings, mock_azure_client):
        """Test setting a secret (should call update)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "update") as mock_update:
            await secret.set("test_secret", "test-value")

            mock_update.assert_called_once_with("test_secret", "test-value")

    async def test_exists_true(self, mock_secret_settings, mock_azure_client):
        """Test checking if secret exists (returns True)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", return_value="secret-value"):
            result = await secret.exists("test_secret")
            assert result is True

    async def test_exists_false(self, mock_secret_settings, mock_azure_client):
        """Test checking if secret exists (returns False)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", return_value=None):
            result = await secret.exists("test_secret")
            assert result is False

    async def test_exists_exception(self, mock_secret_settings, mock_azure_client):
        """Test checking if secret exists when get raises exception."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", side_effect=Exception("Network error")):
            result = await secret.exists("test_secret")
            assert result is False

    async def test_delete_secret(self, mock_secret_settings, mock_azure_client):
        """Test deleting a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            await secret.delete("test_secret")

            mock_azure_client.begin_delete_secret.assert_called_once_with(
                "acb-secrets-acb-test-secret"
            )
            secret.logger.debug.assert_called_once_with("Deleted secret - test_secret")

    async def test_list_versions(self, mock_secret_settings, mock_azure_client):
        """Test listing secret versions."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        # Mock version properties
        mock_version1 = MagicMock()
        mock_version1.version = "v1"
        mock_version2 = MagicMock()
        mock_version2.version = "v2"
        mock_version3 = MagicMock()
        mock_version3.version = None  # Should be skipped

        mock_azure_client.list_properties_of_secret_versions.return_value = [
            mock_version1,
            mock_version2,
            mock_version3,
        ]

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            result = await secret.list_versions("test_secret")

            mock_azure_client.list_properties_of_secret_versions.assert_called_once_with(
                "acb-secrets-acb-test-secret"
            )
            assert result == ["v1", "v2"]

    async def test_list_versions_exception(
        self, mock_secret_settings, mock_azure_client
    ):
        """Test listing secret versions with exception."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()

        mock_azure_client.list_properties_of_secret_versions.side_effect = Exception(
            "List failed"
        )

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            result = await secret.list_versions("test_secret")

            assert result == []
            secret.logger.exception.assert_called_once()

    async def test_error_handling_in_operations(
        self, mock_secret_settings, mock_azure_client
    ):
        """Test error handling in various operations."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()

        # Test error in list operation
        mock_azure_client.list_properties_of_secrets.side_effect = Exception(
            "List failed"
        )

        with (
            patch.object(secret, "get_client", return_value=mock_azure_client),
            pytest.raises(Exception, match="List failed"),
        ):
            await secret.list()

        secret.logger.exception.assert_called_with(
            "Failed to list secrets: List failed"
        )

        # Test error in get operation (non-NotFound)
        secret.logger.reset_mock()
        mock_azure_client.get_secret.side_effect = Exception("Get failed")

        with (
            patch.object(secret, "get_client", return_value=mock_azure_client),
            pytest.raises(Exception, match="Get failed"),
        ):
            await secret.get("test_secret")

        secret.logger.exception.assert_called_with(
            "Failed to get secret test_secret: Get failed"
        )

        # Test error in create operation
        secret.logger.reset_mock()
        mock_azure_client.set_secret.side_effect = Exception("Create failed")

        with (
            patch.object(secret, "get_client", return_value=mock_azure_client),
            pytest.raises(Exception, match="Create failed"),
        ):
            await secret.create("test_secret", "value")

        secret.logger.exception.assert_called_with(
            "Failed to create secret test_secret: Create failed"
        )

        # Test error in update operation
        secret.logger.reset_mock()

        with (
            patch.object(secret, "get_client", return_value=mock_azure_client),
            pytest.raises(Exception, match="Create failed"),
        ):  # Same error as create
            await secret.update("test_secret", "value")

        secret.logger.exception.assert_called_with(
            "Failed to update secret test_secret: Create failed"
        )

        # Test error in delete operation
        secret.logger.reset_mock()
        mock_azure_client.begin_delete_secret.side_effect = Exception("Delete failed")

        with (
            patch.object(secret, "get_client", return_value=mock_azure_client),
            pytest.raises(Exception, match="Delete failed"),
        ):
            await secret.delete("test_secret")

        secret.logger.exception.assert_called_with(
            "Failed to delete secret test_secret: Delete failed"
        )

    async def test_comprehensive_workflow(
        self, mock_secret_settings, mock_azure_client
    ):
        """Test a comprehensive workflow with multiple operations."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        # Mock all client methods
        mock_azure_client.list_properties_of_secrets.return_value = []

        mock_secret_obj = MagicMock()
        mock_secret_obj.value = "workflow-value"
        mock_azure_client.get_secret.return_value = mock_secret_obj

        mock_azure_client.set_secret.return_value = None
        mock_azure_client.begin_delete_secret.return_value = None

        mock_version1 = MagicMock()
        mock_version1.version = "v1"
        mock_azure_client.list_properties_of_secret_versions.return_value = [
            mock_version1
        ]

        with patch.object(secret, "get_client", return_value=mock_azure_client):
            # Create secret
            await secret.create("workflow_secret", "workflow-value")

            # Get secret
            value = await secret.get("workflow_secret")
            assert value == "workflow-value"

            # List secrets
            secrets = await secret.list()
            assert secrets == []

            # Update secret
            await secret.update("workflow_secret", "updated-value")

            # Set secret (calls update)
            await secret.set("workflow_secret", "set-value")

            # Check if exists
            with patch.object(secret, "get", return_value="exists"):
                exists = await secret.exists("workflow_secret")
                assert exists is True

            # List versions
            versions = await secret.list_versions("workflow_secret")
            assert versions == ["v1"]

            # Delete secret
            await secret.delete("workflow_secret")

            # Verify all operations were called
            mock_azure_client.list_properties_of_secrets.assert_called_once()
            mock_azure_client.get_secret.assert_called_once()
            assert mock_azure_client.set_secret.call_count == 3  # create + update + set
            mock_azure_client.begin_delete_secret.assert_called_once()
            mock_azure_client.list_properties_of_secret_versions.assert_called_once()

    def test_module_metadata(self):
        """Test module metadata is properly defined."""
        from acb.adapters.secret.azure import MODULE_METADATA

        assert MODULE_METADATA.name == "Azure Key Vault"
        assert MODULE_METADATA.category == "secret"
        assert MODULE_METADATA.provider == "azure"
        assert MODULE_METADATA.version == "1.0.0"
        assert "azure-keyvault-secrets>=4.8.0" in MODULE_METADATA.required_packages
        assert "azure-identity>=1.15.0" in MODULE_METADATA.required_packages
        assert len(MODULE_METADATA.capabilities) == 3
        assert (
            MODULE_METADATA.description == "Azure Key Vault secret management adapter"
        )

    async def test_name_conversion_edge_cases(self, mock_secret_settings):
        """Test edge cases in name conversion between underscores and dashes."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_test_"

        # Test multiple underscores
        result = secret._get_full_key("my_test_secret_name")
        assert result == "acb-secrets-acb-test-my-test-secret-name"

        # Test extraction
        extracted = secret._extract_secret_name(
            "acb-secrets-acb-test-my-test-secret-name"
        )
        assert extracted == "my_test_secret_name"

        # Test empty adapter name handling in list
        mock_secret_settings.secret.secret_prefix = "test_prefix_"
        result_prefix = secret._get_full_key("simple")
        assert result_prefix == "test-prefix-acb-test-simple"

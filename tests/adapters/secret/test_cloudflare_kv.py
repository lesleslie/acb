"""Tests for Cloudflare KV Secret adapter."""

from unittest.mock import MagicMock, patch

import pytest
from anyio import Path as AsyncPath

from acb.adapters.secret.cloudflare import Secret, SecretSettings


class TestCloudflareKVSecretSettings:
    """Test Cloudflare KV Secret settings."""

    def test_init_with_defaults(self, mock_config):
        """Test settings initialization with default values."""
        settings = SecretSettings(secrets_path=AsyncPath("/tmp/secrets"))

        assert settings.api_token is None
        assert settings.account_id is None
        assert settings.namespace_id is None
        assert settings.key_prefix == "acb_secrets_"
        assert settings.ttl is None

    def test_init_with_custom_values(self, mock_config):
        """Test settings initialization with custom values."""
        settings = SecretSettings(
            secrets_path=AsyncPath("/tmp/custom"),
            api_token="test-api-token",
            account_id="test-account-id",
            namespace_id="test-namespace-id",
            key_prefix="my_secrets_",
            ttl=3600,
        )

        assert settings.api_token == "test-api-token"
        assert settings.account_id == "test-account-id"
        assert settings.namespace_id == "test-namespace-id"
        assert settings.key_prefix == "my_secrets_"
        assert settings.ttl == 3600


class TestCloudflareKVSecret:
    """Test Cloudflare KV Secret adapter."""

    @pytest.fixture
    def mock_secret_settings(self, mock_config):
        """Mock secret settings for testing."""
        mock_config.secret = SecretSettings(
            secrets_path=AsyncPath("/tmp/test"),
            api_token="test-api-token",
            account_id="test-account-id",
            namespace_id="test-namespace-id",
            key_prefix="acb_secrets_",
            ttl=3600,
        )
        return mock_config

    @pytest.fixture
    def mock_cloudflare_client(self):
        """Mock Cloudflare client."""
        client = MagicMock()

        # Mock KV namespace operations
        client.kv.namespaces.keys.list = MagicMock()
        client.kv.namespaces.values.get = MagicMock()
        client.kv.namespaces.bulk.update = MagicMock()
        client.kv.namespaces.bulk.delete = MagicMock()

        return client

    @patch("acb.adapters.secret.cloudflare._cloudflare_available", True)
    def test_init_cloudflare_available(self, mock_secret_settings):
        """Test adapter initialization when Cloudflare SDK is available."""
        secret = Secret()
        secret.config = mock_secret_settings

        assert secret._client is None

    @patch("acb.adapters.secret.cloudflare._cloudflare_available", False)
    def test_init_cloudflare_not_available(self, mock_secret_settings):
        """Test adapter initialization when Cloudflare SDK is not available."""
        with pytest.raises(ImportError, match="Cloudflare SDK not available"):
            Secret()

    @patch("acb.adapters.secret.cloudflare.Cloudflare")
    async def test_create_client_success(
        self, mock_cloudflare_class, mock_secret_settings, mock_cloudflare_client
    ):
        """Test successful client creation."""
        mock_cloudflare_class.return_value = mock_cloudflare_client

        secret = Secret()
        secret.config = mock_secret_settings

        client = await secret._create_client()

        mock_cloudflare_class.assert_called_once_with(api_token="test-api-token")
        assert client == mock_cloudflare_client

    async def test_create_client_missing_api_token(self, mock_secret_settings):
        """Test client creation with missing API token."""
        mock_secret_settings.secret.api_token = None

        secret = Secret()
        secret.config = mock_secret_settings

        with pytest.raises(ValueError, match="Cloudflare API token is required"):
            await secret._create_client()

    async def test_create_client_missing_account_id(self, mock_secret_settings):
        """Test client creation with missing account ID."""
        mock_secret_settings.secret.account_id = None

        secret = Secret()
        secret.config = mock_secret_settings

        with pytest.raises(ValueError, match="Cloudflare account ID is required"):
            await secret._create_client()

    async def test_create_client_missing_namespace_id(self, mock_secret_settings):
        """Test client creation with missing namespace ID."""
        mock_secret_settings.secret.namespace_id = None

        secret = Secret()
        secret.config = mock_secret_settings

        with pytest.raises(ValueError, match="Cloudflare KV namespace ID is required"):
            await secret._create_client()

    async def test_get_client(self, mock_secret_settings, mock_cloudflare_client):
        """Test client getter with lazy initialization."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(
            secret, "_create_client", return_value=mock_cloudflare_client
        ) as mock_create:
            client = await secret.get_client()

            mock_create.assert_called_once()
            assert secret._client == client
            assert client == mock_cloudflare_client

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

    def test_client_property_initialized(
        self, mock_secret_settings, mock_cloudflare_client
    ):
        """Test client property when initialized."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret._client = mock_cloudflare_client

        assert secret.client == mock_cloudflare_client

    def test_get_full_key(self, mock_secret_settings):
        """Test full key generation."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        result = secret._get_full_key("test_secret")

        assert result == "acb_secrets_acb_test_secret"

    def test_extract_secret_name(self, mock_secret_settings):
        """Test secret name extraction."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        result = secret._extract_secret_name("acb_secrets_acb_test_secret")

        assert result == "test_secret"

    async def test_init_method_success(
        self, mock_secret_settings, mock_cloudflare_client
    ):
        """Test successful initialization."""
        secret = Secret()
        secret.config = mock_secret_settings

        mock_logger = MagicMock()

        with (
            patch.object(secret, "get_client", return_value=mock_cloudflare_client),
            patch.object(secret, "list", return_value=["secret1", "secret2"]),
        ):
            await secret.init(logger=mock_logger)

            mock_logger.info.assert_called_once_with(
                "Cloudflare KV secret adapter initialized successfully"
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

    async def test_list_secrets(self, mock_secret_settings, mock_cloudflare_client):
        """Test listing secrets."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        # Mock response
        mock_key1 = MagicMock()
        mock_key1.name = "acb_secrets_acb_secret1"
        mock_key2 = MagicMock()
        mock_key2.name = "acb_secrets_acb_secret2"
        mock_key3 = MagicMock()
        mock_key3.name = "other_prefix_secret3"

        mock_response = MagicMock()
        mock_response.result = [mock_key1, mock_key2, mock_key3]
        mock_cloudflare_client.kv.namespaces.keys.list.return_value = mock_response

        with patch.object(secret, "get_client", return_value=mock_cloudflare_client):
            result = await secret.list()

            mock_cloudflare_client.kv.namespaces.keys.list.assert_called_once_with(
                "test-namespace-id",
                account_id="test-account-id",
                prefix="acb_secrets_acb_",
            )

            assert result == ["secret1", "secret2"]

    async def test_list_secrets_with_adapter_filter(
        self, mock_secret_settings, mock_cloudflare_client
    ):
        """Test listing secrets with adapter filter."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        # Mock response
        mock_key1 = MagicMock()
        mock_key1.name = "acb_secrets_acb_cache_secret1"
        mock_key2 = MagicMock()
        mock_key2.name = "acb_secrets_acb_sql_secret2"

        mock_response = MagicMock()
        mock_response.result = [mock_key1, mock_key2]
        mock_cloudflare_client.kv.namespaces.keys.list.return_value = mock_response

        with patch.object(secret, "get_client", return_value=mock_cloudflare_client):
            result = await secret.list("cache")

            mock_cloudflare_client.kv.namespaces.keys.list.assert_called_once_with(
                "test-namespace-id",
                account_id="test-account-id",
                prefix="acb_secrets_acb_cache_",
            )

            assert result == ["cache_secret1"]

    async def test_get_secret(self, mock_secret_settings, mock_cloudflare_client):
        """Test getting a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        mock_cloudflare_client.kv.namespaces.values.get.return_value = (
            "test-secret-value"
        )

        with patch.object(secret, "get_client", return_value=mock_cloudflare_client):
            result = await secret.get("test_secret")

            mock_cloudflare_client.kv.namespaces.values.get.assert_called_once_with(
                "test-namespace-id",
                "acb_secrets_acb_test_secret",
                account_id="test-account-id",
            )

            assert result == "test-secret-value"
            secret.logger.info.assert_called_once_with("Fetched secret - test_secret")

    async def test_get_secret_not_found(
        self, mock_secret_settings, mock_cloudflare_client
    ):
        """Test getting a secret that doesn't exist."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        mock_cloudflare_client.kv.namespaces.values.get.return_value = None

        with patch.object(secret, "get_client", return_value=mock_cloudflare_client):
            result = await secret.get("nonexistent_secret")

            assert result is None

    async def test_create_secret(self, mock_secret_settings, mock_cloudflare_client):
        """Test creating a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_cloudflare_client):
            await secret.create("new_secret", "new-secret-value")

            mock_cloudflare_client.kv.namespaces.bulk.update.assert_called_once_with(
                "test-namespace-id",
                [
                    {
                        "key": "acb_secrets_acb_new_secret",
                        "value": "new-secret-value",
                        "expiration_ttl": 3600,
                    }
                ],
                account_id="test-account-id",
            )

            secret.logger.debug.assert_called_once_with("Created secret - new_secret")

    async def test_create_secret_no_ttl(
        self, mock_secret_settings, mock_cloudflare_client
    ):
        """Test creating a secret without TTL."""
        mock_secret_settings.secret.ttl = None

        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_cloudflare_client):
            await secret.create("new_secret", "new-secret-value")

            mock_cloudflare_client.kv.namespaces.bulk.update.assert_called_once_with(
                "test-namespace-id",
                [{"key": "acb_secrets_acb_new_secret", "value": "new-secret-value"}],
                account_id="test-account-id",
            )

    async def test_update_secret(self, mock_secret_settings, mock_cloudflare_client):
        """Test updating a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_cloudflare_client):
            await secret.update("existing_secret", "updated-value")

            mock_cloudflare_client.kv.namespaces.bulk.update.assert_called_once_with(
                "test-namespace-id",
                [
                    {
                        "key": "acb_secrets_acb_existing_secret",
                        "value": "updated-value",
                        "expiration_ttl": 3600,
                    }
                ],
                account_id="test-account-id",
            )

            secret.logger.debug.assert_called_once_with(
                "Updated secret - existing_secret"
            )

    async def test_set_secret(self, mock_secret_settings, mock_cloudflare_client):
        """Test setting a secret (should call update)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "update") as mock_update:
            await secret.set("test_secret", "test-value")

            mock_update.assert_called_once_with("test_secret", "test-value")

    async def test_exists_true(self, mock_secret_settings, mock_cloudflare_client):
        """Test checking if secret exists (returns True)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", return_value="secret-value"):
            result = await secret.exists("test_secret")
            assert result is True

    async def test_exists_false(self, mock_secret_settings, mock_cloudflare_client):
        """Test checking if secret exists (returns False)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", return_value=None):
            result = await secret.exists("test_secret")
            assert result is False

    async def test_exists_exception(self, mock_secret_settings, mock_cloudflare_client):
        """Test checking if secret exists when get raises exception."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", side_effect=Exception("Network error")):
            result = await secret.exists("test_secret")
            assert result is False

    async def test_delete_secret(self, mock_secret_settings, mock_cloudflare_client):
        """Test deleting a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_cloudflare_client):
            await secret.delete("test_secret")

            mock_cloudflare_client.kv.namespaces.bulk.delete.assert_called_once_with(
                "test-namespace-id",
                ["acb_secrets_acb_test_secret"],
                account_id="test-account-id",
            )

            secret.logger.debug.assert_called_once_with("Deleted secret - test_secret")

    async def test_list_versions(self, mock_secret_settings, mock_cloudflare_client):
        """Test listing secret versions (not supported)."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()

        result = await secret.list_versions("test_secret")

        assert result == []
        secret.logger.warning.assert_called_once_with(
            "Listing secret versions is not supported by Cloudflare KV adapter"
        )

    async def test_error_handling_in_operations(
        self, mock_secret_settings, mock_cloudflare_client
    ):
        """Test error handling in various operations."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()

        # Test error in list operation
        mock_cloudflare_client.kv.namespaces.keys.list.side_effect = Exception(
            "List failed"
        )

        with (
            patch.object(secret, "get_client", return_value=mock_cloudflare_client),
            pytest.raises(Exception, match="List failed"),
        ):
            await secret.list()

        secret.logger.exception.assert_called_with(
            "Failed to list secrets: List failed"
        )

        # Test error in get operation
        secret.logger.reset_mock()
        mock_cloudflare_client.kv.namespaces.values.get.side_effect = Exception(
            "Get failed"
        )

        with (
            patch.object(secret, "get_client", return_value=mock_cloudflare_client),
            pytest.raises(Exception, match="Get failed"),
        ):
            await secret.get("test_secret")

        secret.logger.exception.assert_called_with(
            "Failed to get secret test_secret: Get failed"
        )

        # Test error in create operation
        secret.logger.reset_mock()
        mock_cloudflare_client.kv.namespaces.bulk.update.side_effect = Exception(
            "Create failed"
        )

        with (
            patch.object(secret, "get_client", return_value=mock_cloudflare_client),
            pytest.raises(Exception, match="Create failed"),
        ):
            await secret.create("test_secret", "value")

        secret.logger.exception.assert_called_with(
            "Failed to create secret test_secret: Create failed"
        )

        # Test error in update operation
        secret.logger.reset_mock()

        with (
            patch.object(secret, "get_client", return_value=mock_cloudflare_client),
            pytest.raises(Exception, match="Create failed"),
        ):  # Same error as create
            await secret.update("test_secret", "value")

        secret.logger.exception.assert_called_with(
            "Failed to update secret test_secret: Create failed"
        )

        # Test error in delete operation
        secret.logger.reset_mock()
        mock_cloudflare_client.kv.namespaces.bulk.delete.side_effect = Exception(
            "Delete failed"
        )

        with (
            patch.object(secret, "get_client", return_value=mock_cloudflare_client),
            pytest.raises(Exception, match="Delete failed"),
        ):
            await secret.delete("test_secret")

        secret.logger.exception.assert_called_with(
            "Failed to delete secret test_secret: Delete failed"
        )

    async def test_comprehensive_workflow(
        self, mock_secret_settings, mock_cloudflare_client
    ):
        """Test a comprehensive workflow with multiple operations."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        # Mock all client methods
        mock_response = MagicMock()
        mock_response.result = []
        mock_cloudflare_client.kv.namespaces.keys.list.return_value = mock_response
        mock_cloudflare_client.kv.namespaces.values.get.return_value = "workflow-value"
        mock_cloudflare_client.kv.namespaces.bulk.update.return_value = None
        mock_cloudflare_client.kv.namespaces.bulk.delete.return_value = None

        with patch.object(secret, "get_client", return_value=mock_cloudflare_client):
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

            # List versions (not supported)
            versions = await secret.list_versions("workflow_secret")
            assert versions == []

            # Delete secret
            await secret.delete("workflow_secret")

            # Verify all operations were called
            mock_cloudflare_client.kv.namespaces.keys.list.assert_called_once()
            mock_cloudflare_client.kv.namespaces.values.get.assert_called_once()
            assert (
                mock_cloudflare_client.kv.namespaces.bulk.update.call_count == 3
            )  # create + update + set
            mock_cloudflare_client.kv.namespaces.bulk.delete.assert_called_once()

    def test_module_metadata(self):
        """Test module metadata is properly defined."""
        from acb.adapters.secret.cloudflare import MODULE_METADATA

        assert MODULE_METADATA.name == "Cloudflare KV"
        assert MODULE_METADATA.category == "secret"
        assert MODULE_METADATA.provider == "cloudflare"
        assert MODULE_METADATA.version == "1.0.0"
        assert "cloudflare>=3.0.0" in MODULE_METADATA.required_packages
        # Check that capabilities are present (they're enum members)
        assert len(MODULE_METADATA.capabilities) == 3
        assert (
            MODULE_METADATA.description
            == "Cloudflare Workers KV secret management adapter"
        )

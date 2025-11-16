"""Tests for Infisical Secret adapter."""

from unittest.mock import MagicMock, patch

import pytest
from anyio import Path as AsyncPath

from acb.adapters.secret.infisical import Secret, SecretSettings


class TestInfisicalSecretSettings:
    """Test Infisical Secret settings."""

    def test_init_with_defaults(self, mock_config):
        """Test settings initialization with default values."""
        settings = SecretSettings(secrets_path=AsyncPath("/tmp/secrets"))

        assert settings.host == "https://app.infisical.com"
        assert settings.client_id is None
        assert settings.client_secret is None
        assert settings.token is None
        assert settings.project_id is None
        assert settings.environment == "dev"
        assert settings.secret_path == "/"
        assert settings.cache_ttl == 60

    def test_init_with_custom_values(self, mock_config):
        """Test settings initialization with custom values."""
        settings = SecretSettings(
            secrets_path=AsyncPath("/tmp/custom"),
            host="https://custom.infisical.com",
            client_id="test-client-id",
            client_secret="test-client-secret",
            token="test-token",
            project_id="test-project-id",
            environment="prod",
            secret_path="/app",
            cache_ttl=120,
        )

        assert settings.host == "https://custom.infisical.com"
        assert settings.client_id == "test-client-id"
        assert settings.client_secret == "test-client-secret"
        assert settings.token == "test-token"
        assert settings.project_id == "test-project-id"
        assert settings.environment == "prod"
        assert settings.secret_path == "/app"
        assert settings.cache_ttl == 120


class TestInfisicalSecret:
    """Test Infisical Secret adapter."""

    @pytest.fixture
    def mock_secret_settings(self, mock_config):
        """Mock secret settings for testing."""
        mock_config.secret = SecretSettings(
            secrets_path=AsyncPath("/tmp/test"),
            host="https://test.infisical.com",
            token="test-token",
            project_id="test-project-id",
            environment="test",
            secret_path="/test",
            cache_ttl=60,
        )
        return mock_config

    @pytest.fixture
    def mock_infisical_client(self):
        """Mock Infisical SDK client."""
        client = MagicMock()
        client.auth.universal_auth.login = MagicMock()

        # Mock secrets operations
        client.secrets.list_secrets = MagicMock()
        client.secrets.get_secret_by_name = MagicMock()
        client.secrets.create_secret_by_name = MagicMock()
        client.secrets.update_secret_by_name = MagicMock()
        client.secrets.delete_secret_by_name = MagicMock()

        return client

    def test_init(self, mock_secret_settings):
        """Test adapter initialization."""
        secret = Secret()
        secret.config = mock_secret_settings

        assert secret._client is None

    @patch("acb.adapters.secret.infisical.InfisicalSDKClient")
    async def test_create_client_with_token(
        self, mock_client_class, mock_secret_settings, mock_infisical_client
    ):
        """Test client creation with token authentication."""
        mock_client_class.return_value = mock_infisical_client

        secret = Secret()
        secret.config = mock_secret_settings

        client = await secret._create_client()

        mock_client_class.assert_called_once_with(
            host="https://test.infisical.com", token="test-token", cache_ttl=60
        )
        assert client == mock_infisical_client
        mock_infisical_client.auth.universal_auth.login.assert_not_called()

    @patch("acb.adapters.secret.infisical.InfisicalSDKClient")
    async def test_create_client_with_universal_auth(
        self, mock_client_class, mock_secret_settings, mock_infisical_client
    ):
        """Test client creation with universal auth."""
        mock_client_class.return_value = mock_infisical_client

        # Remove token and set client credentials
        mock_secret_settings.secret.token = None
        mock_secret_settings.secret.client_id = "test-client-id"
        mock_secret_settings.secret.client_secret = "test-client-secret"

        secret = Secret()
        secret.config = mock_secret_settings

        await secret._create_client()

        mock_client_class.assert_called_once_with(
            host="https://test.infisical.com", token=None, cache_ttl=60
        )
        mock_infisical_client.auth.universal_auth.login.assert_called_once_with(
            client_id="test-client-id", client_secret="test-client-secret"
        )

    async def test_get_client(self, mock_secret_settings, mock_infisical_client):
        """Test client getter with lazy initialization."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(
            secret, "_create_client", return_value=mock_infisical_client
        ) as mock_create:
            client = await secret.get_client()

            mock_create.assert_called_once()
            assert secret._client == client
            assert client == mock_infisical_client

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
        self, mock_secret_settings, mock_infisical_client
    ):
        """Test client property when initialized."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret._client = mock_infisical_client

        assert secret.client == mock_infisical_client

    async def test_init_method_success(
        self, mock_secret_settings, mock_infisical_client
    ):
        """Test successful initialization."""
        secret = Secret()
        secret.config = mock_secret_settings

        mock_logger = MagicMock()

        with (
            patch.object(secret, "get_client", return_value=mock_infisical_client),
            patch.object(secret, "list", return_value=["secret1", "secret2"]),
        ):
            await secret.init(logger=mock_logger)

            mock_logger.info.assert_called_once_with(
                "Infisical secret adapter initialized successfully"
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

    def test_extract_secret_name(self, mock_secret_settings):
        """Test secret name extraction."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        result = secret.extract_secret_name("acb_test_secret")
        assert result == "test_secret"

        result = secret.extract_secret_name("some/path/acb_another_secret")
        assert result == "another_secret"

    @patch("asyncio.to_thread")
    async def test_list_secrets(
        self, mock_to_thread, mock_secret_settings, mock_infisical_client
    ):
        """Test listing secrets."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        # Mock response
        mock_secret_obj1 = MagicMock()
        mock_secret_obj1.secretKey = "acb_secret1"
        mock_secret_obj2 = MagicMock()
        mock_secret_obj2.secretKey = "acb_secret2"
        mock_secret_obj3 = MagicMock()
        mock_secret_obj3.secretKey = "other_secret"

        mock_response = MagicMock()
        mock_response.secrets = [mock_secret_obj1, mock_secret_obj2, mock_secret_obj3]
        mock_to_thread.return_value = mock_response

        with patch.object(secret, "get_client", return_value=mock_infisical_client):
            result = await secret.list()

            mock_to_thread.assert_called_once_with(
                mock_infisical_client.secrets.list_secrets,
                project_id="test-project-id",
                environment_slug="test",
                secret_path="/test",
            )
            assert result == ["secret1", "secret2"]

    @patch("asyncio.to_thread")
    async def test_list_secrets_with_adapter_filter(
        self, mock_to_thread, mock_secret_settings, mock_infisical_client
    ):
        """Test listing secrets with adapter filter."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        # Mock response
        mock_secret_obj1 = MagicMock()
        mock_secret_obj1.secretKey = "acb_cache_secret1"
        mock_secret_obj2 = MagicMock()
        mock_secret_obj2.secretKey = "acb_sql_secret2"

        mock_response = MagicMock()
        mock_response.secrets = [mock_secret_obj1, mock_secret_obj2]
        mock_to_thread.return_value = mock_response

        with patch.object(secret, "get_client", return_value=mock_infisical_client):
            result = await secret.list("cache")

            assert result == ["cache_secret1"]

    async def test_list_secrets_no_project_id(
        self, mock_secret_settings, mock_infisical_client
    ):
        """Test listing secrets without project ID."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.config.secret.project_id = None
        secret.logger = MagicMock()  # Mock logger to prevent AttributeError

        with (
            patch.object(secret, "get_client", return_value=mock_infisical_client),
            pytest.raises(ValueError, match="Project ID is required"),
        ):
            await secret.list()

    @patch("asyncio.to_thread")
    async def test_get_secret(
        self, mock_to_thread, mock_secret_settings, mock_infisical_client
    ):
        """Test getting a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        mock_response = MagicMock()
        mock_response.secretValue = "test-secret-value"
        mock_to_thread.return_value = mock_response

        with patch.object(secret, "get_client", return_value=mock_infisical_client):
            result = await secret.get("test_secret")

            mock_to_thread.assert_called_once_with(
                mock_infisical_client.secrets.get_secret_by_name,
                secret_name="acb_test_secret",
                project_id="test-project-id",
                environment_slug="test",
                secret_path="/test",
                version="",
            )
            assert result == "test-secret-value"
            secret.logger.info.assert_called_once_with("Fetched secret - test_secret")

    @patch("asyncio.to_thread")
    async def test_get_secret_with_version(
        self, mock_to_thread, mock_secret_settings, mock_infisical_client
    ):
        """Test getting a secret with specific version."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        mock_response = MagicMock()
        mock_response.secretValue = "test-secret-value-v2"
        mock_to_thread.return_value = mock_response

        with patch.object(secret, "get_client", return_value=mock_infisical_client):
            result = await secret.get("test_secret", version="v2")

            mock_to_thread.assert_called_once_with(
                mock_infisical_client.secrets.get_secret_by_name,
                secret_name="acb_test_secret",
                project_id="test-project-id",
                environment_slug="test",
                secret_path="/test",
                version="v2",
            )
            assert result == "test-secret-value-v2"

    async def test_get_secret_no_project_id(
        self, mock_secret_settings, mock_infisical_client
    ):
        """Test getting secret without project ID."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.config.secret.project_id = None
        secret.logger = MagicMock()  # Mock logger to prevent AttributeError

        with (
            patch.object(secret, "get_client", return_value=mock_infisical_client),
            pytest.raises(ValueError, match="Project ID is required"),
        ):
            await secret.get("test_secret")

    @patch("asyncio.to_thread")
    async def test_create_secret(
        self, mock_to_thread, mock_secret_settings, mock_infisical_client
    ):
        """Test creating a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_infisical_client):
            await secret.create("new_secret", "new-value")

            mock_to_thread.assert_called_once_with(
                mock_infisical_client.secrets.create_secret_by_name,
                secret_name="acb_new_secret",
                project_id="test-project-id",
                environment_slug="test",
                secret_path="/test",
                secret_value="new-value",
            )
            secret.logger.debug.assert_called_once_with("Created secret - new_secret")

    @patch("asyncio.to_thread")
    async def test_update_secret(
        self, mock_to_thread, mock_secret_settings, mock_infisical_client
    ):
        """Test updating a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_infisical_client):
            await secret.update("existing_secret", "updated-value")

            mock_to_thread.assert_called_once_with(
                mock_infisical_client.secrets.update_secret_by_name,
                current_secret_name="acb_existing_secret",
                project_id="test-project-id",
                environment_slug="test",
                secret_path="/test",
                secret_value="updated-value",
            )
            secret.logger.debug.assert_called_once_with(
                "Updated secret - existing_secret"
            )

    async def test_set_secret_exists(self, mock_secret_settings, mock_infisical_client):
        """Test setting a secret that already exists."""
        secret = Secret()
        secret.config = mock_secret_settings

        with (
            patch.object(secret, "exists", return_value=True),
            patch.object(secret, "update") as mock_update,
            patch.object(secret, "create") as mock_create,
        ):
            await secret.set("test_secret", "test-value")

            mock_update.assert_called_once_with("test_secret", "test-value")
            mock_create.assert_not_called()

    async def test_set_secret_new(self, mock_secret_settings, mock_infisical_client):
        """Test setting a new secret."""
        secret = Secret()
        secret.config = mock_secret_settings

        with (
            patch.object(secret, "exists", return_value=False),
            patch.object(secret, "update") as mock_update,
            patch.object(secret, "create") as mock_create,
        ):
            await secret.set("test_secret", "test-value")

            mock_create.assert_called_once_with("test_secret", "test-value")
            mock_update.assert_not_called()

    async def test_exists_true(self, mock_secret_settings, mock_infisical_client):
        """Test checking if secret exists (returns True)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", return_value="secret-value"):
            result = await secret.exists("test_secret")
            assert result is True

    async def test_exists_false(self, mock_secret_settings, mock_infisical_client):
        """Test checking if secret exists (returns False)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", side_effect=Exception("Not found")):
            result = await secret.exists("test_secret")
            assert result is False

    @patch("asyncio.to_thread")
    async def test_delete_secret(
        self, mock_to_thread, mock_secret_settings, mock_infisical_client
    ):
        """Test deleting a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.logger = MagicMock()

        with patch.object(secret, "get_client", return_value=mock_infisical_client):
            await secret.delete("test_secret")

            mock_to_thread.assert_called_once_with(
                mock_infisical_client.secrets.delete_secret_by_name,
                secret_name="acb_test_secret",
                project_id="test-project-id",
                environment_slug="test",
                secret_path="/test",
            )
            secret.logger.debug.assert_called_once_with("Deleted secret - test_secret")

    async def test_list_versions(self, mock_secret_settings, mock_infisical_client):
        """Test listing secret versions (not supported)."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()

        result = await secret.list_versions("test_secret")

        assert result == []
        secret.logger.warning.assert_called_once_with(
            "Listing secret versions is not currently supported by the Infisical adapter"
        )

    async def test_error_handling_in_operations(
        self, mock_secret_settings, mock_infisical_client
    ):
        """Test error handling in various operations."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()

        # Test error in list operation
        with (
            patch.object(
                secret, "get_client", side_effect=Exception("Connection failed")
            ),
            pytest.raises(Exception, match="Connection failed"),
        ):
            await secret.list()

        secret.logger.exception.assert_called_with(
            "Unexpected error listing secrets: Connection failed"
        )

        # Test error in get operation
        secret.logger.reset_mock()
        with (
            patch.object(secret, "get_client", side_effect=Exception("Get failed")),
            pytest.raises(Exception, match="Get failed"),
        ):
            await secret.get("test_secret")

        secret.logger.exception.assert_called_with(
            "Unexpected error getting secret test_secret: Get failed"
        )

        # Test error in create operation
        secret.logger.reset_mock()
        with (
            patch.object(secret, "get_client", side_effect=Exception("Create failed")),
            pytest.raises(Exception, match="Create failed"),
        ):
            await secret.create("test_secret", "value")

        secret.logger.exception.assert_called_with(
            "Unexpected error creating secret test_secret: Create failed"
        )

        # Test error in update operation
        secret.logger.reset_mock()
        with (
            patch.object(secret, "get_client", side_effect=Exception("Update failed")),
            pytest.raises(Exception, match="Update failed"),
        ):
            await secret.update("test_secret", "value")

        secret.logger.exception.assert_called_with(
            "Unexpected error updating secret test_secret: Update failed"
        )

        # Test error in delete operation
        secret.logger.reset_mock()
        with (
            patch.object(secret, "get_client", side_effect=Exception("Delete failed")),
            pytest.raises(Exception, match="Delete failed"),
        ):
            await secret.delete("test_secret")

        secret.logger.exception.assert_called_with(
            "Unexpected error deleting secret test_secret: Delete failed"
        )

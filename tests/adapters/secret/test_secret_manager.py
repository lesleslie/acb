"""Tests for Google Secret Manager adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from google.api_core.exceptions import AlreadyExists, PermissionDenied

from acb.adapters.secret.secret_manager import Secret, SecretSettings


class TestSecretManagerSettings:
    """Test Google Secret Manager settings."""

    def test_init_with_defaults(self, mock_config):
        """Test settings initialization with default values."""
        settings = SecretSettings(secrets_path=AsyncPath("/tmp/secrets"))

        # SecretSettings inherits from SecretBaseSettings which only requires secrets_path
        assert settings.secrets_path == AsyncPath("/tmp/secrets")


class TestSecretManager:
    """Test Google Secret Manager adapter."""

    @pytest.fixture
    def mock_secret_settings(self, mock_config):
        """Mock secret settings for testing."""
        mock_config.secret = SecretSettings(secrets_path=AsyncPath("/tmp/test"))
        return mock_config

    @pytest.fixture
    def mock_gcp_client(self):
        """Mock Google Cloud Secret Manager client."""
        client = AsyncMock()

        # Mock client methods
        client.list_secrets = AsyncMock()
        client.access_secret_version = AsyncMock()
        client.create_secret = AsyncMock()
        client.add_secret_version = AsyncMock()
        client.delete_secret = AsyncMock()
        client.list_secret_versions = AsyncMock()
        client.secret_path = MagicMock()

        return client

    def test_init(self, mock_secret_settings):
        """Test adapter initialization."""
        secret = Secret()
        secret.config = mock_secret_settings

        # Set project manually since it's a class attribute
        secret.project = "test-project"
        secret.parent = f"projects/{secret.project}"

        assert secret.project == "test-project"
        assert secret.parent == "projects/test-project"

    def test_extract_secret_name(self, mock_secret_settings):
        """Test secret name extraction."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"

        result = secret.extract_secret_name(
            "projects/test-project/secrets/acb_test_secret"
        )
        assert result == "test_secret"

        result = secret.extract_secret_name("acb_another_secret")
        assert result == "another_secret"

    async def test_list_secrets(self, mock_secret_settings):
        """Test listing secrets."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.project = "test-project"
        secret.parent = "projects/test-project"

        # Mock secret objects
        mock_secret1 = MagicMock()
        mock_secret1.name = "projects/test-project/secrets/acb_secret1"
        mock_secret2 = MagicMock()
        mock_secret2.name = "projects/test-project/secrets/acb_secret2"
        mock_secret3 = MagicMock()
        mock_secret3.name = "projects/test-project/secrets/other_secret"

        # Create async iterator
        async def async_iter():
            for secret_obj in [mock_secret1, mock_secret2, mock_secret3]:
                yield secret_obj

        mock_client = AsyncMock()
        mock_client.list_secrets.return_value = async_iter()

        with patch.object(secret, "client", mock_client):
            result = await secret.list()

            # Import the required class for assertion
            mock_client.list_secrets.assert_called_once()
            call_args = mock_client.list_secrets.call_args
            assert call_args.kwargs["request"].parent == "projects/test-project"
            assert call_args.kwargs["request"].filter == "acb_"

            assert result == ["secret1", "secret2"]

    async def test_list_secrets_with_adapter_filter(self, mock_secret_settings):
        """Test listing secrets with adapter filter."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.prefix = "acb_"
        secret.project = "test-project"
        secret.parent = "projects/test-project"

        mock_secret1 = MagicMock()
        mock_secret1.name = "projects/test-project/secrets/acb_cache_secret1"
        mock_secret2 = MagicMock()
        mock_secret2.name = "projects/test-project/secrets/acb_sql_secret2"

        async def async_iter():
            for secret_obj in [mock_secret1, mock_secret2]:
                yield secret_obj

        mock_client = AsyncMock()
        mock_client.list_secrets.return_value = async_iter()

        with patch.object(secret, "client", mock_client):
            result = await secret.list("cache")

            mock_client.list_secrets.assert_called_once()
            call_args = mock_client.list_secrets.call_args
            assert call_args.kwargs["request"].filter == "acb_cache_"

            assert result == ["secret1"]

    async def test_list_secrets_permission_denied(self, mock_secret_settings):
        """Test listing secrets with permission denied error."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.project = "test-project"
        secret.parent = "projects/test-project"

        mock_client = AsyncMock()
        mock_client.list_secrets.side_effect = PermissionDenied("Access denied")

        with patch.object(secret, "client", mock_client):
            with pytest.raises(SystemExit):
                await secret.list()

    async def test_get_secret(self, mock_secret_settings):
        """Test getting a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()
        secret.project = "test-project"

        # Mock response
        mock_payload = MagicMock()
        mock_payload.data = b"test-secret-value"
        mock_response = MagicMock()
        mock_response.payload = mock_payload

        mock_client = AsyncMock()
        mock_client.access_secret_version.return_value = mock_response

        with patch.object(secret, "client", mock_client):
            result = await secret.get("test_secret")

            mock_client.access_secret_version.assert_called_once()
            call_args = mock_client.access_secret_version.call_args
            assert (
                call_args.kwargs["request"].name
                == "projects/test-project/secrets/test_secret/versions/latest"
            )

            assert result == "test-secret-value"
            secret.logger.info.assert_called_once_with("Fetched secret - test_secret")

    async def test_get_secret_with_version(self, mock_secret_settings):
        """Test getting a secret with specific version."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()
        secret.project = "test-project"

        mock_payload = MagicMock()
        mock_payload.data = b"test-secret-value-v2"
        mock_response = MagicMock()
        mock_response.payload = mock_payload

        mock_client = AsyncMock()
        mock_client.access_secret_version.return_value = mock_response

        with patch.object(secret, "client", mock_client):
            result = await secret.get("test_secret", version="2")

            call_args = mock_client.access_secret_version.call_args
            assert (
                call_args.kwargs["request"].name
                == "projects/test-project/secrets/test_secret/versions/2"
            )

            assert result == "test-secret-value-v2"

    async def test_create_secret(self, mock_secret_settings):
        """Test creating a new secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()
        secret.project = "test-project"
        secret.parent = "projects/test-project"

        mock_secret_obj = MagicMock()
        mock_secret_obj.name = "projects/test-project/secrets/new_secret"

        mock_client = AsyncMock()
        mock_client.create_secret.return_value = mock_secret_obj
        mock_client.add_secret_version.return_value = None

        with patch.object(secret, "client", mock_client):
            await secret.create("new_secret", "new-secret-value")

            # Verify create_secret was called
            mock_client.create_secret.assert_called_once()
            create_call_args = mock_client.create_secret.call_args
            assert create_call_args.kwargs["request"].parent == "projects/test-project"
            assert create_call_args.kwargs["request"].secret_id == "new_secret"

            # Verify add_secret_version was called
            mock_client.add_secret_version.assert_called_once()
            add_call_args = mock_client.add_secret_version.call_args
            assert add_call_args.kwargs["request"].parent == mock_secret_obj.name
            assert (
                add_call_args.kwargs["request"].payload["data"] == b"new-secret-value"
            )

            secret.logger.debug.assert_called_once_with("Created secret - new_secret")

    async def test_create_secret_already_exists(self, mock_secret_settings):
        """Test creating a secret that already exists (should be suppressed)."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()
        secret.project = "test-project"
        secret.parent = "projects/test-project"

        mock_client = AsyncMock()
        mock_client.create_secret.side_effect = AlreadyExists("Secret already exists")

        with patch.object(secret, "client", mock_client):
            # Should not raise exception due to suppress()
            await secret.create("existing_secret", "value")

            mock_client.create_secret.assert_called_once()
            # add_secret_version should not be called since create failed
            mock_client.add_secret_version.assert_not_called()

    async def test_update_secret(self, mock_secret_settings):
        """Test updating an existing secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()
        secret.project = "test-project"

        mock_client = AsyncMock()
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/existing_secret"
        )
        mock_client.add_secret_version.return_value = None

        with patch.object(secret, "client", mock_client):
            await secret.update("existing_secret", "updated-value")

            mock_client.secret_path.assert_called_once_with(
                "test-project", "existing_secret"
            )

            mock_client.add_secret_version.assert_called_once()
            call_args = mock_client.add_secret_version.call_args
            assert (
                call_args.kwargs["request"].parent
                == "projects/test-project/secrets/existing_secret"
            )
            assert call_args.kwargs["request"].payload["data"] == b"updated-value"

            secret.logger.debug.assert_called_once_with(
                "Updated secret - existing_secret"
            )

    async def test_set_secret_exists(self, mock_secret_settings):
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

    async def test_set_secret_new(self, mock_secret_settings):
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

    async def test_exists_true(self, mock_secret_settings):
        """Test checking if secret exists (returns True)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", return_value="secret-value"):
            result = await secret.exists("test_secret")
            assert result is True

    async def test_exists_false(self, mock_secret_settings):
        """Test checking if secret exists (returns False)."""
        secret = Secret()
        secret.config = mock_secret_settings

        with patch.object(secret, "get", side_effect=Exception("Not found")):
            result = await secret.exists("test_secret")
            assert result is False

    async def test_delete_secret(self, mock_secret_settings):
        """Test deleting a secret."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()
        secret.project = "test-project"

        mock_client = AsyncMock()
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/test_secret"
        )
        mock_client.delete_secret.return_value = None

        with patch.object(secret, "client", mock_client):
            await secret.delete("test_secret")

            mock_client.secret_path.assert_called_once_with(
                "test-project", "test_secret"
            )

            mock_client.delete_secret.assert_called_once()
            call_args = mock_client.delete_secret.call_args
            assert (
                call_args.kwargs["request"].name
                == "projects/test-project/secrets/test_secret"
            )

            secret.logger.debug.assert_called_once_with(
                "Deleted secret - projects/test-project/secrets/test_secret"
            )

    async def test_list_versions(self, mock_secret_settings):
        """Test listing secret versions."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.project = "test-project"

        # Mock version objects
        mock_version1 = MagicMock()
        mock_version1.name = "projects/test-project/secrets/test_secret/versions/1"
        mock_version2 = MagicMock()
        mock_version2.name = "projects/test-project/secrets/test_secret/versions/2"
        mock_version3 = MagicMock()
        mock_version3.name = "projects/test-project/secrets/test_secret/versions/latest"

        async def async_iter():
            for version in [mock_version1, mock_version2, mock_version3]:
                yield version

        mock_client = AsyncMock()
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/test_secret"
        )
        mock_client.list_secret_versions.return_value = async_iter()

        with patch.object(secret, "client", mock_client):
            result = await secret.list_versions("test_secret")

            mock_client.secret_path.assert_called_once_with(
                "test-project", "test_secret"
            )

            mock_client.list_secret_versions.assert_called_once()
            call_args = mock_client.list_secret_versions.call_args
            assert (
                call_args.kwargs["request"].parent
                == "projects/test-project/secrets/test_secret"
            )

            assert result == ["1", "2", "latest"]

    @patch("acb.adapters.secret.secret_manager.SecretManagerServiceAsyncClient")
    def test_client_property(self, mock_client_class, mock_secret_settings):
        """Test client property initialization."""
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        secret = Secret()
        secret.config = mock_secret_settings

        client = secret.client

        mock_client_class.assert_called_once()
        assert client == mock_client_instance

        # Second access should return cached client
        client2 = secret.client
        assert client == client2
        assert mock_client_class.call_count == 1

    async def test_init_method(self, mock_secret_settings):
        """Test init method (NoReturn)."""
        secret = Secret()
        secret.config = mock_secret_settings

        # init method should return None and not raise
        result = await secret.init()
        assert result is None

    async def test_error_handling_in_operations(self, mock_secret_settings):
        """Test error handling in various operations."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.project = "test-project"

        mock_client = AsyncMock()

        # Test error in get operation
        mock_client.access_secret_version.side_effect = Exception("Access failed")

        with patch.object(secret, "client", mock_client):
            with pytest.raises(Exception, match="Access failed"):
                await secret.get("test_secret")

        # Test error in create operation
        mock_client.create_secret.side_effect = Exception("Create failed")

        with patch.object(secret, "client", mock_client):
            with pytest.raises(Exception, match="Create failed"):
                await secret.create("test_secret", "value")

        # Test error in delete operation
        mock_client.delete_secret.side_effect = Exception("Delete failed")

        with patch.object(secret, "client", mock_client):
            with pytest.raises(Exception, match="Delete failed"):
                await secret.delete("test_secret")

    async def test_comprehensive_workflow(self, mock_secret_settings):
        """Test a comprehensive workflow with multiple operations."""
        secret = Secret()
        secret.config = mock_secret_settings
        secret.logger = MagicMock()
        secret.project = "test-project"

        # Mock the client and its methods
        mock_client = AsyncMock()

        # Setup create workflow
        mock_secret_obj = MagicMock()
        mock_secret_obj.name = "projects/test-project/secrets/workflow_secret"
        mock_client.create_secret.return_value = mock_secret_obj
        mock_client.add_secret_version.return_value = None

        # Setup get workflow
        mock_payload = MagicMock()
        mock_payload.data = b"workflow-value"
        mock_response = MagicMock()
        mock_response.payload = mock_payload
        mock_client.access_secret_version.return_value = mock_response

        # Setup list versions workflow
        mock_version = MagicMock()
        mock_version.name = "projects/test-project/secrets/workflow_secret/versions/1"

        async def version_iter():
            yield mock_version

        mock_client.list_secret_versions.return_value = version_iter()
        mock_client.secret_path.return_value = (
            "projects/test-project/secrets/workflow_secret"
        )
        mock_client.delete_secret.return_value = None

        with patch.object(secret, "client", mock_client):
            # Create secret
            await secret.create("workflow_secret", "workflow-value")

            # Get secret
            value = await secret.get("workflow_secret")
            assert value == "workflow-value"

            # List versions
            versions = await secret.list_versions("workflow_secret")
            assert versions == ["1"]

            # Update secret
            await secret.update("workflow_secret", "updated-value")

            # Delete secret
            await secret.delete("workflow_secret")

            # Verify all operations were called
            mock_client.create_secret.assert_called_once()
            mock_client.access_secret_version.assert_called_once()
            mock_client.list_secret_versions.assert_called_once()
            assert mock_client.add_secret_version.call_count == 2  # create + update
            mock_client.delete_secret.assert_called_once()

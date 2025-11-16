"""Tests for Mailgun SMTP adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from acb.adapters.smtp.mailgun import Smtp, SmtpSettings


class TestMailgunSmtpSettings:
    """Test Mailgun SMTP settings."""

    def test_init_with_defaults(self, mock_config):
        """Test settings initialization with default values."""
        settings = SmtpSettings()

        # In testing mode, these values are set automatically
        assert settings.api_key.get_secret_value() == "test-api-key"
        assert settings.password.get_secret_value() == "test-password"
        assert settings.api_url == "https://api.mailgun.net/v3/domains"
        assert settings.mx_servers == ["smtp.mailgun.com"]

    def test_init_with_custom_values(self, mock_config):
        """Test settings initialization with custom values."""
        settings = SmtpSettings(
            api_key=SecretStr("custom_api_key"),
            password=SecretStr("custom_password"),
        )

        assert settings.api_key.get_secret_value() == "custom_api_key"
        assert settings.password.get_secret_value() == "custom_password"


class TestMailgunSmtp:
    """Test Mailgun SMTP adapter."""

    @pytest.fixture
    def mock_smtp_settings(self, mock_config):
        """Mock SMTP settings for testing."""
        mock_config.smtp = SmtpSettings()
        mock_config.app.domain = "example.com"
        return mock_config

    @pytest.fixture
    def mock_requests(self):
        """Mock requests adapter."""
        requests = AsyncMock()
        requests.get.return_value = MagicMock(
            json=MagicMock(return_value='{"items": []}')
        )
        requests.post.return_value = MagicMock(
            json=MagicMock(return_value='{"message": "success"}')
        )
        requests.put.return_value = MagicMock(
            json=MagicMock(return_value='{"message": "success"}')
        )
        requests.delete.return_value = MagicMock(
            json=MagicMock(return_value='{"message": "success"}')
        )
        return requests

    async def test_get_response_get(self, mock_smtp_settings, mock_requests):
        """Test GET request."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        with patch("acb.actions.encode.load.json", return_value={"items": []}):
            result = await smtp.get_response("get", "example.com")

        assert result == {"items": []}
        mock_requests.get.assert_called_once()

    async def test_get_response_post(self, mock_smtp_settings, mock_requests):
        """Test POST request."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        with patch("acb.actions.encode.load.json", return_value={"message": "success"}):
            result = await smtp.get_response("post", "example.com", {"test": "data"})

        assert result == {"message": "success"}
        mock_requests.post.assert_called_once()

    async def test_get_response_put(self, mock_smtp_settings, mock_requests):
        """Test PUT request."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        with patch("acb.actions.encode.load.json", return_value={"message": "success"}):
            result = await smtp.get_response("put", "example.com", {"test": "data"})

        assert result == {"message": "success"}
        mock_requests.put.assert_called_once()

    async def test_get_response_delete(self, mock_smtp_settings, mock_requests):
        """Test DELETE request."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        with patch("acb.actions.encode.load.json", return_value={"message": "success"}):
            result = await smtp.get_response("delete", "example.com")

        assert result == {"message": "success"}
        mock_requests.delete.assert_called_once()

    async def test_get_response_invalid_method(self, mock_smtp_settings, mock_requests):
        """Test invalid HTTP method raises ValueError."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        with pytest.raises(ValueError):
            await smtp.get_response("invalid", "example.com")

    async def test_list_domains(self, mock_smtp_settings, mock_requests):
        """Test domain listing."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        with patch.object(
            smtp,
            "get_response",
            return_value={"items": [{"name": "domain1.com"}, {"name": "domain2.com"}]},
        ):
            domains = await smtp.list_domains()

        assert domains == ["domain1.com", "domain2.com"]

    async def test_list_domains_empty(self, mock_smtp_settings, mock_requests):
        """Test domain listing when no domains exist."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        with patch.object(smtp, "get_response", return_value={"items": []}):
            domains = await smtp.list_domains()

        assert domains == []

    async def test_get_domain(self, mock_smtp_settings, mock_requests):
        """Test getting domain information."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        expected_domain_info = {"name": "example.com", "state": "active"}
        with patch.object(smtp, "get_response", return_value=expected_domain_info):
            result = await smtp.get_domain("example.com")

        assert result == expected_domain_info

    async def test_create_domain(self, mock_smtp_settings, mock_requests):
        """Test domain creation."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests
        smtp.logger = MagicMock()

        post_response = {"message": "Domain created"}
        put_response = {"message": "Domain configured"}

        with patch.object(
            smtp, "get_response", side_effect=[post_response, put_response]
        ):
            result = await smtp.create_domain("example.com")

        assert result == put_response
        smtp.logger.debug.assert_called_once_with(post_response)

    async def test_delete_domain(self, mock_smtp_settings, mock_requests):
        """Test domain deletion."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        expected_response = {"message": "Domain deleted"}
        with patch.object(smtp, "get_response", return_value=expected_response):
            result = await smtp.delete_domain("example.com")

        assert result == expected_response

    async def test_create_domain_credentials(self, mock_smtp_settings, mock_requests):
        """Test domain credentials creation."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        expected_response = {"message": "Credentials created"}
        with patch.object(smtp, "get_response", return_value=expected_response):
            result = await smtp.create_domain_credentials("example.com")

        assert result == expected_response

    async def test_get_dns_records(self, mock_smtp_settings, mock_requests):
        """Test DNS records retrieval."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests

        domain_info = {
            "receiving_dns_records": [{"priority": "10", "value": "mx.mailgun.org"}],
            "sending_dns_records": [
                {
                    "name": "example.com",
                    "record_type": "TXT",
                    "value": "v=spf1 include:mailgun.org ~all",
                }
            ],
        }

        with patch.object(smtp, "get_domain", return_value=domain_info):
            records = await smtp.get_dns_records("example.com")

        assert len(records) == 2  # MX + TXT records
        mx_record = records[0]
        assert mx_record.name == "example.com"
        assert mx_record.type == "MX"

    async def test_list_routes(self, mock_smtp_settings, mock_requests):
        """Test listing routes."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests
        smtp.logger = MagicMock()

        routes_response = {
            "items": [
                {
                    "id": "1",
                    "expression": "match_recipient('test@example.com')",
                    "description": "test route",
                },
                {
                    "id": "2",
                    "expression": "match_recipient('admin@other.com')",
                    "description": "other route",
                },
            ]
        }

        with patch.object(smtp, "get_response", return_value=routes_response):
            routes = await smtp.list_routes()

        # Should only return routes matching our domain
        expected_routes = [
            route
            for route in routes_response["items"]
            if "example.com" in route["expression"]
        ]
        assert routes == expected_routes

    async def test_delete_route(self, mock_smtp_settings, mock_requests):
        """Test route deletion."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests
        smtp.logger = MagicMock()

        route = {"id": "route123", "description": "test route"}
        mock_response = MagicMock()
        mock_requests.delete.return_value = mock_response

        result = await smtp.delete_route(route)

        assert result == mock_response
        smtp.logger.info.assert_called_once_with("Deleted route for test route")

    async def test_get_name(self, mock_smtp_settings):
        """Test name extraction from email address."""
        result = Smtp.get_name("'testuser@example.com'")
        assert result == "testuser"

    async def test_get_name_no_match(self, mock_smtp_settings):
        """Test name extraction with no match."""
        result = Smtp.get_name("invalid_format")
        assert result == ""

    async def test_create_route(self, mock_smtp_settings, mock_requests):
        """Test route creation."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests
        smtp.logger = MagicMock()

        # Mock list_routes to return empty list (no existing routes)
        with patch.object(smtp, "list_routes", return_value=[]):
            with patch.object(
                smtp, "get_response", return_value={"message": "Route created"}
            ):
                result = await smtp.create_route("admin", "admin@company.com")

        assert result == {"message": "Route created"}
        smtp.logger.info.assert_called_once()

    async def test_create_route_single_address(self, mock_smtp_settings, mock_requests):
        """Test route creation with single forwarding address."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests
        smtp.logger = MagicMock()

        with patch.object(smtp, "list_routes", return_value=[]):
            with patch.object(
                smtp, "get_response", return_value={"message": "Route created"}
            ):
                result = await smtp.create_route("info", "info@company.com")

        assert result == {"message": "Route created"}

    async def test_create_route_multiple_addresses(
        self, mock_smtp_settings, mock_requests
    ):
        """Test route creation with multiple forwarding addresses."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests
        smtp.logger = MagicMock()

        forwarding_addresses = ["admin@company.com", "backup@company.com"]

        with patch.object(smtp, "list_routes", return_value=[]):
            with patch.object(
                smtp, "get_response", return_value={"message": "Route created"}
            ):
                result = await smtp.create_route("support", forwarding_addresses)

        assert result == {"message": "Route created"}

    async def test_create_route_existing_route_conflict(
        self, mock_smtp_settings, mock_requests
    ):
        """Test route creation when conflicting route exists."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.requests = mock_requests
        smtp.logger = MagicMock()

        existing_route = {
            "id": "existing123",
            "expression": "match_recipient('admin@example.com')",
            "actions": ["forward('old@company.com')", "stop(self)"],
        }

        with patch.object(smtp, "list_routes", return_value=[existing_route]):
            with patch.object(smtp, "delete_route") as mock_delete:
                with patch.object(
                    smtp, "get_response", return_value={"message": "Route created"}
                ):
                    result = await smtp.create_route("admin", "new@company.com")

        mock_delete.assert_called_once_with(existing_route)
        assert result == {"message": "Route created"}

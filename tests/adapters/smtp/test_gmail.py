"""Tests for Gmail SMTP adapter."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from acb.adapters.smtp.gmail import Smtp, SmtpSettings


class TestGmailSmtpSettings:
    """Test Gmail SMTP settings."""

    def test_init_with_defaults(self, mock_config):
        """Test settings initialization with default values."""
        settings = SmtpSettings()

        # In testing mode, these values are set automatically
        assert settings.client_id == "test-client-id"
        assert settings.client_secret.get_secret_value() == "test-client-secret"
        assert settings.refresh_token.get_secret_value() == "test-refresh-token"
        assert settings.token_uri == "https://oauth2.googleapis.com/token"
        assert "https://www.googleapis.com/auth/gmail.send" in settings.scopes
        assert len(settings.mx_servers) == 5
        assert "aspmx.l.google.com." in settings.mx_servers[0]

    def test_init_with_custom_values(self, mock_config):
        """Test settings initialization with custom values."""
        settings = SmtpSettings(
            client_id="custom_client_id",
            client_secret=SecretStr("custom_secret"),
            refresh_token=SecretStr("custom_token"),
        )

        assert settings.client_id == "custom_client_id"
        assert settings.client_secret.get_secret_value() == "custom_secret"
        assert settings.refresh_token.get_secret_value() == "custom_token"


class TestGmailSmtp:
    """Test Gmail SMTP adapter."""

    @pytest.fixture
    def mock_smtp_settings(self, mock_config):
        """Mock SMTP settings for testing."""
        mock_config.smtp = SmtpSettings()
        return mock_config

    @patch("acb.adapters.smtp.gmail.build")
    @patch("acb.adapters.smtp.gmail.Credentials")
    async def test_get_gmail_service(
        self, mock_credentials, mock_build, mock_smtp_settings
    ):
        """Test Gmail service creation."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings

        service = smtp._get_gmail_service()

        mock_credentials.assert_called_once()
        mock_build.assert_called_once_with(
            "gmail", "v1", credentials=mock_credentials.return_value
        )
        assert service == mock_build.return_value

    async def test_get_response(self, mock_smtp_settings):
        """Test get_response method."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.logger = MagicMock()

        result = await smtp.get_response("POST", "example.com", {"test": "data"})

        assert result == {"message": "success", "status": "ok"}
        smtp.logger.debug.assert_called_once_with(
            "Gmail adapter: POST request for example.com"
        )

    async def test_list_domains(self, mock_smtp_settings):
        """Test domain listing."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.config.smtp.domain = "example.com"

        domains = await smtp.list_domains()

        assert domains == ["example.com"]

    async def test_list_domains_no_domain(self, mock_smtp_settings):
        """Test domain listing when no domain configured."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.config.smtp.domain = None

        domains = await smtp.list_domains()

        assert domains == []

    async def test_get_domain(self, mock_smtp_settings):
        """Test getting domain configuration."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings

        domain_config = await smtp.get_domain("example.com")

        assert domain_config["domain"] == "example.com"
        assert "receiving_dns_records" in domain_config
        assert "sending_dns_records" in domain_config
        assert len(domain_config["receiving_dns_records"]) == 5  # MX servers
        assert len(domain_config["sending_dns_records"]) == 2  # SPF and DMARC

    async def test_create_domain(self, mock_smtp_settings):
        """Test domain creation."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.logger = MagicMock()

        result = await smtp.create_domain("example.com")

        assert result["message"] == "Domain configured for Gmail"
        assert result["domain"] == "example.com"
        smtp.logger.info.assert_called_once_with(
            "Gmail adapter: Domain example.com configuration simulated"
        )

    async def test_delete_domain(self, mock_smtp_settings):
        """Test domain deletion."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.logger = MagicMock()

        result = await smtp.delete_domain("example.com")

        assert result["message"] == "Domain deletion simulated"
        assert result["domain"] == "example.com"
        smtp.logger.info.assert_called_once_with(
            "Gmail adapter: Domain example.com deletion simulated"
        )

    async def test_create_domain_credentials(self, mock_smtp_settings):
        """Test domain credentials creation."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings

        result = await smtp.create_domain_credentials("example.com")

        assert result["message"] == "Gmail uses OAuth authentication"

    async def test_update_domain_credentials(self, mock_smtp_settings):
        """Test domain credentials update."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings

        result = await smtp.update_domain_credentials("example.com")

        assert result["message"] == "Gmail uses OAuth authentication"

    async def test_get_dns_records(self, mock_smtp_settings):
        """Test DNS records retrieval."""
        smtp = Smtp()
        smtp.config = mock_smtp_settings

        records = await smtp.get_dns_records("example.com")

        assert len(records) == 3  # MX, SPF, DMARC
        mx_record = records[0]
        assert mx_record.name == "example.com"
        assert mx_record.type == "MX"

    @patch("acb.adapters.smtp.gmail.build")
    @patch("acb.adapters.smtp.gmail.Credentials")
    async def test_send_email_success(
        self, mock_credentials, mock_build, mock_smtp_settings
    ):
        """Test successful email sending."""
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "test_message_id"
        }
        mock_build.return_value = mock_service

        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.logger = MagicMock()

        result = await smtp.send_email(
            to="recipient@example.com", subject="Test Subject", body="Test body content"
        )

        assert result["id"] == "test_message_id"
        assert result["status"] == "sent"
        smtp.logger.info.assert_called_once_with(
            "Email sent to recipient@example.com, message ID: test_message_id"
        )

    @patch("acb.adapters.smtp.gmail.build")
    @patch("acb.adapters.smtp.gmail.Credentials")
    async def test_send_email_html(
        self, mock_credentials, mock_build, mock_smtp_settings
    ):
        """Test HTML email sending."""
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "test_message_id"
        }
        mock_build.return_value = mock_service

        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.logger = MagicMock()

        result = await smtp.send_email(
            to="recipient@example.com",
            subject="Test Subject",
            body="<h1>Test HTML</h1>",
            html=True,
        )

        assert result["id"] == "test_message_id"
        assert result["status"] == "sent"

    @patch("acb.adapters.smtp.gmail.build")
    @patch("acb.adapters.smtp.gmail.Credentials")
    async def test_send_email_failure(
        self, mock_credentials, mock_build, mock_smtp_settings
    ):
        """Test email sending failure."""
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b"Bad request"
        )
        mock_build.return_value = mock_service

        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.logger = MagicMock()

        result = await smtp.send_email(
            to="recipient@example.com", subject="Test Subject", body="Test body content"
        )

        assert result["status"] == "failed"
        assert "error" in result
        smtp.logger.exception.assert_called_once()

    async def test_get_name(self, mock_smtp_settings):
        """Test name extraction from email address."""
        result = Smtp.get_name("'testuser@example.com'")
        assert result == "testuser"

    async def test_get_name_no_match(self, mock_smtp_settings):
        """Test name extraction with no match."""
        result = Smtp.get_name("invalid_format")
        assert result == ""

    @patch("acb.adapters.smtp.gmail.build")
    @patch("acb.adapters.smtp.gmail.Credentials")
    async def test_list_routes(self, mock_credentials, mock_build, mock_smtp_settings):
        """Test listing forwarding routes."""
        mock_service = MagicMock()
        mock_service.users.return_value.settings.return_value.forwardingAddresses.return_value.list.return_value.execute.return_value = {
            "forwardingAddresses": [{"forwardingEmail": "test@example.com"}]
        }
        mock_build.return_value = mock_service

        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.config.smtp.domain = "example.com"

        routes = await smtp.list_routes()

        assert len(routes) == 1
        assert routes[0]["id"] == "test@example.com"

    @patch("acb.adapters.smtp.gmail.build")
    @patch("acb.adapters.smtp.gmail.Credentials")
    async def test_list_routes_error(
        self, mock_credentials, mock_build, mock_smtp_settings
    ):
        """Test listing routes with error."""
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_service.users.return_value.settings.return_value.forwardingAddresses.return_value.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b"Forbidden"
        )
        mock_build.return_value = mock_service

        smtp = Smtp()
        smtp.config = mock_smtp_settings
        smtp.logger = MagicMock()

        routes = await smtp.list_routes()

        assert routes == []
        smtp.logger.exception.assert_called_once()

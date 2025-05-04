from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response as HttpxResponse
from pydantic import SecretStr
from acb.adapters.dns._base import DnsRecord
from acb.adapters.smtp._base import SmtpBase, SmtpBaseSettings
from acb.adapters.smtp.gmail import Smtp as GmailSmtp
from acb.adapters.smtp.gmail import SmtpSettings as GmailSmtpSettings
from acb.adapters.smtp.mailgun import (
    Smtp as MailgunSmtp,
)
from acb.adapters.smtp.mailgun import (
    SmtpSettings as MailgunSmtpSettings,
)


class TestSmtpBaseSettings:
    def test_init(self) -> None:
        mock_config = MagicMock()
        mock_config.app = MagicMock()
        mock_config.app.domain = "example.com"
        mock_config.app.title = "Example App"

        settings = SmtpBaseSettings()

        settings.__init__(config=mock_config)

        assert settings.domain == "mail.example.com"
        assert settings.default_from == "info@example.com"
        assert settings.default_from_name == "Example App"
        assert settings.port == 587
        assert settings.tls
        assert not settings.ssl
        assert isinstance(settings.password, SecretStr)
        assert "admin" in settings.forwards
        assert settings.forwards["admin"] == "pat@example.com"

        settings = SmtpBaseSettings()

        settings.domain = "custom.example.com"
        settings.default_from = "custom@example.com"
        settings.default_from_name = "Custom App"
        settings.port = 465
        settings.tls = False
        settings.ssl = True
        settings.forwards = {"support": "support@example.com"}

        assert settings.domain == "custom.example.com"
        assert settings.default_from == "custom@example.com"
        assert settings.default_from_name == "Custom App"
        assert settings.port == 465
        assert not settings.tls
        assert settings.ssl
        assert settings.forwards["support"] == "support@example.com"


class MockSmtpBase(SmtpBase):
    def __init__(self) -> None:
        self.config = MagicMock()
        self.logger = MagicMock()
        self.initialized = False

    async def init(self) -> None:
        self.initialized = True


class TestSmtpBase:
    @pytest.fixture
    def smtp_base(self) -> MockSmtpBase:
        return MockSmtpBase()

    @pytest.mark.asyncio
    async def test_init(self, smtp_base: MockSmtpBase) -> None:
        await smtp_base.init()
        assert smtp_base.initialized


class TestMailgunSmtpSettings:
    def test_init(self) -> None:
        settings = MailgunSmtpSettings()

        settings.domain = "mail.example.com"
        settings.default_from = "info@example.com"
        settings.default_from_name = "Example App"
        settings.api_url = "https://api.mailgun.net/v3/domains"
        settings.mx_servers = ["smtp.mailgun.com"]
        settings.api_key = SecretStr("test-api-key")
        settings.password = SecretStr("test-password")

        assert settings.domain == "mail.example.com"
        assert settings.default_from == "info@example.com"
        assert settings.default_from_name == "Example App"
        assert settings.api_url == "https://api.mailgun.net/v3/domains"
        assert settings.mx_servers == ["smtp.mailgun.com"]
        assert settings.api_key.get_secret_value() == "test-api-key"
        assert settings.password.get_secret_value() == "test-password"


class TestMailgunSmtp:
    @pytest.fixture
    def smtp(self) -> MailgunSmtp:
        instance = MailgunSmtp()
        instance.config = MagicMock()
        instance.config.smtp = MagicMock()
        instance.config.smtp.api_url = "https://api.mailgun.net/v3/domains"
        instance.config.smtp.api_key = MagicMock()
        instance.config.smtp.api_key.get_secret_value.return_value = "test-api-key"
        instance.config.smtp.domain = "example.com"
        instance.config.app = MagicMock()
        instance.config.app.domain = "example.com"
        instance.config.smtp.forwards = {"admin": "admin@example.com"}
        instance.logger = MagicMock()
        instance.requests = MagicMock()
        return instance

    @pytest.mark.asyncio
    async def test_get_response_get(self, smtp: MailgunSmtp) -> None:
        mock_response = MagicMock(spec=HttpxResponse)
        mock_response.json.return_value = {"message": "success"}
        smtp.requests.get = AsyncMock(return_value=mock_response)

        with patch(
            "acb.adapters.smtp.mailgun.load.json",
            AsyncMock(return_value={"message": "success"}),
        ):
            result = await smtp.get_response(
                "get", domain="example.com", params={"limit": 10}
            )

            smtp.requests.get.assert_called_once()
            assert result == {"message": "success"}

    @pytest.mark.asyncio
    async def test_get_response_put(self, smtp: MailgunSmtp) -> None:
        mock_response = MagicMock(spec=HttpxResponse)
        mock_response.json.return_value = {"message": "success"}
        smtp.requests.put = AsyncMock(return_value=mock_response)

        with (
            patch(
                "acb.adapters.smtp.mailgun.load.json",
                AsyncMock(return_value={"message": "success"}),
            ),
            patch("acb.adapters.smtp.mailgun.sys._getframe") as mock_frame,
        ):
            mock_frame.return_value.f_back.f_code.co_name = "test_domain"

            result = await smtp.get_response(
                "put", domain="example.com", data={"key": "value"}
            )

            smtp.requests.put.assert_called_once()
            assert result == {"message": "success"}

    @pytest.mark.asyncio
    async def test_list_domains(self, smtp: MailgunSmtp) -> None:
        with patch.object(smtp, "get_response", AsyncMock()) as mock_get_response:
            mock_get_response.return_value = {
                "items": [{"name": "example.com"}, {"name": "test.com"}]
            }

            domains = await smtp.list_domains()

            mock_get_response.assert_called_once_with(
                "get", params={"skip": 0, "limit": 1000}
            )
            assert domains == ["example.com", "test.com"]

    @pytest.mark.asyncio
    async def test_get_domain(self, smtp: MailgunSmtp) -> None:
        with patch.object(smtp, "get_response", AsyncMock()) as mock_get_response:
            mock_get_response.return_value = {
                "domain": "example.com",
                "state": "active",
            }

            domain_info = await smtp.get_domain("example.com")

            mock_get_response.assert_called_once_with("get", domain="example.com")
            assert domain_info == {"domain": "example.com", "state": "active"}

    @pytest.mark.asyncio
    async def test_create_domain(self, smtp: MailgunSmtp) -> None:
        with patch.object(smtp, "get_response", AsyncMock()) as mock_get_response:
            mock_get_response.side_effect = [
                {"message": "Domain created"},
                {"message": "Connection updated"},
            ]

            result = await smtp.create_domain("example.com")

            assert mock_get_response.call_count == 2
            assert result == {"message": "Connection updated"}

    @pytest.mark.asyncio
    async def test_delete_domain(self, smtp: MailgunSmtp) -> None:
        with patch.object(smtp, "get_response", AsyncMock()) as mock_get_response:
            mock_get_response.return_value = {"message": "Domain deleted"}

            result = await smtp.delete_domain("example.com")

            mock_get_response.assert_called_once_with("delete", domain="example.com")
            assert result == {"message": "Domain deleted"}

    @pytest.mark.asyncio
    async def test_get_dns_records(self, smtp: MailgunSmtp) -> None:
        with (
            patch.object(smtp, "get_domain", AsyncMock()) as mock_get_domain,
            patch("acb.adapters.smtp.mailgun.debug") as mock_debug,
        ):
            mock_get_domain.return_value = {
                "receiving_dns_records": [
                    {"priority": "10", "value": "mx.example.com"}
                ],
                "sending_dns_records": [
                    {"name": "example.com", "record_type": "TXT", "value": "v=spf1"}
                ],
            }

            records = await smtp.get_dns_records("example.com")

            mock_get_domain.assert_called_once_with("example.com")
            assert len(records) == 2
            assert records[0].type == "MX"
            assert records[1].type == "TXT"
            mock_debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_dns_records(self, smtp: MailgunSmtp) -> None:
        mock_dns = AsyncMock()

        with (
            patch.object(smtp, "create_domain", AsyncMock()) as mock_create_domain,
            patch.object(
                smtp, "create_domain_credentials", AsyncMock()
            ) as mock_create_creds,
            patch.object(smtp, "get_dns_records", AsyncMock()) as mock_get_records,
            patch.object(smtp, "delete_domain", AsyncMock()) as mock_delete_domain,
        ):
            mock_records = [MagicMock(spec=DnsRecord), MagicMock(spec=DnsRecord)]
            mock_get_records.return_value = mock_records
            smtp.config.mail.mailgun.gmail.enabled = False

            await smtp.create_dns_records(dns=mock_dns)

            mock_create_domain.assert_called_once_with(smtp.config.smtp.domain)
            mock_create_creds.assert_called_once_with(smtp.config.smtp.domain)
            mock_get_records.assert_called_once_with(smtp.config.smtp.domain)
            mock_delete_domain.assert_called_once_with(smtp.config.smtp.domain)
            mock_dns.create_records.assert_called_once_with(mock_records)

    @pytest.mark.asyncio
    async def test_create_route(self, smtp: MailgunSmtp) -> None:
        with (
            patch.object(smtp, "list_routes", AsyncMock()) as mock_list_routes,
            patch.object(smtp, "get_response", AsyncMock()) as mock_get_response,
        ):
            mock_list_routes.return_value = []
            mock_get_response.return_value = {"message": "Route created"}

            result = await smtp.create_route("admin", "admin@example.com")

            mock_list_routes.assert_called_once()
            mock_get_response.assert_called_once()
            assert result == {"message": "Route created"}
            smtp.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_init(self, smtp: MailgunSmtp) -> None:
        with (
            patch.object(smtp, "create_dns_records", AsyncMock()) as mock_create_dns,
            patch.object(smtp, "delete_routes", AsyncMock()) as mock_delete_routes,
            patch.object(smtp, "create_routes", AsyncMock()) as mock_create_routes,
        ):
            await smtp.init()

            mock_create_dns.assert_called_once()
            mock_delete_routes.assert_called_once()
            mock_create_routes.assert_called_once()


class TestGmailSmtpSettings:
    def test_init(self) -> None:
        settings = GmailSmtpSettings()

        settings.domain = "mail.example.com"
        settings.default_from = "info@example.com"
        settings.default_from_name = "Example App"
        settings.token_uri = "https://oauth2.googleapis.com/token"
        settings.mx_servers = [
            "1 aspmx.l.google.com.",
            "2 alt1.aspmx.l.google.com.",
            "3 alt2.aspmx.l.google.com.",
            "4 alt3.aspmx.l.google.com.",
            "5 alt4.aspmx.l.google.com.",
        ]

        assert settings.domain == "mail.example.com"
        assert settings.default_from == "info@example.com"
        assert settings.default_from_name == "Example App"
        assert settings.token_uri == "https://oauth2.googleapis.com/token"
        assert "https://www.googleapis.com/auth/gmail.send" in settings.scopes
        assert settings.mx_servers is not None and len(settings.mx_servers) == 5
        assert (
            settings.mx_servers is not None
            and "1 aspmx.l.google.com." in settings.mx_servers
        )

        settings = GmailSmtpSettings()
        settings.client_id = "test-client-id"
        settings.client_secret = SecretStr("test-client-secret")
        settings.refresh_token = SecretStr("test-refresh-token")

        assert settings.client_id == "test-client-id"
        assert settings.client_secret.get_secret_value() == "test-client-secret"
        assert settings.refresh_token.get_secret_value() == "test-refresh-token"


class TestGmailSmtp:
    @pytest.fixture
    def smtp(self) -> GmailSmtp:
        instance = GmailSmtp()
        instance.config = MagicMock()
        instance.config.smtp = MagicMock()
        instance.config.smtp.domain = "example.com"
        instance.config.smtp.default_from = "info@example.com"
        instance.config.smtp.default_from_name = "Example App"
        instance.config.smtp.client_id = "test-client-id"
        instance.config.smtp.client_secret = MagicMock()
        instance.config.smtp.client_secret.get_secret_value.return_value = (
            "test-client-secret"
        )
        instance.config.smtp.refresh_token = MagicMock()
        instance.config.smtp.refresh_token.get_secret_value.return_value = (
            "test-refresh-token"
        )
        instance.config.smtp.token_uri = "https://oauth2.googleapis.com/token"
        instance.config.smtp.scopes = ["https://www.googleapis.com/auth/gmail.send"]
        instance.config.smtp.mx_servers = [
            "1 aspmx.l.google.com.",
            "5 alt1.aspmx.l.google.com.",
        ]
        instance.config.smtp.forwards = {"admin": "admin@example.com"}
        instance.logger = MagicMock()
        instance.requests = MagicMock()
        return instance

    def test_get_gmail_service(self, smtp: GmailSmtp) -> None:
        with (
            patch("acb.adapters.smtp.gmail.Credentials") as mock_credentials,
            patch("acb.adapters.smtp.gmail.build") as mock_build,
        ):
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            service = smtp._get_gmail_service()

            mock_credentials.assert_called_once_with(
                None,
                refresh_token="test-refresh-token",
                token_uri="https://oauth2.googleapis.com/token",
                client_id="test-client-id",
                client_secret="test-client-secret",
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            )
            mock_build.assert_called_once_with(
                "gmail", "v1", credentials=mock_credentials.return_value
            )
            assert service == mock_service

    @pytest.mark.asyncio
    async def test_get_response(self, smtp: GmailSmtp) -> None:
        result = await smtp.get_response("get", domain="example.com")

        smtp.logger.debug.assert_called_once()
        assert result["message"] == "success"
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_list_domains(self, smtp: GmailSmtp) -> None:
        domains = await smtp.list_domains()

        assert domains == ["example.com"]

    @pytest.mark.asyncio
    async def test_get_domain(self, smtp: GmailSmtp) -> None:
        domain_info = await smtp.get_domain("example.com")
        assert domain_info is not None and domain_info["domain"] == "example.com"
        assert (
            domain_info is not None and len(domain_info["receiving_dns_records"]) == 2
        )
        assert (
            domain_info is not None
            and domain_info["receiving_dns_records"][0]["priority"] == "1"
        )
        assert (
            domain_info is not None
            and domain_info["receiving_dns_records"][0]["value"]
            == "aspmx.l.google.com."
        )
        assert domain_info is not None and len(domain_info["sending_dns_records"]) == 2
        assert (
            domain_info is not None
            and "v=spf1" in domain_info["sending_dns_records"][0]["value"]
        )
        assert (
            domain_info is not None
            and "v=DMARC1" in domain_info["sending_dns_records"][1]["value"]
        )

    @pytest.mark.asyncio
    async def test_create_domain(self, smtp: GmailSmtp) -> None:
        result = await smtp.create_domain("example.com")

        smtp.logger.info.assert_called_once()
        assert result["message"] == "Domain configured for Gmail"
        assert result["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_delete_domain(self, smtp: GmailSmtp) -> None:
        result = await smtp.delete_domain("example.com")

        smtp.logger.info.assert_called_once()
        assert result["message"] == "Domain deletion simulated"
        assert result["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_get_dns_records(self, smtp: GmailSmtp) -> None:
        with patch("acb.adapters.smtp.gmail.debug") as mock_debug:
            records = await smtp.get_dns_records("example.com")

            assert len(records) == 3
            assert records[0].type == "MX"
            assert records[1].type == "TXT"
            assert records[2].type == "TXT"
            mock_debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_dns_records(self, smtp: GmailSmtp) -> None:
        mock_dns = AsyncMock()

        with patch.object(smtp, "get_dns_records", AsyncMock()) as mock_get_records:
            mock_records = [MagicMock(), MagicMock()]
            mock_get_records.return_value = mock_records

            await smtp.create_dns_records(dns=mock_dns)

            mock_get_records.assert_called_once_with("example.com")
            mock_dns.create_records.assert_called_once_with(mock_records)
            smtp.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_routes(self, smtp: GmailSmtp) -> None:
        with patch.object(smtp, "_get_gmail_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            mock_list = MagicMock()
            mock_service.users().settings().forwardingAddresses().list.return_value = (
                mock_list
            )
            mock_list.execute.return_value = {
                "forwardingAddresses": [{"forwardingEmail": "admin@example.com"}]
            }

            routes = await smtp.list_routes()

            assert len(routes) == 1
            assert routes[0]["id"] == "admin@example.com"
            assert "match_recipient" in routes[0]["expression"]
            assert "forward" in routes[0]["actions"][0]

    @pytest.mark.asyncio
    async def test_delete_route(self, smtp: GmailSmtp) -> None:
        with patch.object(smtp, "_get_gmail_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            mock_delete = MagicMock()
            mock_service.users().settings().forwardingAddresses().delete.return_value = mock_delete

            route = {"id": "admin@example.com", "description": "Admin route"}
            response = await smtp.delete_route(route)

            mock_service.users().settings().forwardingAddresses().delete.assert_called_once_with(
                userId="me", forwardingEmail="admin@example.com"
            )
            assert response.status_code == 200
            smtp.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_route(self, smtp: GmailSmtp) -> None:
        with patch.object(smtp, "_get_gmail_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            mock_create = MagicMock()
            mock_service.users().settings().forwardingAddresses().create.return_value = mock_create

            mock_update = MagicMock()
            mock_service.users().settings().updateAutoForwarding.return_value = (
                mock_update
            )

            result = await smtp.create_route("admin", "admin@example.com")

            mock_service.users().settings().forwardingAddresses().create.assert_called_once_with(
                userId="me", body={"forwardingEmail": "admin@example.com"}
            )
            mock_service.users().settings().updateAutoForwarding.assert_called_once()
            assert result["message"] == "Forwarding created"
            smtp.logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_send_email(self, smtp: GmailSmtp) -> None:
        with (
            patch.object(smtp, "_get_gmail_service") as mock_get_service,
            patch("acb.adapters.smtp.gmail.MIMEMultipart") as mock_mime_multipart,
            patch("acb.adapters.smtp.gmail.MIMEText") as mock_mime_text,
            patch("acb.adapters.smtp.gmail.base64") as mock_base64,
        ):
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            mock_message = MagicMock()
            mock_mime_multipart.return_value = mock_message

            mock_send = MagicMock()
            mock_service.users().messages().send.return_value = mock_send
            mock_send.execute.return_value = {"id": "message-id-123"}

            mock_base64.urlsafe_b64encode.return_value.decode.return_value = (
                "encoded-message"
            )

            result = await smtp.send_email(
                to="user@example.com",
                subject="Test Subject",
                body="Test Body",
            )

            mock_mime_multipart.assert_called_once_with("alternative")
            mock_message.__setitem__.assert_any_call("to", "user@example.com")
            mock_message.__setitem__.assert_any_call("subject", "Test Subject")
            mock_mime_text.assert_called_once_with("Test Body", "plain")
            mock_message.attach.assert_called_once_with(mock_mime_text.return_value)

            mock_service.users().messages().send.assert_called_once_with(
                userId="me", body={"raw": "encoded-message"}
            )

            assert result["id"] == "message-id-123"
            assert result["status"] == "sent"
            smtp.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_init(self, smtp: GmailSmtp) -> None:
        with (
            patch.object(smtp, "create_dns_records", AsyncMock()) as mock_create_dns,
            patch.object(smtp, "delete_routes", AsyncMock()) as mock_delete_routes,
            patch.object(smtp, "create_routes", AsyncMock()) as mock_create_routes,
        ):
            await smtp.init()

            mock_create_dns.assert_called_once()
            mock_delete_routes.assert_called_once()
            mock_create_routes.assert_called_once()

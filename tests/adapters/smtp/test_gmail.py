"""Tests for the Gmail SMTP adapter."""

import typing as t
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr
from acb.adapters.smtp.gmail import Smtp as GmailSmtp
from acb.adapters.smtp.gmail import SmtpSettings as GmailSmtpSettings


@pytest.fixture
def mock_async_context_manager() -> Callable[
    ..., AbstractAsyncContextManager[MagicMock]
]:
    @asynccontextmanager
    async def _async_context_manager(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[MagicMock]:
        yield MagicMock()

    return _async_context_manager


class TestGmailSmtpSettings:
    def test_init_basic(self) -> None:
        settings: GmailSmtpSettings = GmailSmtpSettings(
            name="gmail",
            domain="example.com",
            from_email="test@example.com",
            app_token="test_token",
            app_pwd="test_password",
            subdomain="mail",
        )
        assert settings.name == "gmail"  # type: ignore
        assert settings.domain == "example.com"
        assert settings.from_email == "test@example.com"  # type: ignore
        assert settings.app_token == "test_token"  # type: ignore
        assert settings.app_pwd == "test_password"  # type: ignore
        assert settings.subdomain == "mail"  # type: ignore

    def test_init_with_config(self) -> None:
        mock_config: MagicMock = MagicMock()
        mock_config.app.domain = "example.com"
        mock_config.app.title = "Example App"

        with patch("acb.depends.depends.__call__", return_value=mock_config):
            settings: GmailSmtpSettings = GmailSmtpSettings(
                domain="mail.example.com",
                subdomain="mail",
                default_from="info@example.com",
                default_from_name="Example App",
            )

            assert settings.domain == "mail.example.com"
            assert settings.default_from == "info@example.com"
            assert settings.default_from_name == "Example App"
            assert settings.token_uri == "https://oauth2.googleapis.com/token"
            assert "https://www.googleapis.com/auth/gmail.send" in settings.scopes
            assert settings.mx_servers is not None and len(settings.mx_servers) == 5
            assert "1 aspmx.l.google.com." in settings.mx_servers

        with patch("acb.depends.depends.__call__", return_value=mock_config):
            auth_settings: GmailSmtpSettings = GmailSmtpSettings(
                client_id="test-client-id",
                client_secret=SecretStr("test-client-secret"),
                refresh_token=SecretStr("test-refresh-token"),
                domain="mail.example.com",
                subdomain="mail",
                default_from="info@example.com",
                default_from_name="Example App",
            )
            assert auth_settings.client_id == "test-client-id"
            assert (
                auth_settings.client_secret.get_secret_value() == "test-client-secret"
            )
            assert (
                auth_settings.refresh_token.get_secret_value() == "test-refresh-token"
            )

    def test_validation(self) -> None:
        GmailSmtpSettings(
            name="gmail",
            domain="example.com",
            from_email="test@example.com",
            app_token="test_token",
            app_pwd="test_password",
        )


class TestGmailSmtp:
    @pytest.fixture
    def smtp(
        self,
        mock_async_context_manager: Callable[
            ..., AbstractAsyncContextManager[MagicMock]
        ],
    ) -> GmailSmtp:
        class TestableGmailSmtp(GmailSmtp):
            def __init__(self) -> None:
                super().__init__()
                self.connect = MagicMock()

        instance: GmailSmtp = TestableGmailSmtp()
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
        instance.config.smtp.scopes = ["https://www.googleapis.com/auth/gmail.send"]
        instance.config.smtp.mx_servers = [
            "1 aspmx.l.google.com.",
            "5 alt1.aspmx.l.google.com.",
        ]
        instance.config.smtp.forwards = {"admin": "admin@example.com"}
        instance.logger = MagicMock()
        instance.requests = MagicMock()

        if (
            not hasattr(instance, "_get_gmail_service")
            or instance._get_gmail_service is None
        ):
            instance._get_gmail_service = MagicMock(return_value=MagicMock())

        return instance

    async def test_get_gmail_service(self, smtp: GmailSmtp) -> None:
        def mock_get_gmail_service() -> t.Any:
            from acb.adapters.smtp.gmail import Credentials, build

            creds = Credentials(
                None,
                refresh_token="test-refresh-token",
                token_uri="https://oauth2.googleapis.com/token",
                client_id="test-client-id",
                client_secret="test-client-secret",
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            )
            service = build("gmail", "v1", credentials=creds)
            return service

        smtp._get_gmail_service = mock_get_gmail_service

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
        # Create mock logger
        mock_logger = MagicMock()
        smtp.logger = mock_logger

        result = await smtp.get_response("get", domain="example.com")

        mock_logger.debug.assert_called_once()
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
        # Create mock logger
        mock_logger = MagicMock()
        smtp.logger = mock_logger

        result = await smtp.create_domain("example.com")

        mock_logger.info.assert_called_once()
        assert result["message"] == "Domain configured for Gmail"
        assert result["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_delete_domain(self, smtp: GmailSmtp) -> None:
        # Create mock logger
        mock_logger = MagicMock()
        smtp.logger = mock_logger

        result = await smtp.delete_domain("example.com")

        mock_logger.info.assert_called_once()
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

            # Create mock logger
            mock_logger = MagicMock()
            smtp.logger = mock_logger

            await smtp.create_dns_records(dns=mock_dns)

            mock_get_records.assert_called_once_with("example.com")
            mock_dns.create_records.assert_called_once_with(mock_records)
            mock_logger.info.assert_called_once()

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
        # Create mock logger BEFORE calling the method
        mock_logger = MagicMock()
        smtp.logger = mock_logger

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
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_route(self, smtp: GmailSmtp) -> None:
        # Create mock logger BEFORE calling the method
        mock_logger = MagicMock()
        smtp.logger = mock_logger

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
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_send_email(self, smtp: GmailSmtp) -> None:
        # Create mock logger BEFORE calling the method
        mock_logger = MagicMock()
        smtp.logger = mock_logger

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
            mock_logger.info.assert_called_once()

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

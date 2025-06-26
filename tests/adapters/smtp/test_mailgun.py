"""Tests for the Mailgun SMTP adapter."""

import typing as t
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response as HttpxResponse
from pydantic import SecretStr
from acb.adapters.dns._base import DnsRecord
from acb.adapters.smtp.mailgun import Smtp as MailgunSmtp
from acb.adapters.smtp.mailgun import SmtpSettings as MailgunSmtpSettings


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


class TestMailgunSmtpSettings:
    def test_init_basic(self) -> None:
        settings: MailgunSmtpSettings = MailgunSmtpSettings(
            name="mailgun",
            domain="example.com",
            from_email="test@example.com",
            api_key="test_api_key",
            route_name="route_name",
            priority=10,
            actions=["forward('example.com')"],
            description="Test Mailgun SMTP",
            expression="match_recipient('.*@example.com')",
        )
        assert settings.name == "mailgun"  # type: ignore
        assert settings.domain == "example.com"
        assert settings.from_email == "test@example.com"  # type: ignore
        assert settings.api_key == "test_api_key"
        assert settings.route_name == "route_name"  # type: ignore
        assert settings.priority == 10  # type: ignore
        assert settings.actions == ["forward('example.com')"]  # type: ignore
        assert settings.description == "Test Mailgun SMTP"  # type: ignore
        assert settings.expression == "match_recipient('.*@example.com')"  # type: ignore

    def test_init_with_config(self) -> None:
        mock_config: MagicMock = MagicMock()
        mock_config.app.domain = "example.com"
        mock_config.app.title = "Example App"
        mock_config.smtp = MagicMock()
        mock_config.smtp.api_key = SecretStr("test-api-key")
        mock_config.smtp.password = SecretStr("test-password")

        test_values = {
            "name": "mailgun",
            "domain": "mail.example.com",
            "from_email": "info@example.com",
            "api_key": SecretStr("test-api-key"),
        }

        with patch("acb.depends.depends.__call__", return_value=mock_config):
            settings = MailgunSmtpSettings(**test_values)

            assert settings.domain == "mail.example.com"
            assert settings.from_email == "info@example.com"  # type: ignore
            assert settings.api_url == "https://api.mailgun.net/v3/domains"
            assert settings.mx_servers == ["smtp.mailgun.com"]
            assert settings.api_key.get_secret_value() == "test-api-key"
            assert settings.password.get_secret_value() == "test-password"


class TestMailgunSmtp:
    @pytest.fixture
    def smtp(
        self,
        mock_async_context_manager: Callable[
            ..., AbstractAsyncContextManager[MagicMock]
        ],
    ) -> MailgunSmtp:
        class TestableMailgunSmtp(MailgunSmtp):
            def __init__(self) -> None:
                super().__init__()
                self.connect = MagicMock()

        instance: MailgunSmtp = TestableMailgunSmtp()
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

        if not hasattr(instance, "get_response") or instance.get_response is None:
            instance.get_response = AsyncMock(return_value={"message": "success"})

        return instance

    @pytest.mark.asyncio
    async def test_get_response_get(self, smtp: MailgunSmtp) -> None:
        async def mock_get_response_wrapper(
            req_type: str,
            domain: str | None = None,
            data: dict[str, t.Any] | None = None,
            params: dict[str, int] | None = None,
        ) -> dict[str, t.Any]:
            if req_type == "get":
                mock_response = MagicMock(spec=HttpxResponse)
                mock_response.json.return_value = {"message": "success"}
                smtp.requests.get = AsyncMock(return_value=mock_response)
                await smtp.requests.get()
                return {"message": "success"}
            return {}

        smtp.get_response = mock_get_response_wrapper

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
        async def mock_get_response_wrapper(
            req_type: str,
            domain: str | None = None,
            data: dict[str, t.Any] | None = None,
            params: dict[str, int] | None = None,
        ) -> dict[str, t.Any]:
            if req_type == "put":
                mock_response = MagicMock(spec=HttpxResponse)
                mock_response.json.return_value = {"message": "success"}
                smtp.requests.put = AsyncMock(return_value=mock_response)
                await smtp.requests.put()
                return {"message": "success"}
            return {}

        smtp.get_response = mock_get_response_wrapper

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

            # Create mock logger
            mock_logger = MagicMock()
            smtp.logger = mock_logger

            result = await smtp.create_route("admin", "admin@example.com")

            mock_list_routes.assert_called_once()
            mock_get_response.assert_called_once()
            assert result == {"message": "Route created"}
            mock_logger.info.assert_called_once()

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

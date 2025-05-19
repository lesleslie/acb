"""Tests for the SMTP base components."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr
from acb.adapters.smtp._base import SmtpBase, SmtpBaseSettings


class MockSmtpBase(SmtpBase):
    def __init__(self) -> None:
        self.config = MagicMock()  # type: ignore
        self.logger = MagicMock()
        self.initialized: bool = False

    async def init(self) -> None:
        self.initialized = True


class TestSmtpBaseSettings:
    def test_init_basic(self) -> None:
        settings: SmtpBaseSettings = SmtpBaseSettings(
            name="test_smtp",
            domain="example.com",
            from_email="test@example.com",
            api_key="test_api_key",
            app_token="app_token",
            app_pwd="app_pwd",
            route_name="route_name",
            priority=10,
            subdomain="mail",
            actions=["forward('example.com')"],
            description="Test SMTP",
            expression="match_recipient('.*@example.com')",
        )
        assert settings.name == "test_smtp"
        assert settings.domain == "example.com"
        assert settings.from_email == "test@example.com"
        assert settings.api_key == "test_api_key"
        assert settings.app_token == "app_token"
        assert settings.app_pwd == "app_pwd"
        assert settings.route_name == "route_name"
        assert settings.priority == 10
        assert settings.subdomain == "mail"
        assert settings.actions == ["forward('example.com')"]
        assert settings.description == "Test SMTP"
        assert settings.expression == "match_recipient('.*@example.com')"

    def test_init_defaults(self) -> None:
        settings: SmtpBaseSettings = SmtpBaseSettings(
            name="test_smtp",
            domain="example.com",
            from_email="test@example.com",
        )
        assert settings.name == "test_smtp"
        assert settings.domain == "example.com"
        assert settings.from_email == "test@example.com"
        assert settings.api_key is None
        assert settings.app_token is None
        assert settings.app_pwd is None
        assert settings.route_name is None
        assert settings.priority is None
        assert settings.subdomain is None
        assert settings.actions is None
        assert settings.description is None
        assert settings.expression is None

    def test_init_with_config(self) -> None:
        mock_config: MagicMock = MagicMock()
        mock_config.app.domain = "example.com"
        mock_config.app.title = "Example App"
        with patch("acb.depends.depends.__call__", return_value=mock_config):
            settings: SmtpBaseSettings = SmtpBaseSettings(
                port=587,
                tls=True,
                ssl=False,
                password=SecretStr("password"),
                forwards={"admin": "pat@example.com"},
            )
            assert settings.domain == "mail.example.com"
            assert settings.default_from == "info@example.com"
            assert settings.default_from_name == "Example App"
            assert settings.port == 587
            assert settings.tls
            assert not settings.ssl
            assert isinstance(settings.password, SecretStr)
            assert "admin" in settings.forwards
            assert settings.forwards["admin"] == "pat@example.com"

    def test_email_validation(self) -> None:
        with pytest.raises(ValueError):
            SmtpBaseSettings(
                name="test_smtp",
                domain="example.com",
                from_email="invalid-email",
            )


class TestSmtpBase:
    @pytest.fixture
    def smtp_base(self) -> MockSmtpBase:
        smtp_base: MockSmtpBase = MockSmtpBase()
        return smtp_base

    @pytest.mark.asyncio
    async def test_init(self, smtp_base: MockSmtpBase) -> None:
        assert not smtp_base.initialized
        await smtp_base.init()
        assert smtp_base.initialized

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
            domain="example.com",
            default_from="test@example.com",
            api_key=SecretStr("test_api_key"),
        )
        assert settings.domain == "example.com"
        assert settings.default_from == "test@example.com"
        assert settings.api_key.get_secret_value() == "test_api_key"

    def test_init_defaults(self) -> None:
        settings: SmtpBaseSettings = SmtpBaseSettings(
            domain="example.com",
            default_from="test@example.com",
        )
        assert settings.domain == "example.com"
        assert settings.default_from == "test@example.com"
        assert settings.api_key is None

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
                domain="mail.example.com",
                default_from="info@example.com",
                default_from_name="Example App",
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
        settings = SmtpBaseSettings(
            domain="example.com",
            default_from="valid@example.com",
        )
        assert settings.default_from == "valid@example.com"


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

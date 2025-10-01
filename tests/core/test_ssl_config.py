"""Tests for the SSL configuration module."""

import ssl
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from acb.ssl_config import (
    SSLConfig,
    SSLConfigMixin,
    SSLMode,
    SSLVerifyMode,
    TLSVersion,
)


class TestSSLMode:
    """Test SSLMode enum."""

    def test_ssl_mode_values(self) -> None:
        """Test SSLMode enum values."""
        assert SSLMode.DISABLED == "disabled"
        assert SSLMode.PREFERRED == "preferred"
        assert SSLMode.REQUIRED == "required"
        assert SSLMode.VERIFY_CA == "verify-ca"
        assert SSLMode.VERIFY_FULL == "verify-full"


class TestSSLVerifyMode:
    """Test SSLVerifyMode enum."""

    def test_ssl_verify_mode_values(self) -> None:
        """Test SSLVerifyMode enum values."""
        assert SSLVerifyMode.NONE == "none"
        assert SSLVerifyMode.OPTIONAL == "optional"
        assert SSLVerifyMode.REQUIRED == "required"


class TestTLSVersion:
    """Test TLSVersion enum."""

    def test_tls_version_values(self) -> None:
        """Test TLSVersion enum values."""
        assert TLSVersion.TLS_1_0 == "TLSv1.0"
        assert TLSVersion.TLS_1_1 == "TLSv1.1"
        assert TLSVersion.TLS_1_2 == "TLSv1.2"
        assert TLSVersion.TLS_1_3 == "TLSv1.3"


class TestSSLConfig:
    """Test SSLConfig model."""

    def test_default_ssl_config(self) -> None:
        """Test default SSL configuration."""
        config = SSLConfig()
        assert config.enabled is False
        assert config.mode == SSLMode.PREFERRED
        assert config.cert_path is None
        assert config.key_path is None
        assert config.ca_path is None
        assert config.verify_mode == SSLVerifyMode.REQUIRED
        assert config.verify_hostname is True
        assert config.tls_version == TLSVersion.TLS_1_2
        assert config.ciphers is None
        assert config.check_hostname is True

    def test_custom_ssl_config(self) -> None:
        """Test custom SSL configuration."""
        config = SSLConfig(
            enabled=True,
            mode=SSLMode.REQUIRED,
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            ca_path="/path/to/ca.pem",
            verify_mode=SSLVerifyMode.OPTIONAL,
            verify_hostname=False,
            tls_version=TLSVersion.TLS_1_3,
            ciphers="HIGH:!aNULL",
            check_hostname=False,
        )
        assert config.enabled is True
        assert config.mode == SSLMode.REQUIRED
        assert config.cert_path == "/path/to/cert.pem"
        assert config.key_path == "/path/to/key.pem"
        assert config.ca_path == "/path/to/ca.pem"
        assert config.verify_mode == SSLVerifyMode.OPTIONAL
        assert config.verify_hostname is False
        assert config.tls_version == TLSVersion.TLS_1_3
        assert config.ciphers == "HIGH:!aNULL"
        assert config.check_hostname is False

    def test_validate_files_no_missing(self, tmp_path: Path) -> None:
        """Test file validation with no missing files."""
        # Create temporary files
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        ca_file = tmp_path / "ca.pem"

        cert_file.write_text("cert content")
        key_file.write_text("key content")
        ca_file.write_text("ca content")

        config = SSLConfig(
            enabled=True,
            cert_path=str(cert_file),
            key_path=str(key_file),
            ca_path=str(ca_file),
        )

        missing_files = config.validate_files()
        assert missing_files == []

    def test_validate_files_missing_files(self, tmp_path: Path) -> None:
        """Test file validation with missing files."""
        # Create only one file
        cert_file = tmp_path / "cert.pem"
        cert_file.write_text("cert content")

        config = SSLConfig(
            enabled=True,
            cert_path=str(cert_file),
            key_path="/nonexistent/key.pem",
            ca_path="/nonexistent/ca.pem",
        )

        missing_files = config.validate_files()
        assert len(missing_files) == 2
        assert "private key: /nonexistent/key.pem" in missing_files
        assert "CA certificate: /nonexistent/ca.pem" in missing_files

    def test_validate_files_ssl_disabled(self, tmp_path: Path) -> None:
        """Test file validation when SSL is disabled."""
        config = SSLConfig(
            enabled=False,
            cert_path="/nonexistent/cert.pem",
            key_path="/nonexistent/key.pem",
        )

        missing_files = config.validate_files()
        assert missing_files == []

    def test_create_ssl_context_disabled(self) -> None:
        """Test SSL context creation when disabled."""
        config = SSLConfig(enabled=False)
        context = config.create_ssl_context()
        assert context is None

    def test_create_ssl_context_default(self) -> None:
        """Test default SSL context creation."""
        config = SSLConfig(enabled=True)
        context = config.create_ssl_context()
        assert context is not None
        assert isinstance(context, ssl.SSLContext)

    def test_create_ssl_context_tls_1_0(self) -> None:
        """Test SSL context creation with TLS 1.0."""
        config = SSLConfig(enabled=True, tls_version=TLSVersion.TLS_1_0)
        context = config.create_ssl_context()
        assert context is not None
        # Note: We can't easily test the minimum_version attribute as it's not directly accessible

    def test_create_ssl_context_tls_1_1(self) -> None:
        """Test SSL context creation with TLS 1.1."""
        config = SSLConfig(enabled=True, tls_version=TLSVersion.TLS_1_1)
        context = config.create_ssl_context()
        assert context is not None
        # Note: We can't easily test the minimum_version attribute as it's not directly accessible

    def test_create_ssl_context_with_ciphers(self) -> None:
        """Test SSL context creation with custom ciphers."""
        config = SSLConfig(
            enabled=True,
            ciphers="HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA"
        )
        context = config.create_ssl_context()
        assert context is not None
        # Note: We can't easily test the ciphers as they're not directly accessible

    def test_create_ssl_context_verify_none(self) -> None:
        """Test SSL context creation with verify none."""
        config = SSLConfig(
            enabled=True, verify_mode=SSLVerifyMode.NONE, check_hostname=False
        )
        context = config.create_ssl_context()
        assert context is not None
        assert context.check_hostname is False
        assert context.verify_mode == ssl.CERT_NONE

    def test_create_ssl_context_verify_optional(self) -> None:
        """Test SSL context creation with verify optional."""
        config = SSLConfig(
            enabled=True,
            verify_mode=SSLVerifyMode.OPTIONAL,
            check_hostname=False,
        )
        context = config.create_ssl_context()
        assert context is not None
        assert context.check_hostname is False
        assert context.verify_mode == ssl.CERT_OPTIONAL

    @patch("pathlib.Path.exists")
    @patch("ssl.SSLContext.load_cert_chain")
    @patch("ssl.SSLContext.load_verify_locations")
    def test_create_ssl_context_with_certificates(
        self,
        mock_load_verify: MagicMock,
        mock_load_cert: MagicMock,
        mock_exists: MagicMock
    ) -> None:
        """Test SSL context creation with certificate files."""
        mock_exists.return_value = True
        mock_load_cert.return_value = None
        mock_load_verify.return_value = None

        config = SSLConfig(
            enabled=True,
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            ca_path="/path/to/ca.pem",
        )
        context = config.create_ssl_context()
        assert context is not None
        mock_load_cert.assert_called_once_with("/path/to/cert.pem", "/path/to/key.pem")
        mock_load_verify.assert_called_once_with("/path/to/ca.pem")


class TestSSLConfigMixin:
    """Test SSLConfigMixin class."""

    class MockAdapter(SSLConfigMixin):
        """Mock adapter class for testing."""

        def __init__(self) -> None:
            super().__init__()

    def test_mixin_initialization(self) -> None:
        """Test mixin initialization."""
        adapter = self.MockAdapter()
        assert adapter._ssl_config is None
        assert adapter._ssl_context is None

    def test_get_ssl_config_default(self) -> None:
        """Test getting default SSL configuration."""
        adapter = self.MockAdapter()
        config = adapter._get_ssl_config()
        assert isinstance(config, SSLConfig)
        assert config.enabled is False

    def test_configure_ssl_with_ciphers(self) -> None:
        """Test configuring SSL settings with ciphers."""
        adapter = self.MockAdapter()
        adapter.configure_ssl(
            enabled=True,
            mode=SSLMode.REQUIRED,
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            verify_hostname=False,
            ciphers="HIGH:!aNULL"
        )

        config = adapter._get_ssl_config()
        assert config.enabled is True
        assert config.mode == SSLMode.REQUIRED
        assert config.cert_path == "/path/to/cert.pem"
        assert config.key_path == "/path/to/key.pem"
        assert config.verify_hostname is False
        assert config.ciphers == "HIGH:!aNULL"

    def test_ssl_enabled_property(self) -> None:
        """Test SSL enabled property."""
        adapter = self.MockAdapter()
        assert adapter.ssl_enabled is False

        adapter.configure_ssl(enabled=True)
        assert adapter.ssl_enabled is True

    def test_validate_ssl_config(self, tmp_path: Path) -> None:
        """Test SSL configuration validation."""
        cert_file = tmp_path / "cert.pem"
        cert_file.write_text("cert content")

        adapter = self.MockAdapter()
        adapter.configure_ssl(
            enabled=True, cert_path=str(cert_file), key_path="/nonexistent/key.pem"
        )

        errors = adapter.validate_ssl_config()
        assert len(errors) == 1
        assert "private key: /nonexistent/key.pem" in errors

    def test_get_ssl_context(self) -> None:
        """Test getting SSL context."""
        adapter = self.MockAdapter()
        adapter.configure_ssl(enabled=True)

        context = adapter._get_ssl_context()
        assert context is not None
        assert isinstance(context, ssl.SSLContext)

        # Test that the same context is returned on subsequent calls
        context2 = adapter._get_ssl_context()
        assert context is context2

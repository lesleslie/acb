"""Additional tests for the ACB SSL configuration module."""

import ssl
from unittest.mock import patch

import pytest

from acb.ssl_config import (
    SSLConfig,
    SSLConfigMixin,
    SSLMode,
    SSLVerifyMode,
    TLSVersion,
)


class TestSSLConfig:
    """Test the SSLConfig class."""

    def test_ssl_config_defaults(self) -> None:
        """Test SSLConfig default values."""
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

    def test_ssl_config_custom_values(self) -> None:
        """Test SSLConfig with custom values."""
        config = SSLConfig(
            enabled=True,
            mode=SSLMode.REQUIRED,
            cert_path="/path/to/cert",
            key_path="/path/to/key",
            ca_path="/path/to/ca",
            verify_mode=SSLVerifyMode.OPTIONAL,
            verify_hostname=False,
            tls_version=TLSVersion.TLS_1_3,
            ciphers="HIGH:!aNULL",
            check_hostname=False,
        )

        assert config.enabled is True
        assert config.mode == SSLMode.REQUIRED
        assert config.cert_path == "/path/to/cert"
        assert config.key_path == "/path/to/key"
        assert config.ca_path == "/path/to/ca"
        assert config.verify_mode == SSLVerifyMode.OPTIONAL
        assert config.verify_hostname is False
        assert config.tls_version == TLSVersion.TLS_1_3
        assert config.ciphers == "HIGH:!aNULL"
        assert config.check_hostname is False

    def test_validate_files_all_exist(self, tmp_path) -> None:
        """Test validation when all files exist."""
        # Create temporary files
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        ca_file = tmp_path / "ca.pem"
        cert_file.write_text("cert content")
        key_file.write_text("key content")
        ca_file.write_text("ca content")

        config = SSLConfig(
            cert_path=str(cert_file), key_path=str(key_file), ca_path=str(ca_file)
        )

        errors = config.validate_files()
        assert errors == []

    def test_validate_files_some_missing(self, tmp_path) -> None:
        """Test validation when some files are missing."""
        # Create only one file
        cert_file = tmp_path / "cert.pem"
        cert_file.write_text("cert content")

        config = SSLConfig(
            cert_path=str(cert_file),
            key_path="/nonexistent/key.pem",
            ca_path="/nonexistent/ca.pem",
        )

        errors = config.validate_files()
        assert len(errors) == 2
        assert "SSL file not found: /nonexistent/key.pem" in errors
        assert "SSL file not found: /nonexistent/ca.pem" in errors

    def test_validate_files_all_missing(self) -> None:
        """Test validation when all files are missing."""
        config = SSLConfig(
            cert_path="/nonexistent/cert.pem",
            key_path="/nonexistent/key.pem",
            ca_path="/nonexistent/ca.pem",
        )

        errors = config.validate_files()
        assert len(errors) == 3

    def test_validate_files_none_required(self) -> None:
        """Test validation when no files are specified."""
        config = SSLConfig()

        errors = config.validate_files()
        assert errors == []

    def test_create_ssl_context_disabled(self) -> None:
        """Test creating SSL context when SSL is disabled."""
        config = SSLConfig(enabled=False, tls_version=TLSVersion.TLS_1_2)

        context = config.create_ssl_context()
        assert isinstance(context, ssl.SSLContext)

    def test_create_ssl_context_tls_1_3(self) -> None:
        """Test creating SSL context with TLS 1.3."""
        config = SSLConfig(enabled=True, tls_version=TLSVersion.TLS_1_3)

        context = config.create_ssl_context()
        assert isinstance(context, ssl.SSLContext)
        # The actual protocol value check depends on the system's SSL support

    def test_create_ssl_context_tls_1_2(self) -> None:
        """Test creating SSL context with TLS 1.2."""
        config = SSLConfig(enabled=True, tls_version=TLSVersion.TLS_1_2)

        context = config.create_ssl_context()
        assert isinstance(context, ssl.SSLContext)

    def test_create_ssl_context_verify_none(self) -> None:
        """Test creating SSL context with no verification."""
        config = SSLConfig(
            enabled=True, verify_mode=SSLVerifyMode.NONE, check_hostname=False
        )

        context = config.create_ssl_context()
        assert context.verify_mode == ssl.CERT_NONE
        assert context.check_hostname is False

    def test_create_ssl_context_verify_optional(self) -> None:
        """Test creating SSL context with optional verification."""
        config = SSLConfig(
            enabled=True, verify_mode=SSLVerifyMode.OPTIONAL, check_hostname=True
        )

        context = config.create_ssl_context()
        assert context.verify_mode == ssl.CERT_OPTIONAL
        assert context.check_hostname is True

    def test_create_ssl_context_verify_required(self) -> None:
        """Test creating SSL context with required verification."""
        config = SSLConfig(
            enabled=True, verify_mode=SSLVerifyMode.REQUIRED, check_hostname=True
        )

        context = config.create_ssl_context()
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True

    @pytest.mark.skipif(
        not hasattr(ssl, "TLSVersion"), reason="ssl.TLSVersion not available"
    )
    def test_create_ssl_context_with_certificates(self, tmp_path) -> None:
        """Test creating SSL context with certificate files."""
        # Create temporary certificate files
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

        # Mock the SSL context methods to avoid loading invalid certs
        with patch.object(ssl.SSLContext, "load_cert_chain") as mock_load_cert:
            with patch.object(ssl.SSLContext, "load_verify_locations") as mock_load_ca:
                context = config.create_ssl_context()

                # Verify the context methods were called with correct paths
                mock_load_cert.assert_called_once_with(str(cert_file), str(key_file))
                mock_load_ca.assert_called_once_with(str(ca_file))
                assert isinstance(context, ssl.SSLContext)

    def test_create_ssl_context_with_ciphers(self) -> None:
        """Test creating SSL context with ciphers."""
        config = SSLConfig(enabled=True, ciphers="HIGH:!aNULL")

        config.create_ssl_context()
        # Just ensure no exception is raised when setting ciphers

    def test_to_redis_kwargs_disabled(self) -> None:
        """Test Redis kwargs when SSL is disabled."""
        config = SSLConfig(enabled=False)

        kwargs = config.to_redis_kwargs()
        assert kwargs == {}

    def test_to_redis_kwargs_enabled_with_all_params(self, tmp_path) -> None:
        """Test Redis kwargs when SSL is enabled with all parameters."""
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        ca_file = tmp_path / "ca.pem"
        cert_file.write_text("cert")
        key_file.write_text("key")
        ca_file.write_text("ca")

        config = SSLConfig(
            enabled=True,
            cert_path=str(cert_file),
            key_path=str(key_file),
            ca_path=str(ca_file),
            verify_mode=SSLVerifyMode.NONE,
            check_hostname=False,
            tls_version=TLSVersion.TLS_1_2,
            ciphers="HIGH:!aNULL",
        )

        kwargs = config.to_redis_kwargs()
        assert kwargs["ssl"] is True
        assert kwargs["ssl_certfile"] == str(cert_file)
        assert kwargs["ssl_keyfile"] == str(key_file)
        assert kwargs["ssl_ca_certs"] == str(ca_file)
        assert kwargs["ssl_cert_reqs"] == "none"
        assert kwargs["ssl_check_hostname"] is False
        assert kwargs["ssl_minimum_version"] == TLSVersion.TLS_1_2
        assert kwargs["ssl_ciphers"] == "HIGH:!aNULL"

    def test_to_redis_kwargs_verify_modes(self) -> None:
        """Test Redis kwargs for different verification modes."""
        for verify_mode, expected in [
            (SSLVerifyMode.NONE, "none"),
            (SSLVerifyMode.OPTIONAL, "optional"),
            (SSLVerifyMode.REQUIRED, "required"),
        ]:
            config = SSLConfig(enabled=True, verify_mode=verify_mode)
            kwargs = config.to_redis_kwargs()
            assert kwargs["ssl_cert_reqs"] == expected

    def test_to_postgresql_kwargs_disabled(self) -> None:
        """Test PostgreSQL kwargs when SSL is disabled."""
        config = SSLConfig(enabled=False)

        kwargs = config.to_postgresql_kwargs()
        assert kwargs == {}

    def test_to_postgresql_kwargs_enabled_with_all_params(self, tmp_path) -> None:
        """Test PostgreSQL kwargs when SSL is enabled with all parameters."""
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        ca_file = tmp_path / "ca.pem"
        cert_file.write_text("cert")
        key_file.write_text("key")
        ca_file.write_text("ca")

        config = SSLConfig(
            enabled=True,
            cert_path=str(cert_file),
            key_path=str(key_file),
            ca_path=str(ca_file),
            mode=SSLMode.VERIFY_FULL,
        )

        kwargs = config.to_postgresql_kwargs()
        assert kwargs["sslcert"] == str(cert_file)
        assert kwargs["sslkey"] == str(key_file)
        assert kwargs["sslrootcert"] == str(ca_file)
        assert kwargs["sslmode"] == "verify-full"

    def test_to_postgresql_kwargs_modes(self) -> None:
        """Test PostgreSQL kwargs for different SSL modes."""
        mode_mapping = {
            SSLMode.DISABLED: "disable",
            SSLMode.PREFERRED: "prefer",
            SSLMode.REQUIRED: "require",
            SSLMode.VERIFY_CA: "verify-ca",
            SSLMode.VERIFY_FULL: "verify-full",
        }

        for mode, expected in mode_mapping.items():
            config = SSLConfig(enabled=True, mode=mode)
            kwargs = config.to_postgresql_kwargs()
            assert kwargs["sslmode"] == expected

    def test_to_mysql_kwargs_disabled(self) -> None:
        """Test MySQL kwargs when SSL is disabled."""
        config = SSLConfig(enabled=False)

        kwargs = config.to_mysql_kwargs()
        assert kwargs == {}

    def test_to_mysql_kwargs_enabled_with_all_params(self, tmp_path) -> None:
        """Test MySQL kwargs when SSL is enabled with all parameters."""
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        ca_file = tmp_path / "ca.pem"
        cert_file.write_text("cert")
        key_file.write_text("key")
        ca_file.write_text("ca")

        config = SSLConfig(
            enabled=True,
            cert_path=str(cert_file),
            key_path=str(key_file),
            ca_path=str(ca_file),
            mode=SSLMode.VERIFY_FULL,
        )

        kwargs = config.to_mysql_kwargs()
        assert kwargs["ssl_cert"] == str(cert_file)
        assert kwargs["ssl_key"] == str(key_file)
        assert kwargs["ssl_ca"] == str(ca_file)
        assert kwargs["ssl_mode"] == "VERIFY_IDENTITY"

    def test_to_mysql_kwargs_modes(self) -> None:
        """Test MySQL kwargs for different SSL modes."""
        mode_mapping = {
            SSLMode.DISABLED: "ssl_disabled",
            SSLMode.PREFERRED: "ssl_mode",
            SSLMode.REQUIRED: "ssl_mode",
            SSLMode.VERIFY_CA: "ssl_mode",
            SSLMode.VERIFY_FULL: "ssl_mode",
        }

        mode_values = {
            SSLMode.DISABLED: True,
            SSLMode.PREFERRED: "PREFERRED",
            SSLMode.REQUIRED: "REQUIRED",
            SSLMode.VERIFY_CA: "VERIFY_CA",
            SSLMode.VERIFY_FULL: "VERIFY_IDENTITY",
        }

        for mode, expected_key in mode_mapping.items():
            config = SSLConfig(enabled=True, mode=mode)
            kwargs = config.to_mysql_kwargs()
            if mode == SSLMode.DISABLED:
                assert kwargs[expected_key] is True
            else:
                assert kwargs[expected_key] == mode_values[mode]

    def test_to_mongodb_kwargs_disabled(self) -> None:
        """Test MongoDB kwargs when SSL is disabled."""
        config = SSLConfig(enabled=False)

        kwargs = config.to_mongodb_kwargs()
        assert kwargs == {}

    def test_to_mongodb_kwargs_enabled_with_all_params(self, tmp_path) -> None:
        """Test MongoDB kwargs when SSL is enabled with all parameters."""
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        ca_file = tmp_path / "ca.pem"
        cert_file.write_text("cert")
        key_file.write_text("key")
        ca_file.write_text("ca")

        config = SSLConfig(
            enabled=True,
            cert_path=str(cert_file),
            key_path=str(key_file),
            ca_path=str(ca_file),
            verify_mode=SSLVerifyMode.NONE,
        )

        kwargs = config.to_mongodb_kwargs()
        assert kwargs["ssl"] is True
        assert kwargs["ssl_certfile"] == str(cert_file)
        assert kwargs["ssl_keyfile"] == str(key_file)
        assert kwargs["ssl_ca_certs"] == str(ca_file)
        assert kwargs["ssl_cert_reqs"] == "CERT_NONE"
        assert kwargs["ssl_match_hostname"] == config.check_hostname

    def test_to_mongodb_kwargs_verify_modes(self) -> None:
        """Test MongoDB kwargs for different verification modes."""
        for verify_mode, expected in [
            (SSLVerifyMode.NONE, "CERT_NONE"),
            (SSLVerifyMode.OPTIONAL, "CERT_OPTIONAL"),
            (SSLVerifyMode.REQUIRED, "CERT_REQUIRED"),
        ]:
            config = SSLConfig(enabled=True, verify_mode=verify_mode)
            kwargs = config.to_mongodb_kwargs()
            assert kwargs["ssl_cert_reqs"] == expected

    def test_to_niquests_kwargs_disabled(self) -> None:
        """Test Niquests kwargs when SSL is disabled."""
        config = SSLConfig(enabled=False)

        kwargs = config.to_niquests_kwargs()
        assert kwargs == {}

    def test_to_niquests_kwargs_enabled_with_cert_and_key(self, tmp_path) -> None:
        """Test Niquests kwargs when SSL is enabled with cert and key."""
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        cert_file.write_text("cert")
        key_file.write_text("key")

        config = SSLConfig(
            enabled=True, cert_path=str(cert_file), key_path=str(key_file)
        )

        kwargs = config.to_niquests_kwargs()
        assert kwargs["cert"] == (str(cert_file), str(key_file))
        assert kwargs["verify"] is True  # Default when no CA provided

    def test_to_niquests_kwargs_enabled_with_ca_path(self, tmp_path) -> None:
        """Test Niquests kwargs when SSL is enabled with CA path."""
        ca_file = tmp_path / "ca.pem"
        ca_file.write_text("ca")

        config = SSLConfig(enabled=True, ca_path=str(ca_file))

        kwargs = config.to_niquests_kwargs()
        assert kwargs["verify"] == str(ca_file)

    def test_to_niquests_kwargs_verify_false(self) -> None:
        """Test Niquests kwargs with verify false."""
        config = SSLConfig(enabled=True, verify_mode=SSLVerifyMode.NONE)

        kwargs = config.to_niquests_kwargs()
        assert kwargs["verify"] is False

    def test_to_httpx_kwargs_disabled(self) -> None:
        """Test HTTPX kwargs when SSL is disabled."""
        config = SSLConfig(enabled=False)

        kwargs = config.to_httpx_kwargs()
        assert kwargs == {}

    def test_to_httpx_kwargs_enabled_with_cert_and_key(self, tmp_path) -> None:
        """Test HTTPX kwargs when SSL is enabled with cert and key."""
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        cert_file.write_text("cert")
        key_file.write_text("key")

        config = SSLConfig(
            enabled=True, cert_path=str(cert_file), key_path=str(key_file)
        )

        kwargs = config.to_httpx_kwargs()
        assert kwargs["cert"] == (str(cert_file), str(key_file))
        assert kwargs["verify"] is True  # Default when no CA provided

    def test_to_httpx_kwargs_enabled_with_ca_path(self, tmp_path) -> None:
        """Test HTTPX kwargs when SSL is enabled with CA path."""
        ca_file = tmp_path / "ca.pem"
        ca_file.write_text("ca")

        config = SSLConfig(enabled=True, ca_path=str(ca_file))

        kwargs = config.to_httpx_kwargs()
        assert kwargs["verify"] == str(ca_file)

    def test_to_httpx_kwargs_verify_false(self) -> None:
        """Test HTTPX kwargs with verify false."""
        config = SSLConfig(enabled=True, verify_mode=SSLVerifyMode.NONE)

        kwargs = config.to_httpx_kwargs()
        assert kwargs["verify"] is False

    def test_to_http_client_kwargs_disabled(self) -> None:
        """Test consolidated HTTP client kwargs when SSL is disabled."""
        config = SSLConfig(enabled=False)

        kwargs = config.to_http_client_kwargs()
        assert kwargs == {}

    def test_to_http_client_kwargs_with_cert_and_key(self, tmp_path) -> None:
        """Test consolidated HTTP client kwargs with cert and key."""
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        cert_file.write_text("cert")
        key_file.write_text("key")

        config = SSLConfig(
            enabled=True, cert_path=str(cert_file), key_path=str(key_file)
        )

        kwargs = config.to_http_client_kwargs()
        assert kwargs["cert"] == (str(cert_file), str(key_file))
        assert kwargs["verify"] is True

    def test_to_http_client_kwargs_with_ca_path(self, tmp_path) -> None:
        """Test consolidated HTTP client kwargs with CA path."""
        ca_file = tmp_path / "ca.pem"
        ca_file.write_text("ca")

        config = SSLConfig(enabled=True, ca_path=str(ca_file))

        kwargs = config.to_http_client_kwargs()
        assert kwargs["verify"] == str(ca_file)

    def test_to_http_client_kwargs_with_ciphers(self) -> None:
        """Test consolidated HTTP client kwargs with ciphers."""
        config = SSLConfig(enabled=True, ciphers="HIGH:!aNULL:!eNULL")

        kwargs = config.to_http_client_kwargs()
        assert kwargs["ciphers"] == "HIGH:!aNULL:!eNULL"

    def test_backward_compatibility_type_aliases(self) -> None:
        """Test that Niquests and HTTPX type aliases work correctly."""
        from acb.ssl_config import (
            HTTPClientSSLKwargs,
            HTTPXSSLKwargs,
            NiquestsSSLKwargs,
        )

        # Verify type aliases point to the same class
        assert NiquestsSSLKwargs is HTTPClientSSLKwargs
        assert HTTPXSSLKwargs is HTTPClientSSLKwargs

    def test_niquests_httpx_methods_delegate_correctly(self, tmp_path) -> None:
        """Test that to_niquests_kwargs and to_httpx_kwargs delegate to to_http_client_kwargs."""
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        cert_file.write_text("cert")
        key_file.write_text("key")

        config = SSLConfig(
            enabled=True,
            cert_path=str(cert_file),
            key_path=str(key_file),
            ciphers="HIGH",
        )

        # All three methods should return identical results
        http_kwargs = config.to_http_client_kwargs()
        niquests_kwargs = config.to_niquests_kwargs()
        httpx_kwargs = config.to_httpx_kwargs()

        assert http_kwargs == niquests_kwargs
        assert http_kwargs == httpx_kwargs
        assert niquests_kwargs == httpx_kwargs


class TestSSLConfigMixin:
    """Test the SSLConfigMixin class."""

    def test_mixin_initialization(self) -> None:
        """Test initialization of SSLConfigMixin."""

        class TestClass(SSLConfigMixin):
            pass

        obj = TestClass()
        assert obj._ssl_config is None
        assert obj._ssl_context is None

    def test_get_ssl_config_default(self) -> None:
        """Test getting default SSL config."""

        class TestClass(SSLConfigMixin):
            pass

        obj = TestClass()
        config = obj._get_ssl_config()

        assert isinstance(config, SSLConfig)
        assert config.enabled is False  # Default value

    def test_get_ssl_config_cached(self) -> None:
        """Test that SSL config is cached."""

        class TestClass(SSLConfigMixin):
            pass

        obj = TestClass()
        config1 = obj._get_ssl_config()
        config2 = obj._get_ssl_config()

        assert config1 is config2  # Same instance

    def test_get_ssl_context(self) -> None:
        """Test getting SSL context."""

        class TestClass(SSLConfigMixin):
            pass

        obj = TestClass()
        context = obj._get_ssl_context()

        assert context is not None
        assert isinstance(context, ssl.SSLContext)

    def test_get_ssl_context_cached(self) -> None:
        """Test that SSL context is cached."""

        class TestClass(SSLConfigMixin):
            pass

        obj = TestClass()
        context1 = obj._get_ssl_context()
        context2 = obj._get_ssl_context()

        assert context1 is context2  # Same instance

    def test_configure_ssl(self) -> None:
        """Test configuring SSL settings."""

        class TestClass(SSLConfigMixin):
            pass

        obj = TestClass()

        obj.configure_ssl(
            enabled=True,
            mode=SSLMode.REQUIRED,
            cert_path="/path/to/cert",
            verify_mode=SSLVerifyMode.OPTIONAL,
        )

        config = obj._get_ssl_config()
        assert config.enabled is True
        assert config.mode == SSLMode.REQUIRED
        assert config.cert_path == "/path/to/cert"
        assert config.verify_mode == SSLVerifyMode.OPTIONAL

    def test_configure_ssl_resets_context(self) -> None:
        """Test that configuring SSL resets the context."""

        class TestClass(SSLConfigMixin):
            pass

        obj = TestClass()

        # Get initial context
        initial_context = obj._get_ssl_context()

        # Configure SSL to reset context
        obj.configure_ssl(enabled=True)

        # Get new context
        new_context = obj._get_ssl_context()

        # The contexts should be different objects since the first was discarded
        # when configure_ssl was called
        assert new_context != initial_context

    def test_validate_ssl_config(self) -> None:
        """Test validating SSL configuration."""

        class TestClass(SSLConfigMixin):
            pass

        obj = TestClass()
        obj.configure_ssl(cert_path="/nonexistent/cert", key_path="/nonexistent/key")

        errors = obj.validate_ssl_config()
        assert len(errors) == 2
        assert any("SSL file not found: /nonexistent/cert" in error for error in errors)
        assert any("SSL file not found: /nonexistent/key" in error for error in errors)

    def test_ssl_enabled_property(self) -> None:
        """Test the ssl_enabled property."""

        class TestClass(SSLConfigMixin):
            pass

        obj = TestClass()

        # Initially disabled
        assert obj.ssl_enabled is False

        # Enable and test again
        obj.configure_ssl(enabled=True)
        assert obj.ssl_enabled is True

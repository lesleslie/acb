"""Unit tests for SSL/TLS configuration helpers."""

from __future__ import annotations

import ssl

import pytest

from acb.ssl_config import (
    SSLConfig,
    SSLConfigMixin,
    SSLMode,
    SSLVerifyMode,
    TLSVersion,
)


@pytest.mark.unit
def test_ssl_to_redis_kwargs_basic() -> None:
    cfg = SSLConfig(
        enabled=True,
        cert_path="/tmp/cert.pem",
        key_path="/tmp/key.pem",
        ca_path="/tmp/ca.pem",
    )
    kwargs = cfg.to_redis_kwargs()
    assert kwargs["ssl"] is True
    assert kwargs["ssl_certfile"] == "/tmp/cert.pem"
    assert kwargs["ssl_keyfile"] == "/tmp/key.pem"
    assert kwargs["ssl_ca_certs"] == "/tmp/ca.pem"
    assert kwargs["ssl_cert_reqs"] == "required"


@pytest.mark.unit
def test_ssl_to_redis_kwargs_verify_none() -> None:
    cfg = SSLConfig(enabled=True, verify_mode=SSLVerifyMode.NONE)
    kwargs = cfg.to_redis_kwargs()
    assert kwargs["ssl"] is True
    assert kwargs["ssl_cert_reqs"] == "none"
    assert kwargs["ssl_check_hostname"] is False


@pytest.mark.unit
def test_ssl_to_postgres_kwargs_modes() -> None:
    cfg = SSLConfig(enabled=True, mode=SSLMode.PREFERRED)
    assert cfg.to_postgresql_kwargs()["sslmode"] == "prefer"

    cfg = SSLConfig(enabled=True, mode=SSLMode.REQUIRED)
    assert cfg.to_postgresql_kwargs()["sslmode"] == "require"

    cfg = SSLConfig(enabled=True, mode=SSLMode.VERIFY_CA)
    assert cfg.to_postgresql_kwargs()["sslmode"] == "verify-ca"

    cfg = SSLConfig(enabled=True, mode=SSLMode.VERIFY_FULL)
    assert cfg.to_postgresql_kwargs()["sslmode"] == "verify-full"


@pytest.mark.unit
def test_ssl_to_mysql_kwargs_modes() -> None:
    cfg = SSLConfig(enabled=True, mode=SSLMode.DISABLED)
    assert cfg.to_mysql_kwargs()["ssl_disabled"] is True

    cfg = SSLConfig(enabled=True, mode=SSLMode.PREFERRED)
    assert cfg.to_mysql_kwargs()["ssl_mode"] == "PREFERRED"

    cfg = SSLConfig(enabled=True, mode=SSLMode.REQUIRED)
    assert cfg.to_mysql_kwargs()["ssl_mode"] == "REQUIRED"

    cfg = SSLConfig(enabled=True, mode=SSLMode.VERIFY_CA)
    assert cfg.to_mysql_kwargs()["ssl_mode"] == "VERIFY_CA"

    cfg = SSLConfig(enabled=True, mode=SSLMode.VERIFY_FULL)
    assert cfg.to_mysql_kwargs()["ssl_mode"] == "VERIFY_IDENTITY"


@pytest.mark.unit
def test_ssl_to_http_clients_kwargs() -> None:
    cfg = SSLConfig(
        enabled=True,
        cert_path="/tmp/cert.pem",
        key_path="/tmp/key.pem",
        ca_path="/tmp/ca.pem",
    )
    r_kwargs = cfg.to_niquests_kwargs()
    x_kwargs = cfg.to_httpx_kwargs()
    assert r_kwargs["cert"] == ("/tmp/cert.pem", "/tmp/key.pem")
    assert x_kwargs["cert"] == ("/tmp/cert.pem", "/tmp/key.pem")
    assert r_kwargs["verify"] == "/tmp/ca.pem"
    assert x_kwargs["verify"] == "/tmp/ca.pem"


@pytest.mark.unit
def test_create_ssl_context_versions() -> None:
    cfg = SSLConfig(tls_version=TLSVersion.TLS_1_2)
    ctx = cfg.create_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.minimum_version in (
        ssl.TLSVersion.TLSv1_2,
        ssl.TLSVersion.MINIMUM_SUPPORTED,
    )

    cfg = SSLConfig(tls_version=TLSVersion.TLS_1_3)
    ctx = cfg.create_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.minimum_version in (
        ssl.TLSVersion.TLSv1_3,
        ssl.TLSVersion.MINIMUM_SUPPORTED,
    )


class _WithSSL(SSLConfigMixin):
    pass


@pytest.mark.unit
def test_ssl_config_mixin_flow() -> None:
    obj = _WithSSL()
    # Default lazy creation
    ctx1 = obj._get_ssl_context()
    assert isinstance(ctx1, ssl.SSLContext)

    # Update configuration and ensure context resets
    obj.configure_ssl(
        enabled=True, verify_mode=SSLVerifyMode.NONE, tls_version=TLSVersion.TLS_1_2
    )
    errs = obj.validate_ssl_config()  # no files provided → no errors
    assert errs == []
    ctx2 = obj._get_ssl_context()
    assert isinstance(ctx2, ssl.SSLContext)

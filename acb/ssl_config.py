"""Unified SSL/TLS configuration for ACB adapters.

This module provides a standardized SSL/TLS configuration system that can be used
across all ACB adapters for consistent and secure connections.
"""

import ssl
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field
from typing import Any, NotRequired, TypedDict


class SSLMode(str, Enum):
    """Standard SSL/TLS connection modes."""

    DISABLED = "disabled"
    PREFERRED = "preferred"
    REQUIRED = "required"
    VERIFY_CA = "verify-ca"
    VERIFY_FULL = "verify-full"


class SSLVerifyMode(str, Enum):
    """SSL certificate verification modes."""

    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


class TLSVersion(str, Enum):
    """Supported TLS versions."""

    TLS_1_0 = "TLSv1.0"
    TLS_1_1 = "TLSv1.1"
    TLS_1_2 = "TLSv1.2"
    TLS_1_3 = "TLSv1.3"


# TypedDict definitions for SSL kwargs by library
class RedisSSLKwargs(TypedDict, total=False):
    """TypedDict for Redis SSL connection parameters."""

    ssl: bool
    ssl_certfile: NotRequired[str]
    ssl_keyfile: NotRequired[str]
    ssl_ca_certs: NotRequired[str]
    ssl_cert_reqs: NotRequired[str]  # "none", "optional", "required"
    ssl_check_hostname: NotRequired[bool]
    ssl_minimum_version: NotRequired[str]
    ssl_ciphers: NotRequired[str]


class PostgreSQLSSLKwargs(TypedDict, total=False):
    """TypedDict for PostgreSQL SSL connection parameters."""

    sslcert: NotRequired[str]
    sslkey: NotRequired[str]
    sslrootcert: NotRequired[str]
    sslmode: NotRequired[
        str
    ]  # "disable", "prefer", "require", "verify-ca", "verify-full"


class MySQLSSLKwargs(TypedDict, total=False):
    """TypedDict for MySQL SSL connection parameters."""

    ssl_cert: NotRequired[str]
    ssl_key: NotRequired[str]
    ssl_ca: NotRequired[str]
    ssl_disabled: NotRequired[bool]
    ssl_mode: NotRequired[
        str
    ]  # "PREFERRED", "REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"


class MongoDBSSLKwargs(TypedDict, total=False):
    """TypedDict for MongoDB SSL connection parameters."""

    ssl: bool
    ssl_certfile: NotRequired[str]
    ssl_keyfile: NotRequired[str]
    ssl_ca_certs: NotRequired[str]
    ssl_cert_reqs: NotRequired[str]  # "CERT_NONE", "CERT_OPTIONAL", "CERT_REQUIRED"
    ssl_match_hostname: NotRequired[bool]


class HTTPClientSSLKwargs(TypedDict, total=False):
    """TypedDict for HTTP client SSL connection parameters.

    Used by both Niquests and HTTPX, which share the same SSL interface.
    """

    cert: NotRequired[str | tuple[str, str]]
    verify: NotRequired[bool | str]
    ciphers: NotRequired[str]


# Type aliases for backwards compatibility
NiquestsSSLKwargs = HTTPClientSSLKwargs
HTTPXSSLKwargs = HTTPClientSSLKwargs


class SSLConfig(BaseModel):
    """Unified SSL/TLS configuration model.

    This class provides a standardized way to configure SSL/TLS connections
    across all ACB adapters, ensuring consistent security settings.
    """

    # Basic SSL settings
    enabled: bool = Field(default=False, description="Enable SSL/TLS connections")

    mode: SSLMode = Field(default=SSLMode.PREFERRED, description="SSL connection mode")

    # Certificate and key files
    cert_path: str | None = Field(
        default=None,
        description="Path to SSL certificate file",
    )

    key_path: str | None = Field(
        default=None,
        description="Path to SSL private key file",
    )

    ca_path: str | None = Field(
        default=None,
        description="Path to SSL Certificate Authority file",
    )

    # Verification settings
    verify_mode: SSLVerifyMode = Field(
        default=SSLVerifyMode.REQUIRED,
        description="Certificate verification mode",
    )

    verify_hostname: bool = Field(
        default=True,
        description="Verify hostname against certificate",
    )

    # Protocol settings
    tls_version: TLSVersion = Field(
        default=TLSVersion.TLS_1_2,
        description="Minimum TLS version to use",
    )

    ciphers: str | None = Field(default=None, description="Allowed cipher suites")

    # Connection settings
    check_hostname: bool = Field(
        default=True,
        description="Check hostname in certificate",
    )

    def validate_files(self) -> list[str]:
        """Validate SSL certificate files exist if provided.

        Returns:
            List of validation errors, empty if valid.
        """
        # Validate certificate file paths if provided
        return [
            f"SSL file not found: {path_attr}"
            for path_attr in (self.cert_path, self.key_path, self.ca_path)
            if path_attr and not Path(path_attr).exists()
        ]

    def create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context from configuration."""
        # Create context based on TLS version
        if self.tls_version == TLSVersion.TLS_1_3:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.minimum_version = ssl.TLSVersion.TLSv1_3
        elif self.tls_version == TLSVersion.TLS_1_2:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        else:
            # Use default context for older TLS versions
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        # Configure verification
        if self.verify_mode == SSLVerifyMode.NONE:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        elif self.verify_mode == SSLVerifyMode.OPTIONAL:
            context.check_hostname = self.check_hostname
            context.verify_mode = ssl.CERT_OPTIONAL
        else:  # REQUIRED
            context.check_hostname = self.check_hostname
            context.verify_mode = ssl.CERT_REQUIRED

        # Load certificates
        if self.cert_path and self.key_path:
            context.load_cert_chain(self.cert_path, self.key_path)
        if self.ca_path:
            context.load_verify_locations(self.ca_path)

        # Set ciphers if specified
        if self.ciphers:
            context.set_ciphers(self.ciphers)

        return context

    def to_redis_kwargs(self) -> RedisSSLKwargs:
        """Convert SSL configuration to Redis client SSL kwargs.

        Returns:
            Dictionary of SSL kwargs for Redis client.
        """
        if not self.enabled:
            return {}

        ssl_kwargs: RedisSSLKwargs = {"ssl": True}

        # Map SSL configuration to Redis SSL kwargs
        if self.cert_path:
            ssl_kwargs["ssl_certfile"] = self.cert_path
        if self.key_path:
            ssl_kwargs["ssl_keyfile"] = self.key_path
        if self.ca_path:
            ssl_kwargs["ssl_ca_certs"] = self.ca_path

        # Handle verification mode
        if self.verify_mode == SSLVerifyMode.NONE:
            ssl_kwargs["ssl_cert_reqs"] = "none"
        elif self.verify_mode == SSLVerifyMode.OPTIONAL:
            ssl_kwargs["ssl_cert_reqs"] = "optional"
        else:  # REQUIRED
            ssl_kwargs["ssl_cert_reqs"] = "required"

        # Handle hostname verification
        if self.verify_mode == SSLVerifyMode.NONE:
            ssl_kwargs["ssl_check_hostname"] = False
        else:
            ssl_kwargs["ssl_check_hostname"] = self.check_hostname

        # Handle TLS version
        if self.tls_version:
            ssl_kwargs["ssl_minimum_version"] = self.tls_version

        # Handle ciphers
        if self.ciphers:
            ssl_kwargs["ssl_ciphers"] = self.ciphers

        return ssl_kwargs

    def to_postgresql_kwargs(self) -> PostgreSQLSSLKwargs:
        """Convert SSL configuration to PostgreSQL client SSL kwargs.

        Returns:
            Dictionary of SSL kwargs for PostgreSQL client.
        """
        if not self.enabled:
            return {}

        ssl_kwargs: PostgreSQLSSLKwargs = {}

        # Map SSL configuration to PostgreSQL SSL kwargs
        if self.cert_path:
            ssl_kwargs["sslcert"] = self.cert_path
        if self.key_path:
            ssl_kwargs["sslkey"] = self.key_path
        if self.ca_path:
            ssl_kwargs["sslrootcert"] = self.ca_path

        # Handle SSL mode
        if self.mode == SSLMode.DISABLED:
            ssl_kwargs["sslmode"] = "disable"
        elif self.mode == SSLMode.PREFERRED:
            ssl_kwargs["sslmode"] = "prefer"
        elif self.mode == SSLMode.REQUIRED:
            ssl_kwargs["sslmode"] = "require"
        elif self.mode == SSLMode.VERIFY_CA:
            ssl_kwargs["sslmode"] = "verify-ca"
        elif self.mode == SSLMode.VERIFY_FULL:
            ssl_kwargs["sslmode"] = "verify-full"

        return ssl_kwargs

    def to_mysql_kwargs(self) -> MySQLSSLKwargs:
        """Convert SSL configuration to MySQL client SSL kwargs.

        Returns:
            Dictionary of SSL kwargs for MySQL client.
        """
        if not self.enabled:
            return {}

        ssl_kwargs: MySQLSSLKwargs = {}

        # Map SSL configuration to MySQL SSL kwargs
        if self.cert_path:
            ssl_kwargs["ssl_cert"] = self.cert_path
        if self.key_path:
            ssl_kwargs["ssl_key"] = self.key_path
        if self.ca_path:
            ssl_kwargs["ssl_ca"] = self.ca_path

        # Handle SSL mode
        if self.mode == SSLMode.DISABLED:
            ssl_kwargs["ssl_disabled"] = True
        elif self.mode == SSLMode.PREFERRED:
            ssl_kwargs["ssl_mode"] = "PREFERRED"
        elif self.mode == SSLMode.REQUIRED:
            ssl_kwargs["ssl_mode"] = "REQUIRED"
        elif self.mode == SSLMode.VERIFY_CA:
            ssl_kwargs["ssl_mode"] = "VERIFY_CA"
        elif self.mode == SSLMode.VERIFY_FULL:
            ssl_kwargs["ssl_mode"] = "VERIFY_IDENTITY"

        return ssl_kwargs

    def to_mongodb_kwargs(self) -> MongoDBSSLKwargs:
        """Convert SSL configuration to MongoDB client SSL kwargs.

        Returns:
            Dictionary of SSL kwargs for MongoDB client.
        """
        if not self.enabled:
            return {}

        ssl_kwargs: MongoDBSSLKwargs = {"ssl": True}

        # Map SSL configuration to MongoDB SSL kwargs
        if self.cert_path:
            ssl_kwargs["ssl_certfile"] = self.cert_path
        if self.key_path:
            ssl_kwargs["ssl_keyfile"] = self.key_path
        if self.ca_path:
            ssl_kwargs["ssl_ca_certs"] = self.ca_path

        # Handle verification mode
        if self.verify_mode == SSLVerifyMode.NONE:
            ssl_kwargs["ssl_cert_reqs"] = "CERT_NONE"
        elif self.verify_mode == SSLVerifyMode.OPTIONAL:
            ssl_kwargs["ssl_cert_reqs"] = "CERT_OPTIONAL"
        else:  # REQUIRED
            ssl_kwargs["ssl_cert_reqs"] = "CERT_REQUIRED"

        # Handle hostname verification
        ssl_kwargs["ssl_match_hostname"] = self.check_hostname

        return ssl_kwargs

    def to_http_client_kwargs(self) -> HTTPClientSSLKwargs:
        """Convert SSL configuration to HTTP client (Niquests/HTTPX) SSL kwargs.

        Returns:
            Dictionary of SSL kwargs for HTTP clients (Niquests/HTTPX).
        """
        if not self.enabled:
            return {}

        ssl_kwargs: HTTPClientSSLKwargs = {}

        # Map SSL configuration to HTTP client SSL kwargs
        if self.cert_path and self.key_path:
            ssl_kwargs["cert"] = (self.cert_path, self.key_path)
        elif self.cert_path:
            ssl_kwargs["cert"] = self.cert_path

        if self.ca_path:
            ssl_kwargs["verify"] = self.ca_path
        elif self.verify_mode == SSLVerifyMode.NONE:
            ssl_kwargs["verify"] = False
        else:
            ssl_kwargs["verify"] = True

        # Handle ciphers
        if self.ciphers:
            ssl_kwargs["ciphers"] = self.ciphers

        return ssl_kwargs

    def to_niquests_kwargs(self) -> NiquestsSSLKwargs:
        """Convert SSL configuration to Niquests client SSL kwargs.

        Alias for to_http_client_kwargs() for backwards compatibility.
        """
        return self.to_http_client_kwargs()

    def to_httpx_kwargs(self) -> HTTPXSSLKwargs:
        """Convert SSL configuration to HTTPX client SSL kwargs.

        Alias for to_http_client_kwargs() for backwards compatibility.
        """
        return self.to_http_client_kwargs()


class SSLConfigMixin:
    """Mixin to add SSL configuration capabilities to adapters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._ssl_config: SSLConfig | None = None
        self._ssl_context: ssl.SSLContext | None = None

    def _get_ssl_config(self) -> SSLConfig:
        """Get SSL configuration."""
        if self._ssl_config is None:
            self._ssl_config = SSLConfig()
        return self._ssl_config

    def _get_ssl_context(self) -> ssl.SSLContext | None:
        """Get SSL context, creating if necessary."""
        if self._ssl_context is None:
            ssl_config = self._get_ssl_config()
            self._ssl_context = ssl_config.create_ssl_context()
        return self._ssl_context

    def configure_ssl(
        self,
        enabled: bool = False,
        mode: SSLMode = SSLMode.PREFERRED,
        cert_path: str | None = None,
        key_path: str | None = None,
        ca_path: str | None = None,
        verify_mode: SSLVerifyMode = SSLVerifyMode.REQUIRED,
        verify_hostname: bool = True,
        tls_version: TLSVersion = TLSVersion.TLS_1_2,
        ciphers: str | None = None,
        check_hostname: bool = True,
    ) -> None:
        """Configure SSL settings for this adapter.

        Args:
            enabled: Enable SSL/TLS connections
            mode: SSL connection mode
            cert_path: Path to SSL certificate file
            key_path: Path to SSL private key file
            ca_path: Path to SSL Certificate Authority file
            verify_mode: Certificate verification mode
            verify_hostname: Verify hostname against certificate
            tls_version: Minimum TLS version to use
            ciphers: Allowed cipher suites
            check_hostname: Check hostname in certificate
        """
        self._ssl_config = SSLConfig(
            enabled=enabled,
            mode=mode,
            cert_path=cert_path,
            key_path=key_path,
            ca_path=ca_path,
            verify_mode=verify_mode,
            verify_hostname=verify_hostname,
            tls_version=tls_version,
            ciphers=ciphers,
            check_hostname=check_hostname,
        )
        # Reset SSL context so it will be recreated with new config
        self._ssl_context = None

    def validate_ssl_config(self) -> list[str]:
        """Validate SSL configuration.

        Returns:
            List of validation errors, empty if valid.
        """
        ssl_config = self._get_ssl_config()
        return ssl_config.validate_files()

    @property
    def ssl_enabled(self) -> bool:
        """Check if SSL is enabled."""
        ssl_config = self._get_ssl_config()
        return ssl_config.enabled

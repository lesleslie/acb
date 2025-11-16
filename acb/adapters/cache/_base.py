import typing as t
from aiocache import BaseCache
from aiocache.serializers import BaseSerializer
from msgspec import msgpack
from pydantic import SecretStr

from acb.actions.compress import compress, decompress
from acb.cleanup import CleanupMixin
from acb.config import Config, Settings
from acb.depends import Inject, depends
from acb.ssl_config import SSLConfigMixin


class CacheBaseSettings(Settings, SSLConfigMixin):
    default_ttl: int = 86400
    query_ttl: int = 600
    response_ttl: int | None = 3600
    template_ttl: int | None = 86400

    host: SecretStr = SecretStr("127.0.0.1")
    port: int | None = None
    user: SecretStr | None = None
    password: SecretStr | None = None
    auth_token: SecretStr | None = None
    token_type: str = "Bearer"
    db: int = 0

    # SSL/TLS Configuration
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    ssl_ca_path: str | None = None
    ssl_verify_mode: str = "required"
    tls_version: str = "TLSv1.2"

    connection_string: str | None = None
    connect_timeout: float | None = 3.0
    max_connections: int | None = 50
    health_check_interval: int | None = 0
    retry_on_timeout: bool | None = True

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        # Extract SSL configuration parameters
        ssl_enabled = values.pop("ssl_enabled", False)
        ssl_cert_path = values.pop("ssl_cert_path", None)
        ssl_key_path = values.pop("ssl_key_path", None)
        ssl_ca_path = values.pop("ssl_ca_path", None)
        ssl_verify_mode = values.pop("ssl_verify_mode", "required")
        values.pop("tls_version", "TLSv1.2")

        super().__init__(**values)
        SSLConfigMixin.__init__(self)

        # Configure SSL if enabled
        if ssl_enabled:
            # Map verify mode string to enum
            from acb.ssl_config import SSLVerifyMode

            verify_mode_map = {
                "none": SSLVerifyMode.NONE,
                "optional": SSLVerifyMode.OPTIONAL,
                "required": SSLVerifyMode.REQUIRED,
            }
            verify_mode = verify_mode_map.get(ssl_verify_mode, SSLVerifyMode.REQUIRED)

            self.configure_ssl(
                enabled=True,
                cert_path=ssl_cert_path,
                key_path=ssl_key_path,
                ca_path=ssl_ca_path,
                verify_mode=verify_mode,
                check_hostname=verify_mode == SSLVerifyMode.REQUIRED,
            )

        self.response_ttl = self.default_ttl if config.deployed else 1


class MsgPackSerializer(BaseSerializer):  # type: ignore[misc]
    def __init__(self, *args: t.Any, use_list: bool = True, **kwargs: t.Any) -> None:
        self.use_list = use_list
        super().__init__(*args, **kwargs)

    def dumps(self, value: t.Any) -> str:
        msgpack_data = msgpack.encode(value)
        return compress.brotli(msgpack_data).decode("latin-1")

    def loads(self, value: str) -> t.Any:
        if not value:
            return None  # type: ignore[return-value]
        data_bytes = value.encode("latin-1")
        msgpack_data = decompress.brotli(data_bytes)
        if not msgpack_data:
            return None  # type: ignore[return-value]
        try:
            msgpack_bytes = msgpack_data.encode("latin-1")
        except AttributeError:
            msgpack_bytes = t.cast("bytes", msgpack_data)
        return msgpack.decode(msgpack_bytes)


class CacheProtocol(t.Protocol):
    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None: ...

    async def get(self, key: str) -> bytes | None: ...

    async def exists(self, key: str) -> bool: ...

    async def clear(self, namespace: str) -> None: ...

    async def scan(self, pattern: str) -> t.AsyncIterator[str]: ...


class CacheBase(BaseCache, CleanupMixin):  # type: ignore[misc]
    config: Inject[Config]
    logger: Inject[t.Any]

    def __init__(self, **kwargs: t.Any) -> None:
        BaseCache.__init__(self)
        CleanupMixin.__init__(self)
        self._client = None
        self._client_lock = None

    async def _ensure_client(self) -> t.Any:
        if self._client is None:
            if self._client_lock is None:
                import asyncio

                self._client_lock = asyncio.Lock()
            async with self._client_lock:
                if self._client is None:
                    self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> t.Any:
        msg = "Subclasses must implement _create_client()"
        raise NotImplementedError(msg)

    async def _cleanup_resources(self) -> None:
        """Override to clean up cache-specific resources."""
        # Register client for cleanup using simplified mixin
        if self._client is not None:
            self.register_resource(self._client)
            self._client = None

        # Use parent cleanup method
        await super().cleanup()

    # Removed health check functionality - simplified cache implementation

    # Basic cache operations - implementations should override these
    async def get(
        self,
        key: str,
        default: t.Any = None,
        loads_fn: t.Callable[..., t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> t.Any:
        """Get cache value."""
        client = await self._ensure_client()
        return await client.get(key)

    async def set(
        self,
        key: str,
        value: t.Any,
        ttl: int | None = None,
        dumps_fn: t.Callable[..., t.Any] | None = None,
        namespace: str | None = None,
        _cas_token: t.Any = None,
        _conn: t.Any = None,
    ) -> None:
        """Set cache value."""
        client = await self._ensure_client()
        await client.set(key, value, ttl=ttl)

    async def delete(
        self,
        key: str,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> bool:
        """Delete cache key."""
        client = await self._ensure_client()
        return bool(await client.delete(key))  # type: ignore[no-any-return]

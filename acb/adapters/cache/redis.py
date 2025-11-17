"""Redis Cache Adapter for ACB.

Integrates ACB with Redis for high-performance distributed caching using both
aiocache and coredis for maximum compatibility and features.

Features:
    - Connection pooling with configurable limits
    - Cluster support for high availability
    - Health check monitoring
    - Automatic reconnection on failures
    - Tracking cache for debugging
    - Namespace-based key organization

Requirements:
    - Redis server (standalone or cluster)
    - aiocache[redis] for cache interface
    - coredis for advanced Redis features

Example:
    Basic usage with Redis caching:

    ```python
    from acb.depends import Inject, depends
    from acb.adapters import import_adapter

    Cache = import_adapter("cache")


    @depends.inject
    async def my_function(cache: Inject[Cache]):
        await cache.set("user:123", {"name": "John"}, ttl=300)
        user_data = await cache.get("user:123")
        return user_data
    ```

Author: lesleslie <les@wedgwoodwebworks.com>
Created: 2025-01-12
"""

from uuid import UUID

import typing as t
from pydantic import SecretStr

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.config import Config
from acb.debug import debug
from acb.depends import Inject, depends
from acb.ssl_config import SSLConfigMixin

from ._base import CacheBase, CacheBaseSettings

# Lazy imports for heavy dependencies
_redis_imports: dict[str, t.Any] = {}

MODULE_ID = UUID("0197fe78-4fc8-73f6-be8a-78fd61b63a07")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Redis Cache",
    category="cache",
    provider="redis",
    version="1.1.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-15",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.CACHING,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.HEALTH_CHECKS,
        AdapterCapability.RECONNECTION,
    ],
    required_packages=["aiocache[redis]", "coredis"],
    description="High-performance Redis caching adapter with TLS support",
    settings_class="CacheSettings",
    config_example={
        "host": "localhost",
        "port": 6379,
        "password": "your-redis-password",  # pragma: allowlist secret
        "ssl_enabled": True,
        "ssl_cert_path": "/path/to/cert.pem",
        "ssl_key_path": "/path/to/key.pem",
        "ssl_ca_path": "/path/to/ca.pem",
    },
)


def _get_redis_imports() -> dict[str, t.Any]:
    """Lazy import of Redis dependencies for better startup performance."""
    if not _redis_imports:
        try:
            from aiocache.backends.redis import RedisBackend
            from aiocache.serializers import PickleSerializer
            from coredis.cache import TrackingCache
            from coredis.client import Redis, RedisCluster

            _redis_imports.update(
                {
                    "RedisBackend": RedisBackend,
                    "PickleSerializer": PickleSerializer,
                    "TrackingCache": TrackingCache,
                    "Redis": Redis,
                    "RedisCluster": RedisCluster,
                },
            )
        except ImportError as e:
            debug(f"Redis dependencies not available: {e}")

    return _redis_imports


class CacheSettings(CacheBaseSettings):
    local_host: str = "127.0.0.1"
    port: int | None = 6379
    cluster: bool | None = False

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)
        self.host: SecretStr = (
            SecretStr(self.local_host) if not config.deployed else self.host
        )
        self.port = 6379 if self.port is None else self.port
        if not self.connection_string:
            host = self.host.get_secret_value()
            auth_part = ""
            if self.user and self.password:
                auth_part = f"{self.user.get_secret_value()}:{self.password.get_secret_value()}@"
            elif self.password:
                auth_part = f":{self.password.get_secret_value()}@"
            elif self.auth_token:
                auth_part = f":{self.auth_token.get_secret_value()}@"
            protocol = "rediss" if self.ssl_enabled else "redis"
            self.connection_string = (
                f"{protocol}://{auth_part}{host}:{self.port}/{self.db}"
            )


class Cache(CacheBase, SSLConfigMixin):
    def __init__(self, redis_url: str | None = None, **kwargs: t.Any) -> None:
        self.redis_url = redis_url
        self._init_kwargs = {k: v for k, v in kwargs.items() if k != "redis_url"}
        self._redis_backend: t.Any = None
        super().__init__()
        SSLConfigMixin.__init__(self)

    def __setattr__(self, name: str, value: t.Any) -> None:
        """Override __setattr__ to handle config assignment and SSL configuration."""
        super().__setattr__(name, value)
        # If we're setting the config, configure SSL based on cache settings
        if name == "config" and hasattr(value, "cache"):
            self._update_ssl_config_from_cache_settings(value.cache)
        # If we're setting ssl_verify_mode directly on the cache, update SSL config
        elif (
            hasattr(self, "config")
            and hasattr(self.config, "cache")
            and name == "ssl_verify_mode"
        ):
            setattr(self.config.cache, name, value)
            self._update_ssl_config_from_cache_settings(self.config.cache)

    def _update_ssl_config_from_cache_settings(self, cache_settings: t.Any) -> None:
        """Update SSL configuration from cache settings."""
        if hasattr(cache_settings, "ssl_enabled") and cache_settings.ssl_enabled:
            # Configure SSL based on cache settings
            from acb.ssl_config import SSLVerifyMode

            verify_mode_map = {
                "none": SSLVerifyMode.NONE,
                "optional": SSLVerifyMode.OPTIONAL,
                "required": SSLVerifyMode.REQUIRED,
            }
            verify_mode = verify_mode_map.get(
                getattr(cache_settings, "ssl_verify_mode", "required"),
                SSLVerifyMode.REQUIRED,
            )

            self.configure_ssl(
                enabled=True,
                cert_path=getattr(cache_settings, "ssl_cert_path", None),
                key_path=getattr(cache_settings, "ssl_key_path", None),
                ca_path=getattr(cache_settings, "ssl_ca_path", None),
                verify_mode=verify_mode,
                check_hostname=verify_mode
                == SSLVerifyMode.REQUIRED,  # False for optional/none, True for required
            )

    def _build_ssl_kwargs(self) -> dict[str, t.Any]:
        """Build SSL kwargs using unified SSL configuration."""
        # Get current SSL configuration from config
        if hasattr(self, "config") and hasattr(self.config, "cache"):
            cache_settings = self.config.cache
            if hasattr(cache_settings, "ssl_enabled") and cache_settings.ssl_enabled:
                # Create SSL config dynamically from current settings
                from acb.ssl_config import SSLConfig, SSLVerifyMode

                # Map verify mode string to enum
                verify_mode_map = {
                    "none": SSLVerifyMode.NONE,
                    "optional": SSLVerifyMode.OPTIONAL,
                    "required": SSLVerifyMode.REQUIRED,
                }
                verify_mode = verify_mode_map.get(
                    getattr(cache_settings, "ssl_verify_mode", "required"),
                    SSLVerifyMode.REQUIRED,
                )

                ssl_config = SSLConfig(
                    enabled=True,
                    cert_path=getattr(cache_settings, "ssl_cert_path", None),
                    key_path=getattr(cache_settings, "ssl_key_path", None),
                    ca_path=getattr(cache_settings, "ssl_ca_path", None),
                    verify_mode=verify_mode,
                    check_hostname=verify_mode
                    == SSLVerifyMode.REQUIRED,  # False for optional/none
                )

                return dict(ssl_config.to_redis_kwargs())

        # Fall back to default behavior
        if not self.ssl_enabled:
            return {}

        ssl_config = self._get_ssl_config()
        return dict(ssl_config.to_redis_kwargs())

    async def _create_client(self) -> t.Any:
        """Create Redis client with lazy imports for better performance."""
        redis_imports = _get_redis_imports()
        if not redis_imports:
            msg = "Redis dependencies not available"
            raise ImportError(msg)

        Redis = redis_imports["Redis"]
        RedisCluster = redis_imports["RedisCluster"]
        TrackingCache = redis_imports["TrackingCache"]

        if self.config.cache.connection_string:
            redis_kwargs = self._init_kwargs | {
                "client_name": self.config.app.name if self.config.app else "acb",
                "cache": TrackingCache(),
                "decode_responses": False,
                "max_connections": self.config.cache.max_connections,
                "health_check_interval": self.config.cache.health_check_interval,
                "retry_on_timeout": self.config.cache.retry_on_timeout,
            }
            if self.config.cache.ssl_enabled:
                ssl_kwargs = self._build_ssl_kwargs()
                redis_kwargs.update(ssl_kwargs)
            if self.config.cache.cluster:
                self.logger.info("RedisCluster mode enabled")  # type: ignore[no-untyped-call]
                del redis_kwargs["health_check_interval"]
                return RedisCluster.from_url(
                    self.config.cache.connection_string,
                    **redis_kwargs,
                )

            return Redis.from_url(self.config.cache.connection_string, **redis_kwargs)
        redis_kwargs = self._init_kwargs | {
            "host": self.config.cache.host.get_secret_value(),
            "port": self.config.cache.port,
            "db": self.config.cache.db,
            "client_name": self.config.app.name if self.config.app else "acb",
            "cache": TrackingCache(),
            "decode_responses": False,
            "connect_timeout": self.config.cache.connect_timeout,
            "max_connections": self.config.cache.max_connections,
            "health_check_interval": self.config.cache.health_check_interval,
            "retry_on_timeout": self.config.cache.retry_on_timeout,
        }
        if self.config.cache.user:
            redis_kwargs["username"] = self.config.cache.user.get_secret_value()
        if self.config.cache.password:
            redis_kwargs["password"] = self.config.cache.password.get_secret_value()
        elif self.config.cache.auth_token:
            redis_kwargs["password"] = self.config.cache.auth_token.get_secret_value()
        if self.config.cache.ssl_enabled:
            ssl_kwargs = self._build_ssl_kwargs()
            redis_kwargs.update(ssl_kwargs)
        if self.config.cache.cluster:
            self.logger.info("RedisCluster mode enabled")  # type: ignore[no-untyped-call]
            del redis_kwargs["health_check_interval"]
            return RedisCluster(**redis_kwargs)

        return Redis(**redis_kwargs)

    async def get_client(self) -> t.Any:
        return await self._ensure_client()

    async def _close(self, *args: t.Any, _conn: t.Any = None, **kwargs: t.Any) -> None:
        # Clean up advanced cache if initialized
        if hasattr(self, "_multi_tier_cache") and self._multi_tier_cache is not None:
            try:
                await self._multi_tier_cache.cleanup()
                self.logger.debug("Successfully cleaned up advanced cache")  # type: ignore[no-untyped-call]
            except Exception as e:
                self.logger.warning(f"Failed to cleanup advanced cache: {e}")  # type: ignore[no-untyped-call]

        # Clean up tracing
        try:
            await self.shutdown_tracing()
            self.logger.debug("Successfully cleaned up tracing")  # type: ignore[no-untyped-call]
        except Exception as e:
            self.logger.warning(f"Failed to cleanup tracing: {e}")  # type: ignore[no-untyped-call]

        if self._client is not None:
            await self._client.close()

    async def _clear(
        self,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> t.Literal[True]:
        if not namespace:
            pattern = f"{self.config.app.name if self.config.app else 'acb'}:*"
        else:
            pattern = (
                f"{self.config.app.name if self.config.app else 'acb'}:{namespace}:*"
            )
        client = await self.get_client()
        keys = await client.keys(pattern)
        if keys:
            debug(keys)
            for key in keys:
                await client.unlink((key,))
        return True

    async def _exists(self, key: str, _conn: t.Any = None) -> bool:
        client = await self.get_client()
        number = await client.exists([key])
        return bool(number)

    def _mask_connection_string(self, connection_string: str) -> str:
        """Mask sensitive information in connection string for logging."""
        if "@" not in connection_string:
            return connection_string

        parts = connection_string.split("@")
        if ":" in parts[0]:
            auth_part = parts[0].split(":")
            if len(auth_part) >= 3:
                auth_part[2] = "***"
                parts[0] = ":".join(auth_part)
            elif len(auth_part) == 2:
                auth_part[1] = "***"
                parts[0] = ":".join(auth_part)
        return "@".join(parts)

    def _setup_serializer(self) -> None:
        """Setup the serializer for Redis operations."""
        if hasattr(self, "_serializer"):
            return

        redis_imports = _get_redis_imports()
        PickleSerializer = redis_imports.get("PickleSerializer")
        if PickleSerializer:
            self._serializer = PickleSerializer()
        else:
            # Fallback to a simple serializer if Redis imports fail
            self._serializer = None

    async def init(self, *args: t.Any, **kwargs: t.Any) -> None:
        self._init_kwargs.update(kwargs)

        if not hasattr(self, "_namespace"):
            self._namespace = f"{self.config.app.name if self.config.app else 'acb'}:"

        self._setup_serializer()

        if self.config.cache.connection_string:
            masked_connection_string = self._mask_connection_string(
                self.config.cache.connection_string,
            )
            self.logger.info(
                f"Initializing Redis cache connection to {masked_connection_string}",
            )  # type: ignore[no-untyped-call]
        else:
            self.logger.info(
                f"Initializing Redis cache connection to {self.config.cache.host.get_secret_value()}:{self.config.cache.port}",
            )  # type: ignore[no-untyped-call]

        try:
            client = await self.get_client()
            await client.ping()
            self.logger.info("Redis cache connection initialized successfully")  # type: ignore[no-untyped-call]
        except Exception as e:
            self.logger.exception(f"Failed to initialize Redis cache connection: {e}")  # type: ignore[no-untyped-call]
            raise


depends.set(Cache, "redis")

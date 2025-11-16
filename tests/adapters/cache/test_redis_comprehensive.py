"""Comprehensive tests for Redis Cache adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typing as t
from pydantic import SecretStr

from acb.adapters.cache.redis import Cache, CacheSettings
from acb.config import Config


class MockRedisClient:
    """Mock for Redis Client."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        # Create the mock attributes directly
        self.ping = AsyncMock()
        self.close = AsyncMock()
        self.keys = AsyncMock()
        self.unlink = AsyncMock()
        self.exists = AsyncMock()
        self.get = AsyncMock()
        self.set = AsyncMock()
        self.delete = AsyncMock()

    @classmethod
    def from_url(cls, *args: t.Any, **kwargs: t.Any) -> "MockRedisClient":
        return cls(*args, **kwargs)


class MockRedisCluster:
    """Mock for Redis Cluster."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        # Create the mock attributes directly
        self.ping = AsyncMock()
        self.close = AsyncMock()

    @classmethod
    def from_url(cls, *args: t.Any, **kwargs: t.Any) -> "MockRedisCluster":
        return cls(*args, **kwargs)


class MockTrackingCache(MagicMock):
    """Mock for Redis TrackingCache."""

    pass


class MockPickleSerializer(MagicMock):
    """Mock for PickleSerializer."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.dumps = MagicMock(return_value=b"serialized_data")
        self.loads = MagicMock(return_value={"key": "value"})


class TestRedisSettings:
    """Test Redis Cache settings."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for settings testing."""
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app
        mock_config.deployed = False

        # Mock logger to avoid logger config issues
        mock_logger = MagicMock()
        mock_logger.verbose = False
        mock_config.logger = mock_logger

        return mock_config

    def test_default_settings(self, mock_config):
        """Test settings initialization with default values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = CacheSettings()

        # Test Redis-specific defaults
        assert settings.local_host == "127.0.0.1"
        assert settings.port == 6379
        assert settings.cluster is False

        # Test inherited defaults from CacheBaseSettings
        assert (
            settings.host.get_secret_value() == "127.0.0.1"
        )  # Uses local_host when not deployed
        assert settings.db == 0
        assert settings.password is None  # Default password is None

    def test_custom_settings(self, mock_config):
        """Test settings with custom values (defaults to not deployed)."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = CacheSettings(
                port=6380,
                password=SecretStr("prod-password"),
                cluster=True,
            )

        # When not deployed, host defaults to local_host
        assert settings.host.get_secret_value() == "127.0.0.1"
        assert settings.port == 6380
        assert settings.password.get_secret_value() == "prod-password"
        assert settings.cluster is True

    def test_connection_string_building_defaults(self, mock_config):
        """Test connection string building with default host."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = CacheSettings(
                port=6379,
                password=SecretStr("redispass"),
                db=1,
                ssl_enabled=False,
            )

        # Should use local_host when not deployed
        expected = "redis://:redispass@127.0.0.1:6379/1"
        assert settings.connection_string == expected

    def test_connection_string_with_ssl_defaults(self, mock_config):
        """Test connection string building with SSL using defaults."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = CacheSettings(
                port=6380,
                user=SecretStr("redisuser"),
                password=SecretStr("redispass"),
                db=2,
                ssl_enabled=True,
            )

        # Should use local_host when not deployed
        expected = "rediss://redisuser:redispass@127.0.0.1:6380/2"
        assert settings.connection_string == expected

    def test_connection_string_with_auth_token_defaults(self, mock_config):
        """Test connection string building with auth token using defaults."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = CacheSettings(
                port=6379,
                auth_token=SecretStr("auth-token-123"),
                db=0,
                ssl_enabled=True,
            )

        # Should use local_host when not deployed
        expected = "rediss://:auth-token-123@127.0.0.1:6379/0"
        assert settings.connection_string == expected


class TestRedisCache:
    """Test Redis Cache adapter."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for testing."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app

        # Mock cache settings
        mock_cache = MagicMock(spec=CacheSettings)
        mock_cache.host = SecretStr("127.0.0.1")
        mock_cache.port = 6379
        mock_cache.db = 0
        mock_cache.user = None
        mock_cache.password = SecretStr("redispass")
        mock_cache.auth_token = None
        mock_cache.connection_string = "redis://:redispass@127.0.0.1:6379/0"
        mock_cache.cluster = False
        mock_cache.ssl_enabled = False
        mock_cache.ssl_cert_path = None
        mock_cache.ssl_key_path = None
        mock_cache.ssl_ca_path = None
        mock_cache.ssl_verify_mode = "required"
        mock_cache.connect_timeout = 5.0
        mock_cache.max_connections = 20
        mock_cache.health_check_interval = 30
        mock_cache.retry_on_timeout = True
        mock_config.cache = mock_cache

        return mock_config

    @pytest.fixture
    def mock_ssl_config(self):
        """Mock config with SSL enabled."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app

        # Mock cache settings with SSL
        mock_cache = MagicMock(spec=CacheSettings)
        mock_cache.host = SecretStr("redis.example.com")
        mock_cache.port = 6380
        mock_cache.db = 0
        mock_cache.user = SecretStr("redisuser")
        mock_cache.password = SecretStr("redispass")
        mock_cache.connection_string = (
            "rediss://redisuser:redispass@redis.example.com:6380/0"
        )
        mock_cache.cluster = False
        mock_cache.ssl_enabled = True
        mock_cache.ssl_cert_path = "/path/to/cert.pem"
        mock_cache.ssl_key_path = "/path/to/key.pem"
        mock_cache.ssl_ca_path = "/path/to/ca.pem"
        mock_cache.ssl_verify_mode = "required"
        mock_cache.connect_timeout = 5.0
        mock_cache.max_connections = 20
        mock_cache.health_check_interval = 30
        mock_cache.retry_on_timeout = True

        # Mock SSL config object with dynamic behavior
        mock_ssl_config = MagicMock()

        def mock_to_redis_kwargs():
            verify_mode = mock_cache.ssl_verify_mode
            return {
                "ssl": True,
                "ssl_certfile": "/path/to/cert.pem",
                "ssl_keyfile": "/path/to/key.pem",
                "ssl_ca_certs": "/path/to/ca.pem",
                "ssl_check_hostname": verify_mode == "required",
                "ssl_cert_reqs": verify_mode,
            }

        mock_ssl_config.to_redis_kwargs.side_effect = mock_to_redis_kwargs
        mock_cache.ssl_config = mock_ssl_config

        mock_config.cache = mock_cache

        return mock_config

    @pytest.fixture
    def redis_cache(self, mock_config):
        """Redis cache adapter for testing."""
        cache = Cache()
        cache.config = mock_config
        cache.logger = MagicMock()
        return cache

    @pytest.fixture
    def redis_ssl_cache(self, mock_ssl_config):
        """Redis cache adapter with SSL for testing."""
        cache = Cache()
        cache.config = mock_ssl_config
        cache.logger = MagicMock()
        return cache

    def test_adapter_initialization(self, redis_cache):
        """Test adapter initialization."""
        assert redis_cache._client is None
        assert redis_cache._redis_backend is None
        assert hasattr(redis_cache, "config")
        assert hasattr(redis_cache, "logger")

    def test_adapter_initialization_with_url(self):
        """Test adapter initialization with redis_url."""
        cache = Cache(redis_url="redis://localhost:6379/1")
        assert cache.redis_url == "redis://localhost:6379/1"

    def test_build_ssl_kwargs(self, redis_ssl_cache):
        """Test SSL kwargs building."""
        ssl_kwargs = redis_ssl_cache._build_ssl_kwargs()

        assert ssl_kwargs["ssl"] is True
        assert ssl_kwargs["ssl_certfile"] == "/path/to/cert.pem"
        assert ssl_kwargs["ssl_keyfile"] == "/path/to/key.pem"
        assert ssl_kwargs["ssl_ca_certs"] == "/path/to/ca.pem"
        assert ssl_kwargs["ssl_check_hostname"] is True
        assert ssl_kwargs["ssl_cert_reqs"] == "required"

    def test_build_ssl_kwargs_optional_mode(self, redis_ssl_cache):
        """Test SSL kwargs with optional verification."""
        redis_ssl_cache.config.cache.ssl_verify_mode = "optional"

        ssl_kwargs = redis_ssl_cache._build_ssl_kwargs()

        assert ssl_kwargs["ssl_check_hostname"] is False
        assert ssl_kwargs["ssl_cert_reqs"] == "optional"

    def test_build_ssl_kwargs_none_mode(self, redis_ssl_cache):
        """Test SSL kwargs with no verification."""
        redis_ssl_cache.config.cache.ssl_verify_mode = "none"

        ssl_kwargs = redis_ssl_cache._build_ssl_kwargs()

        assert ssl_kwargs["ssl_check_hostname"] is False
        assert ssl_kwargs["ssl_cert_reqs"] == "none"

    def test_build_ssl_kwargs_disabled(self, redis_cache):
        """Test SSL kwargs when SSL is disabled."""
        ssl_kwargs = redis_cache._build_ssl_kwargs()
        assert ssl_kwargs == {}

    async def test_create_client_from_connection_string(self, redis_cache):
        """Test client creation from connection string."""
        mock_redis = MockRedisClient()
        MockTrackingCache()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
            patch.object(
                MockRedisClient, "from_url", return_value=mock_redis
            ) as mock_from_url,
        ):
            client = await redis_cache._create_client()

            mock_from_url.assert_called_once()
            call_args = mock_from_url.call_args
            assert call_args[0][0] == "redis://:redispass@127.0.0.1:6379/0"
            assert "client_name" in call_args[1]
            assert call_args[1]["client_name"] == "testapp"
            assert "cache" in call_args[1]
            assert call_args[1]["decode_responses"] is False
            assert client == mock_redis

    async def test_create_client_cluster_mode(self, redis_cache):
        """Test client creation in cluster mode."""
        redis_cache.config.cache.cluster = True
        mock_cluster = MockRedisCluster()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
            patch.object(
                MockRedisCluster, "from_url", return_value=mock_cluster
            ) as mock_from_url,
        ):
            client = await redis_cache._create_client()

            mock_from_url.assert_called_once()
            redis_cache.logger.info.assert_called_with("RedisCluster mode enabled")
            assert client == mock_cluster

    async def test_create_client_without_connection_string(self, redis_cache):
        """Test client creation without connection string."""
        redis_cache.config.cache.connection_string = None
        mock_redis = MockRedisClient()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
            patch.object(
                MockRedisClient, "__new__", return_value=mock_redis
            ) as mock_redis_new,
        ):
            client = await redis_cache._create_client()

            # Verify Redis constructor was called
            mock_redis_new.assert_called()
            # Verify the client is the mock we provided
            assert client is mock_redis

    async def test_create_client_with_ssl(self, redis_ssl_cache):
        """Test client creation with SSL configuration."""
        mock_redis = MockRedisClient()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
            patch.object(
                MockRedisClient, "from_url", return_value=mock_redis
            ) as mock_from_url,
        ):
            await redis_ssl_cache._create_client()

            call_kwargs = mock_from_url.call_args[1]
            assert "ssl" in call_kwargs
            assert call_kwargs["ssl"] is True
            assert "ssl_certfile" in call_kwargs
            assert "ssl_keyfile" in call_kwargs
            assert "ssl_ca_certs" in call_kwargs

    async def test_create_client_import_error(self, redis_cache):
        """Test client creation when Redis imports fail."""
        with patch("acb.adapters.cache.redis._get_redis_imports", return_value={}):
            with pytest.raises(ImportError, match="Redis dependencies not available"):
                await redis_cache._create_client()

    async def test_get_client(self, redis_cache):
        """Test get_client method."""
        mock_client = MockRedisClient()

        with patch.object(redis_cache, "_ensure_client", return_value=mock_client):
            client = await redis_cache.get_client()
            assert client == mock_client

    async def test_close(self, redis_cache):
        """Test close method."""
        mock_client = MockRedisClient()
        redis_cache._client = mock_client

        await redis_cache._close()
        mock_client.close.assert_called_once()

    async def test_close_no_client(self, redis_cache):
        """Test close method when no client exists."""
        await redis_cache._close()
        # Should not raise an exception

    async def test_clear_without_namespace(self, redis_cache):
        """Test clear method without namespace."""
        mock_client = MockRedisClient()
        mock_client.keys.return_value = ["testapp:key1", "testapp:key2"]

        with patch.object(redis_cache, "get_client", return_value=mock_client):
            result = await redis_cache._clear()

            mock_client.keys.assert_called_once_with("testapp:*")
            assert mock_client.unlink.call_count == 2
            assert result is True

    async def test_clear_with_namespace(self, redis_cache):
        """Test clear method with namespace."""
        mock_client = MockRedisClient()
        mock_client.keys.return_value = ["testapp:users:key1"]

        with patch.object(redis_cache, "get_client", return_value=mock_client):
            result = await redis_cache._clear(namespace="users")

            mock_client.keys.assert_called_once_with("testapp:users:*")
            mock_client.unlink.assert_called_once_with(("testapp:users:key1",))
            assert result is True

    async def test_clear_no_keys(self, redis_cache):
        """Test clear method when no keys match."""
        mock_client = MockRedisClient()
        mock_client.keys.return_value = []

        with patch.object(redis_cache, "get_client", return_value=mock_client):
            result = await redis_cache._clear()

            mock_client.keys.assert_called_once_with("testapp:*")
            mock_client.unlink.assert_not_called()
            assert result is True

    async def test_exists_true(self, redis_cache):
        """Test exists method when key exists."""
        mock_client = MockRedisClient()
        mock_client.exists.return_value = 1

        with patch.object(redis_cache, "get_client", return_value=mock_client):
            result = await redis_cache._exists("test_key")

            mock_client.exists.assert_called_once_with(["test_key"])
            assert result is True

    async def test_exists_false(self, redis_cache):
        """Test exists method when key doesn't exist."""
        mock_client = MockRedisClient()
        mock_client.exists.return_value = 0

        with patch.object(redis_cache, "get_client", return_value=mock_client):
            result = await redis_cache._exists("test_key")

            mock_client.exists.assert_called_once_with(["test_key"])
            assert result is False

    async def test_init_with_connection_string(self, redis_cache):
        """Test initialization with connection string."""
        mock_client = MockRedisClient()
        mock_serializer = MockPickleSerializer()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch.object(redis_cache, "get_client", return_value=mock_client),
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
            patch.object(redis_cache, "_setup_serializer"),
        ):
            # Set the mock serializer directly
            redis_cache._serializer = mock_serializer

            await redis_cache.init()

            mock_client.ping.assert_called_once()
            assert redis_cache._namespace == "testapp:"
            assert redis_cache._serializer == mock_serializer
            redis_cache.logger.info.assert_called()

    async def test_init_without_connection_string(self, redis_cache):
        """Test initialization without connection string."""
        redis_cache.config.cache.connection_string = None
        mock_client = MockRedisClient()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch.object(redis_cache, "get_client", return_value=mock_client),
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
        ):
            await redis_cache.init()

            mock_client.ping.assert_called_once()
            redis_cache.logger.info.assert_called()

    async def test_init_with_masked_password(self, redis_cache):
        """Test initialization logs masked password."""
        redis_cache.config.cache.connection_string = (
            "redis://user:password123@redis.com:6379/0"
        )
        mock_client = MockRedisClient()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch.object(redis_cache, "get_client", return_value=mock_client),
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
        ):
            await redis_cache.init()

            # Check that password was masked in logs
            log_calls = [
                call.args[0] for call in redis_cache.logger.info.call_args_list
            ]
            connection_log = next(
                (
                    call
                    for call in log_calls
                    if "Initializing Redis cache connection to" in call
                ),
                None,
            )
            assert connection_log is not None
            assert "***" in connection_log
            assert "password123" not in connection_log

    async def test_init_failure(self, redis_cache):
        """Test initialization failure handling."""
        mock_client = MockRedisClient()
        mock_client.ping.side_effect = Exception("Connection refused")

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch.object(redis_cache, "get_client", return_value=mock_client),
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
        ):
            with pytest.raises(Exception, match="Connection refused"):
                await redis_cache.init()

            redis_cache.logger.exception.assert_called_once()

    async def test_init_with_kwargs(self, redis_cache):
        """Test initialization with additional kwargs."""
        mock_client = MockRedisClient()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch.object(redis_cache, "get_client", return_value=mock_client),
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
        ):
            await redis_cache.init(custom_param="value", another_param=123)

            assert redis_cache._init_kwargs["custom_param"] == "value"
            assert redis_cache._init_kwargs["another_param"] == 123

    def test_get_redis_imports_success(self):
        """Test successful Redis imports."""
        mock_redis_backend = MagicMock()
        mock_pickle_serializer = MagicMock()
        mock_tracking_cache = MagicMock()
        mock_redis = MagicMock()
        mock_redis_cluster = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "aiocache.backends.redis": MagicMock(RedisBackend=mock_redis_backend),
                "aiocache.serializers": MagicMock(
                    PickleSerializer=mock_pickle_serializer
                ),
                "coredis.cache": MagicMock(TrackingCache=mock_tracking_cache),
                "coredis.client": MagicMock(
                    Redis=mock_redis, RedisCluster=mock_redis_cluster
                ),
            },
        ):
            # Clear the imports cache first
            from acb.adapters.cache.redis import _redis_imports

            _redis_imports.clear()

            from acb.adapters.cache.redis import _get_redis_imports

            imports = _get_redis_imports()

            assert "RedisBackend" in imports
            assert "PickleSerializer" in imports
            assert "TrackingCache" in imports
            assert "Redis" in imports
            assert "RedisCluster" in imports

    def test_get_redis_imports_failure(self):
        """Test Redis imports failure."""
        # Clear the imports cache first
        from acb.adapters.cache.redis import _redis_imports

        _redis_imports.clear()

        with (
            patch.dict(
                "sys.modules",
                {
                    "aiocache.backends.redis": None,
                    "aiocache.serializers": None,
                    "coredis.cache": None,
                    "coredis.client": None,
                },
            ),
            patch("acb.adapters.cache.redis.debug") as mock_debug,
        ):
            from acb.adapters.cache.redis import _get_redis_imports

            imports = _get_redis_imports()

            assert imports == {}
            mock_debug.assert_called_once()

    def test_module_metadata(self):
        """Test module metadata constants."""
        from uuid import UUID

        from acb.adapters import AdapterStatus
        from acb.adapters.cache.redis import MODULE_ID, MODULE_METADATA, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE
        assert MODULE_METADATA.name == "Redis Cache"
        assert MODULE_METADATA.category == "cache"
        assert MODULE_METADATA.provider == "redis"

    def test_depends_registration(self):
        """Test that Cache class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        cache_class = depends.get(Cache)
        assert cache_class is not None

    def test_inheritance_structure(self):
        """Test that Redis cache properly inherits from CacheBase."""
        from acb.adapters.cache._base import CacheBase

        cache = Cache()

        # Test inheritance
        assert isinstance(cache, CacheBase)

        # Test that required methods exist
        assert hasattr(cache, "get_client")
        assert hasattr(cache, "init")
        assert hasattr(cache, "_close")
        assert hasattr(cache, "_clear")
        assert hasattr(cache, "_exists")

    async def test_comprehensive_workflow(self, redis_cache):
        """Test comprehensive Redis cache workflow."""
        mock_client = MockRedisClient()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch.object(redis_cache, "get_client", return_value=mock_client),
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
        ):
            # Initialize cache
            await redis_cache.init()
            mock_client.ping.assert_called_once()

            # Test namespace is set
            assert redis_cache._namespace == "testapp:"

            # Test serializer is set
            assert redis_cache._serializer is not None

            # Test exists check
            mock_client.exists.return_value = 0
            exists = await redis_cache._exists("test_key")
            assert exists is False

            # Test clear operation
            mock_client.keys.return_value = ["testapp:key1", "testapp:key2"]
            await redis_cache._clear()
            mock_client.keys.assert_called_with("testapp:*")
            assert mock_client.unlink.call_count == 2

            # Test close
            # Set the _client attribute to the mock client so _close can access it
            redis_cache._client = mock_client
            await redis_cache._close()
            mock_client.close.assert_called_once()

            # Verify all operations completed successfully
            redis_cache.logger.info.assert_called()

    async def test_cluster_configuration_workflow(self, redis_cache):
        """Test Redis cluster configuration workflow."""
        redis_cache.config.cache.cluster = True
        mock_cluster = MockRedisCluster()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
            patch.object(MockRedisCluster, "from_url", return_value=mock_cluster),
        ):
            # Create client in cluster mode
            client = await redis_cache._create_client()

            # Verify cluster mode was logged
            redis_cache.logger.info.assert_called_with("RedisCluster mode enabled")
            assert client == mock_cluster

    async def test_ssl_configuration_workflow(self, redis_ssl_cache):
        """Test SSL configuration workflow."""
        mock_client = MockRedisClient()

        mock_imports = {
            "Redis": MockRedisClient,
            "RedisCluster": MockRedisCluster,
            "TrackingCache": MockTrackingCache,
            "PickleSerializer": MockPickleSerializer,
        }

        with (
            patch(
                "acb.adapters.cache.redis._get_redis_imports", return_value=mock_imports
            ),
            patch.object(
                MockRedisClient, "from_url", return_value=mock_client
            ) as mock_from_url,
            patch.object(redis_ssl_cache, "get_client", return_value=mock_client),
        ):
            # Create client with SSL
            await redis_ssl_cache._create_client()

            # Verify SSL kwargs were included
            call_kwargs = mock_from_url.call_args[1]
            assert call_kwargs["ssl"] is True
            assert "ssl_certfile" in call_kwargs
            assert "ssl_keyfile" in call_kwargs
            assert "ssl_ca_certs" in call_kwargs
            assert call_kwargs["ssl_check_hostname"] is True

            # Initialize with SSL
            await redis_ssl_cache.init()
            mock_client.ping.assert_called_once()
            redis_ssl_cache.logger.info.assert_called()

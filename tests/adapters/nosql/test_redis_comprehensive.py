"""Comprehensive tests for Redis NoSQL adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typing as t
from pydantic import SecretStr

from acb.adapters.nosql.redis import Nosql, NosqlSettings
from acb.config import Config


class MockRedisClient(MagicMock):
    """Mock for Redis Client."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.ping = AsyncMock()
        self.keys = AsyncMock()
        self.hgetall = AsyncMock()
        self.hset = AsyncMock()
        self.sadd = AsyncMock()
        self.srem = AsyncMock()
        self.scard = AsyncMock()
        self.delete = AsyncMock()
        self.incr = AsyncMock()
        self.pipeline = MagicMock()
        self.from_url = classmethod(lambda cls, *args, **kwargs: cls())


class MockRedisPipeline(MagicMock):
    """Mock for Redis Pipeline."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.execute = AsyncMock()
        self.discard = AsyncMock()


class MockMigrator(MagicMock):
    """Mock for Redis-OM Migrator."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.run = MagicMock()


class TestRedisNosqlSettings:
    """Test Redis NoSQL settings."""

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
            settings = NosqlSettings()

        # Test Redis-specific defaults
        assert settings.port == 6379
        assert settings.db == 0
        assert settings.cache_db == 0
        assert settings.decode_responses is True
        assert settings.encoding == "utf-8"

        # Test inherited defaults from NosqlBaseSettings
        assert settings.database == "testapp"
        assert settings.collection_prefix == "testapp_"
        assert settings.connection_string == "redis://127.0.0.1:6379/0"

    def test_custom_settings(self, mock_config):
        """Test settings initialization with custom values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                host=SecretStr("redis.example.com"),
                port=6380,
                user=SecretStr("redisuser"),
                password=SecretStr("redispass"),
                db=1,
                cache_db=5,
                decode_responses=False,
                encoding="latin-1",
                ssl_enabled=True,
                ssl_cert_path="/path/to/cert.pem",
                ssl_key_path="/path/to/key.pem",
                ssl_ca_path="/path/to/ca.pem",
            )

        assert settings.host.get_secret_value() == "redis.example.com"
        assert settings.port == 6380
        assert settings.user.get_secret_value() == "redisuser"
        assert settings.password.get_secret_value() == "redispass"
        assert settings.db == 1
        assert settings.cache_db == 5
        assert settings.decode_responses is False
        assert settings.encoding == "latin-1"
        assert settings.ssl_enabled is True

    def test_connection_string_building_redis(self, mock_config):
        """Test connection string building for Redis protocol."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                host=SecretStr("redis.example.com"),
                port=6379,
                password=SecretStr("redispass"),
                db=1,
                ssl_enabled=False,
            )

        expected = "redis://:redispass@redis.example.com:6379/1"
        assert settings.connection_string == expected

    def test_connection_string_building_rediss(self, mock_config):
        """Test connection string building for Redis SSL protocol."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                host=SecretStr("redis.example.com"),
                port=6380,
                user=SecretStr("redisuser"),
                password=SecretStr("redispass"),
                db=2,
                ssl_enabled=True,
            )

        expected = "rediss://redisuser:redispass@redis.example.com:6380/2"
        assert settings.connection_string == expected

    def test_connection_string_with_auth_token(self, mock_config):
        """Test connection string building with auth token."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = NosqlSettings(
                host=SecretStr("redis.example.com"),
                port=6379,
                auth_token=SecretStr("auth-token-123"),
                db=0,
                ssl_enabled=True,
            )

        expected = "rediss://:auth-token-123@redis.example.com:6379/0"
        assert settings.connection_string == expected

    def test_cache_db_validator_success(self, mock_config):
        """Test cache_db validator with valid values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            # Valid values: 0 and > 3
            settings1 = NosqlSettings(cache_db=0)
            assert settings1.cache_db == 0

            settings2 = NosqlSettings(cache_db=5)
            assert settings2.cache_db == 0  # Always returns 0

    def test_cache_db_validator_failure(self, mock_config):
        """Test cache_db validator with invalid values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            # Invalid values: 1, 2 (reserved)
            with pytest.raises(ValueError, match="must be > 3"):
                NosqlSettings(cache_db=1)

            with pytest.raises(ValueError, match="must be > 3"):
                NosqlSettings(cache_db=2)


class TestRedisNosql:
    """Test Redis NoSQL adapter."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for testing."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app

        # Mock nosql settings
        mock_nosql = MagicMock(spec=NosqlSettings)
        mock_nosql.host = SecretStr("127.0.0.1")
        mock_nosql.port = 6379
        mock_nosql.db = 0
        mock_nosql.user = None
        mock_nosql.password = SecretStr("redispass")
        mock_nosql.auth_token = None
        mock_nosql.connection_string = "redis://:redispass@127.0.0.1:6379/0"
        mock_nosql.ssl_enabled = False
        mock_nosql.ssl_cert_path = None
        mock_nosql.ssl_key_path = None
        mock_nosql.ssl_ca_path = None
        mock_nosql.ssl_verify_mode = "required"
        mock_nosql.ssl_ciphers = None
        mock_nosql.connect_timeout = 5.0
        mock_nosql.socket_timeout = 5.0
        mock_nosql.max_pool_size = 100
        mock_nosql.decode_responses = True
        mock_nosql.encoding = "utf-8"
        mock_nosql.collection_prefix = "testapp_"
        mock_config.nosql = mock_nosql

        return mock_config

    @pytest.fixture
    def mock_ssl_config(self):
        """Mock config with SSL enabled."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app

        # Mock nosql settings with SSL
        mock_nosql = MagicMock(spec=NosqlSettings)
        mock_nosql.host = SecretStr("redis.example.com")
        mock_nosql.port = 6380
        mock_nosql.db = 0
        mock_nosql.user = SecretStr("redisuser")
        mock_nosql.password = SecretStr("redispass")
        mock_nosql.connection_string = (
            "rediss://redisuser:redispass@redis.example.com:6380/0"
        )
        mock_nosql.ssl_enabled = True
        mock_nosql.ssl_cert_path = "/path/to/cert.pem"
        mock_nosql.ssl_key_path = "/path/to/key.pem"
        mock_nosql.ssl_ca_path = "/path/to/ca.pem"
        mock_nosql.ssl_verify_mode = "required"
        mock_nosql.ssl_ciphers = "ECDHE+AESGCM"
        mock_nosql.connect_timeout = 5.0
        mock_nosql.socket_timeout = 5.0
        mock_nosql.max_pool_size = 100
        mock_nosql.decode_responses = True
        mock_nosql.encoding = "utf-8"
        mock_nosql.collection_prefix = "testapp_"
        mock_config.nosql = mock_nosql

        return mock_config

    @pytest.fixture
    def redis_nosql(self, mock_config):
        """Redis NoSQL adapter for testing."""
        adapter = Nosql()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def redis_ssl_nosql(self, mock_ssl_config):
        """Redis NoSQL adapter with SSL for testing."""
        adapter = Nosql()
        adapter.config = mock_ssl_config
        adapter.logger = MagicMock()
        return adapter

    def test_adapter_initialization(self, redis_nosql):
        """Test adapter initialization."""
        assert redis_nosql._models == {}
        assert redis_nosql._client is None
        assert redis_nosql._transaction is None
        assert hasattr(redis_nosql, "config")
        assert hasattr(redis_nosql, "logger")

    def test_build_ssl_kwargs(self, redis_ssl_nosql):
        """Test SSL kwargs building."""
        ssl_kwargs = redis_ssl_nosql._build_ssl_kwargs()

        assert ssl_kwargs["ssl"] is True
        assert ssl_kwargs["ssl_certfile"] == "/path/to/cert.pem"
        assert ssl_kwargs["ssl_keyfile"] == "/path/to/key.pem"
        assert ssl_kwargs["ssl_ca_certs"] == "/path/to/ca.pem"
        assert ssl_kwargs["ssl_check_hostname"] is True
        assert ssl_kwargs["ssl_cert_reqs"] == "required"
        assert ssl_kwargs["ssl_ciphers"] == "ECDHE+AESGCM"
        assert ssl_kwargs["socket_connect_timeout"] == 5.0
        assert ssl_kwargs["socket_timeout"] == 5.0
        assert ssl_kwargs["max_connections"] == 100

    def test_build_ssl_kwargs_optional_mode(self, redis_ssl_nosql):
        """Test SSL kwargs with optional verification."""
        redis_ssl_nosql.config.nosql.ssl_verify_mode = "optional"

        ssl_kwargs = redis_ssl_nosql._build_ssl_kwargs()

        assert ssl_kwargs["ssl_check_hostname"] is False
        assert ssl_kwargs["ssl_cert_reqs"] == "optional"

    def test_build_ssl_kwargs_none_mode(self, redis_ssl_nosql):
        """Test SSL kwargs with no verification."""
        redis_ssl_nosql.config.nosql.ssl_verify_mode = "none"

        ssl_kwargs = redis_ssl_nosql._build_ssl_kwargs()

        assert ssl_kwargs["ssl_check_hostname"] is False
        assert ssl_kwargs["ssl_cert_reqs"] == "none"

    def test_build_ssl_kwargs_disabled(self, redis_nosql):
        """Test SSL kwargs when SSL is disabled."""
        ssl_kwargs = redis_nosql._build_ssl_kwargs()
        # Should still include connection timeouts and pool size
        assert "ssl" not in ssl_kwargs
        assert ssl_kwargs["socket_connect_timeout"] == 5.0
        assert ssl_kwargs["socket_timeout"] == 5.0
        assert ssl_kwargs["max_connections"] == 100

    def test_client_property(self, redis_nosql):
        """Test client property creation."""
        with patch("acb.adapters.nosql.redis.redis.from_url") as mock_from_url:
            mock_client = MockRedisClient()
            mock_from_url.return_value = mock_client

            client = redis_nosql.client

            mock_from_url.assert_called_once_with(
                "redis://:redispass@127.0.0.1:6379/0",
                decode_responses=True,
                encoding="utf-8",
                socket_connect_timeout=5.0,
                socket_timeout=5.0,
                max_connections=100,
            )
            assert redis_nosql._client == mock_client
            assert client == mock_client

            # Test caching
            client2 = redis_nosql.client
            assert client == client2
            assert mock_from_url.call_count == 1

    def test_client_property_with_ssl(self, redis_ssl_nosql):
        """Test client property with SSL configuration."""
        with patch("acb.adapters.nosql.redis.redis.from_url") as mock_from_url:
            mock_client = MockRedisClient()
            mock_from_url.return_value = mock_client

            call_kwargs = mock_from_url.call_args[1]
            assert call_kwargs["ssl"] is True
            assert call_kwargs["ssl_certfile"] == "/path/to/cert.pem"
            assert call_kwargs["ssl_keyfile"] == "/path/to/key.pem"
            assert call_kwargs["ssl_ca_certs"] == "/path/to/ca.pem"

    def test_om_client_property(self, redis_nosql):
        """Test Redis-OM client property creation."""
        with patch(
            "acb.adapters.nosql.redis.get_redis_connection"
        ) as mock_get_connection:
            mock_client = MockRedisClient()
            mock_get_connection.return_value = mock_client

            client = redis_nosql.om_client

            mock_get_connection.assert_called_once_with(
                url="redis://:redispass@127.0.0.1:6379/0",
                decode_responses=True,
                socket_connect_timeout=5.0,
                socket_timeout=5.0,
                max_connections=100,
            )
            assert client == mock_client

    async def test_init_success(self, redis_nosql):
        """Test successful initialization."""
        mock_client = MockRedisClient()
        mock_migrator = MockMigrator()

        with (
            patch.object(redis_nosql, "client", mock_client),
            patch("acb.adapters.nosql.redis.Migrator", return_value=mock_migrator),
        ):
            await redis_nosql.init()

            mock_client.ping.assert_called_once()
            mock_migrator.run.assert_called_once()
            redis_nosql.logger.info.assert_any_call(
                "Initializing Redis connection to redis://:redispass@127.0.0.1:6379/0"
            )
            redis_nosql.logger.info.assert_any_call(
                "Redis connection initialized successfully"
            )

    async def test_init_failure(self, redis_nosql):
        """Test initialization failure handling."""
        mock_client = MockRedisClient()
        mock_client.ping.side_effect = Exception("Connection refused")

        with patch.object(redis_nosql, "client", mock_client):
            with pytest.raises(Exception, match="Connection refused"):
                await redis_nosql.init()

            redis_nosql.logger.exception.assert_called_once()

    def test_get_key_with_id(self, redis_nosql):
        """Test key generation with ID."""
        key = redis_nosql._get_key("users", "123")
        assert key == "testapp_users:123"

    def test_get_key_without_id(self, redis_nosql):
        """Test key generation without ID."""
        key = redis_nosql._get_key("users")
        assert key == "testapp_users"

    def test_matches_filter_empty(self, redis_nosql):
        """Test filter matching with empty filter."""
        data = {"name": "John", "age": 30}
        assert redis_nosql._matches_filter(data, {}) is True

    def test_matches_filter_success(self, redis_nosql):
        """Test filter matching success."""
        data = {"name": "John", "age": 30, "city": "New York"}
        filter_dict = {"name": "John", "age": 30}
        assert redis_nosql._matches_filter(data, filter_dict) is True

    def test_matches_filter_failure(self, redis_nosql):
        """Test filter matching failure."""
        data = {"name": "John", "age": 30}
        filter_dict = {"name": "Jane", "age": 30}
        assert redis_nosql._matches_filter(data, filter_dict) is False

    def test_matches_filter_missing_key(self, redis_nosql):
        """Test filter matching with missing key."""
        data = {"name": "John"}
        filter_dict = {"name": "John", "age": 30}
        assert redis_nosql._matches_filter(data, filter_dict) is False

    async def test_find_simple(self, redis_nosql):
        """Test find method with simple filter."""
        mock_client = MockRedisClient()
        mock_client.keys.return_value = [b"testapp_users:1", b"testapp_users:2"]
        mock_client.hgetall.side_effect = [
            {b"name": b"John", b"age": b"30"},
            {b"name": b"Jane", b"age": b"25"},
        ]

        with patch.object(redis_nosql, "client", mock_client):
            results = await redis_nosql.find("users", {"name": "John"})

            mock_client.keys.assert_called_once_with("testapp_users:*")
            assert mock_client.hgetall.call_count == 2

            # Should return only matching documents
            assert len(results) == 1
            assert results[0]["name"] == "John"
            assert results[0]["age"] == "30"
            assert results[0]["_id"] == "1"

    async def test_find_with_limit(self, redis_nosql):
        """Test find method with limit."""
        mock_client = MockRedisClient()
        mock_client.keys.return_value = [
            b"testapp_users:1",
            b"testapp_users:2",
            b"testapp_users:3",
        ]
        mock_client.hgetall.side_effect = [{b"name": b"John"}, {b"name": b"Jane"}]

        with patch.object(redis_nosql, "client", mock_client):
            await redis_nosql.find("users", {}, limit=2)

            # Should limit keys before fetching data
            assert mock_client.hgetall.call_count == 2

    async def test_find_with_string_keys(self, redis_nosql):
        """Test find method with string keys and values."""
        mock_client = MockRedisClient()
        mock_client.keys.return_value = ["testapp_users:1"]
        mock_client.hgetall.return_value = {"name": "John", "age": "30"}

        with patch.object(redis_nosql, "client", mock_client):
            results = await redis_nosql.find("users", {})

            assert len(results) == 1
            assert results[0]["name"] == "John"
            assert results[0]["_id"] == "1"

    async def test_find_one_by_id(self, redis_nosql):
        """Test find_one method with _id filter."""
        mock_client = MockRedisClient()
        mock_client.hgetall.return_value = {b"name": b"John", b"age": b"30"}

        with patch.object(redis_nosql, "client", mock_client):
            result = await redis_nosql.find_one("users", {"_id": "123"})

            mock_client.hgetall.assert_called_once_with("testapp_users:123")
            assert result["name"] == "John"
            assert result["age"] == "30"
            assert result["_id"] == "123"

    async def test_find_one_by_id_not_found(self, redis_nosql):
        """Test find_one method with _id filter when document doesn't exist."""
        mock_client = MockRedisClient()
        mock_client.hgetall.return_value = {}

        with patch.object(redis_nosql, "client", mock_client):
            result = await redis_nosql.find_one("users", {"_id": "123"})

            assert result is None

    async def test_find_one_by_filter(self, redis_nosql):
        """Test find_one method with regular filter."""
        with patch.object(redis_nosql, "find") as mock_find:
            mock_find.return_value = [{"name": "John", "_id": "123"}]

            result = await redis_nosql.find_one("users", {"name": "John"})

            mock_find.assert_called_once_with("users", {"name": "John"}, limit=1)
            assert result == {"name": "John", "_id": "123"}

    async def test_find_one_not_found(self, redis_nosql):
        """Test find_one method when no documents found."""
        with patch.object(redis_nosql, "find") as mock_find:
            mock_find.return_value = []

            result = await redis_nosql.find_one("users", {"name": "NonExistent"})

            assert result is None

    async def test_insert_one_with_id(self, redis_nosql):
        """Test insert_one method with _id specified."""
        mock_client = MockRedisClient()

        with patch.object(redis_nosql, "client", mock_client):
            result = await redis_nosql.insert_one(
                "users", {"_id": "123", "name": "John"}
            )

            mock_client.hset.assert_called_once_with(
                "testapp_users:123", mapping={"name": "John"}
            )
            mock_client.sadd.assert_called_once_with("testapp_users", "123")
            assert result == "123"

    async def test_insert_one_without_id(self, redis_nosql):
        """Test insert_one method without _id specified."""
        mock_client = MockRedisClient()
        mock_client.incr.return_value = 456

        with patch.object(redis_nosql, "client", mock_client):
            result = await redis_nosql.insert_one("users", {"name": "John"})

            mock_client.incr.assert_called_once_with("users:id_counter")
            mock_client.hset.assert_called_once_with(
                "testapp_users:456", mapping={"name": "John"}
            )
            mock_client.sadd.assert_called_once_with("testapp_users", "456")
            assert result == "456"

    async def test_insert_many(self, redis_nosql):
        """Test insert_many method."""
        documents = [{"_id": "1", "name": "John"}, {"name": "Jane"}]

        with patch.object(redis_nosql, "insert_one") as mock_insert_one:
            mock_insert_one.side_effect = ["1", "2"]

            result = await redis_nosql.insert_many("users", documents)

            assert mock_insert_one.call_count == 2
            assert result == ["1", "2"]

    async def test_update_one_success(self, redis_nosql):
        """Test update_one method when document found."""
        mock_client = MockRedisClient()

        with patch.object(redis_nosql, "find_one") as mock_find_one:
            mock_find_one.return_value = {"_id": "123", "name": "John"}

            with patch.object(redis_nosql, "client", mock_client):
                result = await redis_nosql.update_one(
                    "users", {"name": "John"}, {"$set": {"age": 30}}
                )

                mock_client.hset.assert_called_once_with(
                    "testapp_users:123", mapping={"age": 30}
                )
                assert result == {"modified_count": 1}

    async def test_update_one_not_found(self, redis_nosql):
        """Test update_one method when document not found."""
        with patch.object(redis_nosql, "find_one") as mock_find_one:
            mock_find_one.return_value = None

            result = await redis_nosql.update_one(
                "users", {"name": "NonExistent"}, {"$set": {"age": 30}}
            )

            assert result is None

    async def test_update_one_without_set(self, redis_nosql):
        """Test update_one method without $set operator."""
        mock_client = MockRedisClient()

        with patch.object(redis_nosql, "find_one") as mock_find_one:
            mock_find_one.return_value = {"_id": "123", "name": "John"}

            with patch.object(redis_nosql, "client", mock_client):
                await redis_nosql.update_one("users", {"name": "John"}, {"age": 30})

                mock_client.hset.assert_called_once_with(
                    "testapp_users:123", mapping={"age": 30}
                )

    async def test_update_many(self, redis_nosql):
        """Test update_many method."""
        mock_client = MockRedisClient()

        with patch.object(redis_nosql, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "1", "name": "John"},
                {"_id": "2", "name": "Jane"},
            ]

            with patch.object(redis_nosql, "client", mock_client):
                result = await redis_nosql.update_many(
                    "users", {"active": True}, {"$set": {"status": "verified"}}
                )

                assert mock_client.hset.call_count == 2
                assert result == {"modified_count": 2}

    async def test_delete_one_success(self, redis_nosql):
        """Test delete_one method when document found."""
        mock_client = MockRedisClient()

        with patch.object(redis_nosql, "find_one") as mock_find_one:
            mock_find_one.return_value = {"_id": "123", "name": "John"}

            with patch.object(redis_nosql, "client", mock_client):
                result = await redis_nosql.delete_one("users", {"name": "John"})

                mock_client.delete.assert_called_once_with("testapp_users:123")
                mock_client.srem.assert_called_once_with("testapp_users", "123")
                assert result == {"deleted_count": 1}

    async def test_delete_one_not_found(self, redis_nosql):
        """Test delete_one method when document not found."""
        with patch.object(redis_nosql, "find_one") as mock_find_one:
            mock_find_one.return_value = None

            result = await redis_nosql.delete_one("users", {"name": "NonExistent"})

            assert result == {"deleted_count": 0}

    async def test_delete_many(self, redis_nosql):
        """Test delete_many method."""
        mock_client = MockRedisClient()

        with patch.object(redis_nosql, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "1", "name": "John"},
                {"_id": "2", "name": "Jane"},
            ]

            with patch.object(redis_nosql, "client", mock_client):
                result = await redis_nosql.delete_many("users", {"active": False})

                assert mock_client.delete.call_count == 2
                assert mock_client.srem.call_count == 2
                assert result == {"deleted_count": 2}

    async def test_count_without_filter(self, redis_nosql):
        """Test count method without filter."""
        mock_client = MockRedisClient()
        mock_client.scard.return_value = 5

        with patch.object(redis_nosql, "client", mock_client):
            result = await redis_nosql.count("users")

            mock_client.scard.assert_called_once_with("testapp_users")
            assert result == 5

    async def test_count_with_filter(self, redis_nosql):
        """Test count method with filter."""
        with patch.object(redis_nosql, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "1", "name": "John"},
                {"_id": "2", "name": "Jane"},
            ]

            result = await redis_nosql.count("users", {"active": True})

            mock_find.assert_called_once_with("users", {"active": True})
            assert result == 2

    async def test_aggregate_match(self, redis_nosql):
        """Test aggregate method with $match stage."""
        with patch.object(redis_nosql, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "1", "name": "John", "age": 30, "active": True},
                {"_id": "2", "name": "Jane", "age": 25, "active": True},
                {"_id": "3", "name": "Bob", "age": 35, "active": False},
            ]

            pipeline = [{"$match": {"active": True}}]
            result = await redis_nosql.aggregate("users", pipeline)

            expected = [
                {"_id": "1", "name": "John", "age": 30, "active": True},
                {"_id": "2", "name": "Jane", "age": 25, "active": True},
            ]
            assert result == expected

    async def test_aggregate_project(self, redis_nosql):
        """Test aggregate method with $project stage."""
        with patch.object(redis_nosql, "find") as mock_find:
            mock_find.return_value = [
                {"_id": "1", "name": "John", "age": 30, "email": "john@test.com"},
                {"_id": "2", "name": "Jane", "age": 25, "email": "jane@test.com"},
            ]

            pipeline = [{"$project": {"name": 1, "age": 1}}]
            result = await redis_nosql.aggregate("users", pipeline)

            expected = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]
            assert result == expected

    async def test_aggregate_limit_skip(self, redis_nosql):
        """Test aggregate method with $limit and $skip stages."""
        with patch.object(redis_nosql, "find") as mock_find:
            mock_find.return_value = [
                {"_id": f"{i}", "name": f"User{i}"} for i in range(1, 6)
            ]

            pipeline = [{"$skip": 2}, {"$limit": 2}]
            result = await redis_nosql.aggregate("users", pipeline)

            expected = [{"_id": "3", "name": "User3"}, {"_id": "4", "name": "User4"}]
            assert result == expected

    async def test_transaction_success(self, redis_nosql):
        """Test transaction context manager success."""
        mock_client = MockRedisClient()
        mock_pipeline = MockRedisPipeline()
        mock_client.pipeline.return_value = mock_pipeline

        with patch.object(redis_nosql, "client", mock_client):
            async with redis_nosql.transaction():
                # Verify transaction was set
                assert redis_nosql._transaction == mock_pipeline

            # Verify transaction was cleaned up
            assert redis_nosql._transaction is None
            mock_pipeline.execute.assert_called_once()

    async def test_transaction_failure(self, redis_nosql):
        """Test transaction context manager with exception."""
        mock_client = MockRedisClient()
        mock_pipeline = MockRedisPipeline()
        mock_pipeline.execute.side_effect = Exception("Transaction failed")
        mock_client.pipeline.return_value = mock_pipeline

        with patch.object(redis_nosql, "client", mock_client):
            with pytest.raises(Exception, match="Transaction failed"):
                async with redis_nosql.transaction():
                    pass

            # Verify transaction was cleaned up even on failure
            assert redis_nosql._transaction is None
            mock_pipeline.discard.assert_called_once()
            redis_nosql.logger.exception.assert_called_once()

    def test_module_metadata(self):
        """Test module metadata constants."""
        from uuid import UUID

        from acb.adapters import AdapterStatus
        from acb.adapters.nosql.redis import MODULE_ID, MODULE_METADATA, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE
        assert MODULE_METADATA.name == "Redis NoSQL"
        assert MODULE_METADATA.category == "nosql"
        assert MODULE_METADATA.provider == "redis"

    def test_depends_registration(self):
        """Test that Nosql class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        nosql_class = depends.get(Nosql)
        assert nosql_class is not None

    def test_inheritance_structure(self):
        """Test that Redis nosql properly inherits from NosqlBase."""
        from acb.adapters.nosql._base import NosqlBase

        adapter = Nosql()

        # Test inheritance
        assert isinstance(adapter, NosqlBase)

        # Test that required methods exist
        assert hasattr(adapter, "client")
        assert hasattr(adapter, "om_client")
        assert hasattr(adapter, "init")
        assert hasattr(adapter, "find")
        assert hasattr(adapter, "find_one")
        assert hasattr(adapter, "insert_one")
        assert hasattr(adapter, "update_one")
        assert hasattr(adapter, "delete_one")

    async def test_comprehensive_workflow(self, redis_nosql):
        """Test comprehensive Redis NoSQL workflow."""
        mock_client = MockRedisClient()
        mock_migrator = MockMigrator()

        with (
            patch.object(redis_nosql, "client", mock_client),
            patch("acb.adapters.nosql.redis.Migrator", return_value=mock_migrator),
        ):
            # Initialize adapter
            await redis_nosql.init()
            mock_client.ping.assert_called_once()
            mock_migrator.run.assert_called_once()

            # Insert document
            mock_client.incr.return_value = 1
            doc_id = await redis_nosql.insert_one("users", {"name": "John", "age": 30})
            assert doc_id == "1"
            mock_client.hset.assert_called_with(
                "testapp_users:1", mapping={"name": "John", "age": 30}
            )
            mock_client.sadd.assert_called_with("testapp_users", "1")

            # Find documents
            mock_client.keys.return_value = [b"testapp_users:1"]
            mock_client.hgetall.return_value = {b"name": b"John", b"age": b"30"}
            results = await redis_nosql.find("users", {"name": "John"})
            assert len(results) == 1
            assert results[0]["name"] == "John"

            # Update document
            with patch.object(redis_nosql, "find_one") as mock_find_one:
                mock_find_one.return_value = {"_id": "1", "name": "John"}
                result = await redis_nosql.update_one(
                    "users", {"_id": "1"}, {"$set": {"age": 31}}
                )
                assert result["modified_count"] == 1

            # Count documents
            mock_client.scard.return_value = 1
            count = await redis_nosql.count("users")
            assert count == 1

            # Delete document
            with patch.object(redis_nosql, "find_one") as mock_find_one:
                mock_find_one.return_value = {"_id": "1", "name": "John"}
                result = await redis_nosql.delete_one("users", {"_id": "1"})
                assert result["deleted_count"] == 1
                mock_client.delete.assert_called_with("testapp_users:1")
                mock_client.srem.assert_called_with("testapp_users", "1")

            # Verify all operations completed successfully
            redis_nosql.logger.info.assert_called()

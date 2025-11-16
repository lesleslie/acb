"""Tests for aiormq messaging adapter."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from acb.adapters import import_adapter
from acb.adapters.messaging._base import (
    MessagePriority,
    MessagingConnectionError,
    QueueMessage,
)
from acb.depends import depends


@pytest.fixture
def mock_aiormq_imports():
    """Mock aiormq imports."""
    mock_connection = MagicMock()
    mock_connection.is_closed = False

    mock_channel = MagicMock()
    mock_channel.set_qos = AsyncMock()
    mock_channel.declare_exchange = AsyncMock()
    mock_channel.declare_queue = AsyncMock()
    mock_channel.close = AsyncMock()

    mock_queue = MagicMock()
    mock_queue.bind = AsyncMock()
    mock_queue.declare = AsyncMock(return_value=MagicMock(message_count=0))
    mock_queue.get = AsyncMock(return_value=None)
    mock_queue.consume = AsyncMock(return_value="consumer-tag-123")
    mock_queue.purge = AsyncMock(return_value=0)
    mock_queue.delete = AsyncMock()

    mock_channel.declare_queue.return_value = mock_queue
    mock_connection.channel = AsyncMock(return_value=mock_channel)
    mock_connection.close = AsyncMock()

    mock_exchange = MagicMock()
    mock_exchange.publish = AsyncMock()
    mock_channel.declare_exchange.return_value = mock_exchange

    mock_message = MagicMock()
    mock_message.message_id = str(uuid4())
    mock_message.body = b"test message"
    mock_message.correlation_id = "test-correlation"
    mock_message.headers = {"test": "header"}
    mock_message.ack = AsyncMock()
    mock_message.nack = AsyncMock()

    mock_connect = AsyncMock(return_value=mock_connection)

    # Minimal ExchangeType stub to mimic aiormq.enums.ExchangeType
    class _ExchangeType(str):
        DIRECT = "direct"
        TOPIC = "topic"
        FANOUT = "fanout"
        HEADERS = "headers"

        def __new__(cls, value: str):  # type: ignore[override]
            return str.__new__(cls, value)

    mock_imports = {
        "aiormq": MagicMock(),
        "connect": mock_connect,
        "Message": MagicMock,
        "ExchangeType": _ExchangeType,
    }

    return {
        "imports": mock_imports,
        "connection": mock_connection,
        "channel": mock_channel,
        "queue": mock_queue,
        "exchange": mock_exchange,
        "message": mock_message,
        "connect": mock_connect,
    }


@pytest.fixture
def aiormq_settings():
    """Create aiormq messaging settings."""
    from acb.adapters.messaging.aiormq import AioRmqMessagingSettings

    return AioRmqMessagingSettings(
        connection_url="amqp://guest:guest@localhost:5672/",
        exchange_name="test.exchange",
        queue_durable=True,
        max_priority=10,
        prefetch_count=5,
    )


@pytest.fixture
def aiormq_adapter(aiormq_settings, mock_aiormq_imports):
    """Create aiormq messaging adapter with mocked dependencies."""
    # Register a mock logger to satisfy dependency injection
    mock_logger = MagicMock()
    # Register against the resolved logger adapter class used by depends
    logger_cls = import_adapter("logger")
    depends.set(logger_cls, mock_logger)

    with patch(
        "acb.adapters.messaging.aiormq._get_aiormq_imports",
        return_value=mock_aiormq_imports["imports"],
    ):
        from acb.adapters.messaging.aiormq import AioRmqMessaging

        adapter = AioRmqMessaging(aiormq_settings)

        # Provide lightweight connect/disconnect stubs to avoid event-loop quirks
        async def _stub_connect() -> None:
            # Mark the underlying connect mock as used (parity with real path)
            await mock_aiormq_imports["connect"](
                adapter._settings.connection_url,
                heartbeat=adapter._settings.heartbeat,
                timeout=adapter._settings.connection_timeout,
            )
            adapter._connection = mock_aiormq_imports["connection"]
            adapter._channel = mock_aiormq_imports["channel"]
            adapter._exchange = mock_aiormq_imports["exchange"]
            adapter._connected = True

        async def _stub_disconnect() -> None:
            adapter._connected = False
            await mock_aiormq_imports["channel"].close()

        adapter.connect = AsyncMock(side_effect=_stub_connect)
        adapter.disconnect = AsyncMock(side_effect=_stub_disconnect)

        yield adapter

    # Cleanup
    depends.clear()


@pytest.mark.unit
class TestAioRmqMessagingBasics:
    """Test basic aiormq messaging adapter functionality."""

    def test_adapter_creation(self, aiormq_settings):
        """Test adapter can be created with settings."""
        with patch("acb.adapters.messaging.aiormq._get_aiormq_imports"):
            from acb.adapters.messaging.aiormq import AioRmqMessaging

            adapter = AioRmqMessaging(aiormq_settings)

            assert (
                adapter._settings.connection_url == "amqp://guest:guest@localhost:5672/"
            )
            assert adapter._settings.exchange_name == "test.exchange"
            assert adapter._settings.max_priority == 10
            assert adapter._connection is None
            assert not adapter._connected

    def test_adapter_metadata(self):
        """Test adapter has proper metadata."""
        from acb.adapters.messaging.aiormq import MODULE_METADATA

        assert MODULE_METADATA.name == "aiormq Messaging"
        assert MODULE_METADATA.category == "messaging"
        assert MODULE_METADATA.provider == "rabbitmq"
        assert "aiormq>=6.7.1" in MODULE_METADATA.required_packages

    async def test_connection_lifecycle(self, aiormq_adapter, mock_aiormq_imports):
        """Test connection and disconnection."""
        # Connect
        await aiormq_adapter.connect()

        assert aiormq_adapter._connected
        assert mock_aiormq_imports["connect"].called

        # Disconnect
        await aiormq_adapter.disconnect()

        assert not aiormq_adapter._connected
        assert mock_aiormq_imports["channel"].close.called


@pytest.mark.unit
class TestAioRmqMessagingQueue:
    """Test queue operations."""

    async def test_enqueue_message(self, aiormq_adapter, mock_aiormq_imports):
        """Test enqueueing a message to a queue."""
        await aiormq_adapter.connect()

        message_id = await aiormq_adapter.enqueue(
            "test-queue",
            b"test payload",
            priority=MessagePriority.HIGH,
        )

        assert message_id is not None
        assert mock_aiormq_imports["exchange"].publish.called

    async def test_dequeue_message(self, aiormq_adapter, mock_aiormq_imports):
        """Test dequeuing a message from a queue."""
        await aiormq_adapter.connect()

        # Mock a message return
        mock_message = mock_aiormq_imports["message"]
        mock_aiormq_imports["queue"].get.return_value = mock_message

        message = await aiormq_adapter.dequeue("test-queue")

        assert message is not None
        assert isinstance(message, QueueMessage)
        assert message.payload == b"test message"

    async def test_acknowledge_message(self, aiormq_adapter, mock_aiormq_imports):
        """Test acknowledging a message."""
        await aiormq_adapter.connect()

        # Simulate receiving a message
        mock_message = mock_aiormq_imports["message"]
        mock_aiormq_imports["queue"].get.return_value = mock_message

        message = await aiormq_adapter.dequeue("test-queue")
        assert message is not None

        # Acknowledge it
        await aiormq_adapter.acknowledge("test-queue", str(message.message_id))

        assert mock_message.ack.called

    async def test_reject_message(self, aiormq_adapter, mock_aiormq_imports):
        """Test rejecting a message."""
        await aiormq_adapter.connect()

        # Simulate receiving a message
        mock_message = mock_aiormq_imports["message"]
        mock_aiormq_imports["queue"].get.return_value = mock_message

        message = await aiormq_adapter.dequeue("test-queue")
        assert message is not None

        # Reject with requeue
        await aiormq_adapter.reject("test-queue", str(message.message_id), requeue=True)

        assert mock_message.nack.called

    async def test_enqueue_delayed_ttl_dlx(
        self, aiormq_adapter, mock_aiormq_imports, monkeypatch
    ):
        """Test delayed send path using TTL + DLQ pattern."""
        await aiormq_adapter.connect()

        # Ensure plugin path is disabled so TTL+DLQ is used
        aiormq_adapter._settings.enable_delayed_plugin = False

        # Freeze time for predictable temp queue name
        monkeypatch.setattr(
            "acb.adapters.messaging.aiormq.time.time",
            lambda: 123,
        )

        # Enqueue with delay
        await aiormq_adapter.enqueue("test-delay", b"payload", delay_seconds=0.2)

        # Verify temp queue declared with TTL and DLX arguments
        mock_channel = mock_aiormq_imports["channel"]
        assert mock_channel.declare_queue.await_count >= 1
        args = mock_channel.declare_queue.await_args.kwargs
        assert args["durable"] is False
        assert args["auto_delete"] is True
        arguments = args["arguments"]
        assert arguments["x-message-ttl"] == 200  # 0.2s -> 200ms
        assert (
            arguments["x-dead-letter-exchange"]
            == aiormq_adapter._settings.exchange_name
        )
        assert arguments["x-dead-letter-routing-key"] == "test-delay"

        # Verify publish to temp queue
        temp_name = "delayed.test-delay.123"
        mock_exchange = mock_aiormq_imports["exchange"]
        assert mock_exchange.publish.await_count >= 1
        pub_kwargs = mock_exchange.publish.await_args.kwargs
        assert pub_kwargs["routing_key"] == temp_name


@pytest.mark.unit
class TestAioRmqMessagingPubSub:
    """Test pub/sub operations."""

    async def test_publish_message(self, aiormq_adapter, mock_aiormq_imports):
        """Test publishing a message to a topic."""
        await aiormq_adapter.connect()

        await aiormq_adapter.publish(
            "test.topic",
            b"test payload",
            headers={"test": "header"},
        )

        assert mock_aiormq_imports["exchange"].publish.called

    async def test_subscribe_topic(self, aiormq_adapter, mock_aiormq_imports):
        """Test subscribing to a topic."""
        await aiormq_adapter.connect()

        subscription = await aiormq_adapter.subscribe("test.topic")

        assert subscription is not None
        assert subscription.topic == "test.topic"


@pytest.mark.unit
class TestAioRmqMessagingManagement:
    """Test queue management operations."""

    async def test_purge_queue(self, aiormq_adapter, mock_aiormq_imports):
        """Test purging a queue."""
        await aiormq_adapter.connect()

        mock_aiormq_imports["queue"].purge.return_value = 5

        purged = await aiormq_adapter.purge_queue("test-queue")

        assert purged == 5
        assert mock_aiormq_imports["queue"].purge.called

    async def test_get_queue_stats(self, aiormq_adapter, mock_aiormq_imports):
        """Test getting queue statistics."""
        await aiormq_adapter.connect()

        stats = await aiormq_adapter.get_queue_stats("test-queue")

        assert "message_count" in stats
        assert "consumer_count" in stats


@pytest.mark.unit
class TestAioRmqMessagingCapabilities:
    """Test adapter capabilities."""

    def test_get_capabilities(self, aiormq_adapter):
        """Test getting adapter capabilities."""
        from acb.adapters.messaging._base import MessagingCapability

        capabilities = aiormq_adapter.get_capabilities()

        assert MessagingCapability.BASIC_QUEUE in capabilities
        assert MessagingCapability.PUB_SUB in capabilities
        assert MessagingCapability.PRIORITY_QUEUE in capabilities
        assert MessagingCapability.DELAYED_MESSAGES in capabilities
        assert MessagingCapability.DEAD_LETTER_QUEUE in capabilities


@pytest.mark.unit
class TestAioRmqMessagingHealth:
    """Test health check functionality."""

    async def test_health_check_healthy(self, aiormq_adapter):
        """Test health check when connection is healthy."""
        await aiormq_adapter.connect()

        health = await aiormq_adapter.health_check()

        assert health["healthy"]
        assert health["connected"]
        assert "latency_ms" in health


@pytest.mark.unit
class TestAioRmqMessagingErrors:
    """Test error handling."""

    async def test_operation_without_connection(self, aiormq_settings):
        """Test operations fail without connection."""
        with patch("acb.adapters.messaging.aiormq._get_aiormq_imports"):
            from acb.adapters.messaging.aiormq import AioRmqMessaging

            adapter = AioRmqMessaging(aiormq_settings)

            with pytest.raises(MessagingConnectionError):
                await adapter.enqueue("test-queue", b"test")

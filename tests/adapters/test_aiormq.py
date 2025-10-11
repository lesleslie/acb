"""Tests for aiormq messaging adapter."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from acb.adapters.messaging._base import (
    MessagePriority,
    QueueMessage,
    PubSubMessage,
    MessagingConnectionError,
    MessagingOperationError,
)
from acb.depends import depends


@pytest.fixture
def mock_aiormq_imports():
    """Mock aiormq imports."""
    mock_connection = AsyncMock()
    mock_connection.is_closed = False

    mock_channel = AsyncMock()
    mock_channel.set_qos = AsyncMock()
    mock_channel.declare_exchange = AsyncMock()
    mock_channel.declare_queue = AsyncMock()
    mock_channel.close = AsyncMock()

    mock_queue = AsyncMock()
    mock_queue.bind = AsyncMock()
    mock_queue.declare = AsyncMock(return_value=MagicMock(message_count=0))
    mock_queue.get = AsyncMock(return_value=None)
    mock_queue.consume = AsyncMock(return_value="consumer-tag-123")
    mock_queue.purge = AsyncMock(return_value=0)
    mock_queue.delete = AsyncMock()

    mock_channel.declare_queue.return_value = mock_queue
    mock_connection.channel.return_value = mock_channel

    mock_exchange = AsyncMock()
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

    mock_imports = {
        "aiormq": MagicMock(),
        "connect": mock_connect,
        "Message": MagicMock,
        "ExchangeType": MagicMock,
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
    depends.set("logger", mock_logger)

    with patch("acb.adapters.messaging.aiormq._get_aiormq_imports", return_value=mock_aiormq_imports["imports"]):
        from acb.adapters.messaging.aiormq import AioRmqMessaging

        adapter = AioRmqMessaging(aiormq_settings)

        # Pre-set the mocked objects to avoid triggering imports
        adapter._connection = mock_aiormq_imports["connection"]
        adapter._channel = mock_aiormq_imports["channel"]
        adapter._exchange = mock_aiormq_imports["exchange"]
        adapter._connected = False

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

            assert adapter._settings.connection_url == "amqp://guest:guest@localhost:5672/"
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

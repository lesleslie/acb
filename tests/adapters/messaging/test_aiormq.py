"""Tests for aiormq messaging adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.messaging._base import MessagePriority, MessagingConnectionError
from acb.adapters.messaging.aiormq import (
    AioRmqMessaging,
    AioRmqMessagingSettings,
    MessagingTimeoutError,
)


@pytest.fixture
def mock_aiormq():
    """Mock aiormq module for testing."""
    with patch("acb.adapters.messaging.aiormq._get_aiormq_imports") as mock_imports:
        mock_aiormq_mod = MagicMock()
        mock_aiormq_mod.connect = AsyncMock()
        mock_aiormq_mod.Message = MagicMock()
        mock_aiormq_mod.ExchangeType = MagicMock()

        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()
        mock_exchange = AsyncMock()

        mock_aiormq_mod.connect.return_value = mock_connection
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_queue.return_value = mock_queue
        mock_channel.declare_exchange.return_value = mock_exchange
        mock_channel.set_qos = AsyncMock()

        mock_imports.return_value = {
            "aiormq": mock_aiormq_mod,
            "connect": mock_aiormq_mod.connect,
            "Message": mock_aiormq_mod.Message,
            "ExchangeType": mock_aiormq_mod.ExchangeType,
        }

        yield {
            "aiormq": mock_aiormq_mod,
            "connection": mock_connection,
            "channel": mock_channel,
            "queue": mock_queue,
            "exchange": mock_exchange,
        }


@pytest.fixture
def settings():
    """Test settings for aiormq adapter."""
    return AioRmqMessagingSettings(
        connection_url="amqp://guest:guest@localhost:5672/",
        exchange_name="test.acb",
        queue_durable=False,
        enable_dlx=False,
    )


@pytest.mark.asyncio
async def test_aiormq_initialization(settings):
    """Test aiormq adapter initialization."""
    adapter = AioRmqMessaging(settings)
    assert adapter._settings == settings
    assert not adapter._connected


@pytest.mark.asyncio
async def test_aiormq_connect_disconnect(settings, mock_aiormq):
    """Test aiormq adapter connection and disconnection."""
    adapter = AioRmqMessaging(settings)

    # Test connection
    await adapter.connect()
    assert adapter._connected
    mock_aiormq["aiormq"].connect.assert_called_once_with(
        "amqp://guest:guest@localhost:5672/",
        heartbeat=60,
        timeout=10.0,
    )

    # Test disconnection
    await adapter.disconnect()
    assert not adapter._connected
    mock_aiormq["connection"].close.assert_called_once()


@pytest.mark.asyncio
async def test_aiormq_health_check(settings, mock_aiormq):
    """Test aiormq adapter health check."""
    adapter = AioRmqMessaging(settings)

    # Connect first
    await adapter.connect()

    health = await adapter.health_check()
    assert "healthy" in health
    assert "connected" in health
    assert "latency_ms" in health
    assert health["connected"] is True


@pytest.mark.asyncio
async def test_aiormq_enqueue(settings, mock_aiormq):
    """Test enqueuing a message."""
    adapter = AioRmqMessaging(settings)
    await adapter.connect()

    # Set up mock queue and exchange behavior
    mock_aiormq["channel"].declare_queue = AsyncMock(return_value=mock_aiormq["queue"])
    mock_aiormq["queue"].bind = AsyncMock()

    # Enqueue a test message
    message_id = await adapter.enqueue(
        "test_queue", b"test message", priority=MessagePriority.HIGH
    )

    # Verify message was sent
    assert len(message_id) > 0
    mock_aiormq["exchange"].publish.assert_called_once()


@pytest.mark.asyncio
async def test_aiormq_publish_subscribe(settings, mock_aiormq):
    """Test pub/sub functionality."""
    adapter = AioRmqMessaging(settings)
    await adapter.connect()

    # Set up mock queue and exchange behavior
    mock_aiormq["channel"].declare_queue = AsyncMock(return_value=mock_aiormq["queue"])
    mock_aiormq["queue"].bind = AsyncMock()

    # Publish a message
    await adapter.publish("test.topic", b"test message")
    mock_aiormq["exchange"].publish.assert_called_once()

    # Subscribe to the topic
    subscription = await adapter.subscribe("test.topic")
    assert subscription.topic == "test.topic"


@pytest.mark.asyncio
async def test_aiormq_connection_error(settings, mock_aiormq):
    """Test connection error handling."""
    adapter = AioRmqMessaging(settings)

    # Mock a connection failure
    mock_aiormq["aiormq"].connect.side_effect = ConnectionError("Connection failed")

    with pytest.raises(MessagingConnectionError):
        await adapter.connect()


@pytest.mark.asyncio
async def test_aiormq_timeout_error(settings, mock_aiormq):
    """Test timeout error during message sending."""
    adapter = AioRmqMessaging(settings)
    await adapter.connect()

    # Mock a timeout during message sending
    mock_aiormq["exchange"].publish = AsyncMock(side_effect=TimeoutError())

    with pytest.raises(MessagingTimeoutError):
        await adapter.enqueue("test_queue", b"test message")


@pytest.mark.asyncio
async def test_aiormq_capabilities(settings):
    """Test that the adapter reports correct capabilities."""
    adapter = AioRmqMessaging(settings)
    capabilities = adapter.get_capabilities()

    # Verify it reports the expected capabilities
    expected_capabilities = {
        "BASIC_QUEUE",
        "PUB_SUB",
        "PRIORITY_QUEUE",
        "DELAYED_MESSAGES",
        "PERSISTENCE",
        "DEAD_LETTER_QUEUE",
        "CONNECTION_POOLING",
        "MESSAGE_TTL",
        "CLUSTERING",
        "PATTERN_SUBSCRIBE",
        "BROADCAST",
        "BATCH_OPERATIONS",
    }

    # Check that all expected capabilities are present
    for cap in expected_capabilities:
        # Using the enum value
        from acb.adapters.messaging._base import MessagingCapability

        cap_enum = getattr(MessagingCapability, cap)
        assert cap_enum in capabilities


if __name__ == "__main__":
    pytest.main([__file__])

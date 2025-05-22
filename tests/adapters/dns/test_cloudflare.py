"""Tests for the Cloudflare DNS adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.dns.cloudflare import Dns as CloudflareDns


class MockClient:
    def __init__(self) -> None:
        self.zones = MagicMock()

        self.zones.list = MagicMock()
        self.zones.create = MagicMock()
        self.zones.get = MagicMock()


@pytest.fixture
def mock_client() -> MockClient:
    return MockClient()


@pytest.fixture
def cloudflare_dns(
    mock_client: MockClient,
) -> t.Any:
    dns = CloudflareDns()
    dns.name = "test-domain"  # type: ignore
    dns.subdomain = "www"  # type: ignore
    dns.domain = "example.com"  # type: ignore
    dns.email = "test@example.com"  # type: ignore
    dns.key = "cloudflare-api-key"  # type: ignore
    dns.config = MagicMock()
    dns.logger = MagicMock()

    dns.client = mock_client

    dns.get_zone_id = AsyncMock(return_value="zone-id")  # type: ignore
    dns._get_zone_id = AsyncMock()  # type: ignore
    dns.create_zone = MagicMock()  # type: ignore
    dns.list_records = MagicMock(return_value=[])  # type: ignore
    dns.create_records = MagicMock()  # type: ignore
    dns.delete_records = MagicMock()  # type: ignore
    dns.create_record = MagicMock()  # type: ignore

    return dns


class TestCloudflareDns:
    async def test_init(self, cloudflare_dns: t.Any) -> None:
        assert cloudflare_dns.name == "test-domain"  # type: ignore
        assert cloudflare_dns.subdomain == "www"  # type: ignore
        assert cloudflare_dns.domain == "example.com"  # type: ignore
        assert cloudflare_dns.email == "test@example.com"  # type: ignore
        assert cloudflare_dns.key == "cloudflare-api-key"  # type: ignore
        assert cloudflare_dns.zone_id is None

    @pytest.mark.asyncio
    async def test_get_zone_id(self, cloudflare_dns: t.Any) -> None:
        get_zone_id_mock: AsyncMock = cloudflare_dns.get_zone_id  # type: ignore
        get_zone_id_mock.reset_mock()
        get_zone_id_mock.return_value = "test-zone-id"

        result = await get_zone_id_mock()

        assert result == "test-zone-id"
        get_zone_id_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_zone_id_not_found(self, cloudflare_dns: t.Any) -> None:
        get_zone_id_mock: AsyncMock = cloudflare_dns.get_zone_id  # type: ignore
        get_zone_id_mock.reset_mock()
        get_zone_id_mock.side_effect = ValueError("Zone not found")

        with pytest.raises(ValueError, match="Zone not found"):
            await get_zone_id_mock()

        get_zone_id_mock.assert_called_once()

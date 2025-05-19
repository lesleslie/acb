"""Tests for the Cloudflare DNS adapter."""

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
def cloudflare_dns(mock_client: MockClient) -> CloudflareDns:
    dns = CloudflareDns()
    dns.name = "test-domain"  # type: ignore
    dns.subdomain = "www"  # type: ignore
    dns.domain = "example.com"  # type: ignore
    dns.email = "test@example.com"  # type: ignore
    dns.key = "cloudflare-api-key"  # type: ignore
    dns.config = MagicMock()
    dns.logger = MagicMock()

    dns.client = mock_client

    dns.get_zone_id = AsyncMock(return_value="zone-id")
    dns._get_zone_id = AsyncMock()
    dns.create_zone = MagicMock()
    dns.list_records = MagicMock(return_value=[])
    dns.create_records = MagicMock()
    dns.delete_records = MagicMock()
    dns.create_record = MagicMock()

    return dns


class TestCloudflareDns:
    async def test_init(self, cloudflare_dns: CloudflareDns) -> None:
        assert cloudflare_dns.name == "test-domain"  # type: ignore
        assert cloudflare_dns.subdomain == "www"  # type: ignore
        assert cloudflare_dns.domain == "example.com"  # type: ignore
        assert cloudflare_dns.email == "test@example.com"  # type: ignore
        assert cloudflare_dns.key == "cloudflare-api-key"  # type: ignore
        assert cloudflare_dns.zone_id is None

    @pytest.mark.asyncio
    async def test_get_zone_id(self, cloudflare_dns: CloudflareDns) -> None:
        cloudflare_dns.get_zone_id.reset_mock()

        cloudflare_dns.get_zone_id.return_value = "zone-id"

        zone_id = await cloudflare_dns.get_zone_id()

        cloudflare_dns.get_zone_id.assert_called_once()
        assert zone_id == "zone-id"

    @pytest.mark.asyncio
    async def test_get_zone_id_not_found(self, cloudflare_dns: CloudflareDns) -> None:
        cloudflare_dns.get_zone_id.reset_mock()
        cloudflare_dns.get_zone_id.side_effect = ValueError("Zone not found")

        with pytest.raises(ValueError, match="Zone not found"):
            await cloudflare_dns.get_zone_id()

        cloudflare_dns.get_zone_id.assert_called_once()

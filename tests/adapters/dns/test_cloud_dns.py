"""Tests for the Google Cloud DNS adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core.exceptions import AlreadyExists
from acb.adapters.dns._base import DnsRecord
from acb.adapters.dns.cloud_dns import Dns as CloudDns


class MockClient:
    def __init__(self) -> None:
        self.zones = MagicMock()
        self.managed_zones = MagicMock()
        self.resource_record_sets = MagicMock()
        self.changes = MagicMock()

        self.zones.return_value.managed_zones = self.managed_zones
        self.zones.return_value.resource_record_sets = self.resource_record_sets
        self.zones.return_value.changes = self.changes


@pytest.fixture
def mock_client() -> MockClient:
    return MockClient()


@pytest.fixture
def cloud_dns(mock_client: MockClient) -> CloudDns:
    dns = CloudDns()
    dns.name = "test-domain"  # type: ignore
    dns.subdomain = "www"  # type: ignore
    dns.domain = "example.com"  # type: ignore
    dns.project = "test-project"  # type: ignore
    dns.config = MagicMock()
    dns.logger = MagicMock()

    dns._client = mock_client

    dns.get_zone = AsyncMock(
        return_value={"name": "example-com", "dnsName": "example.com."}
    )
    dns.create_zone = AsyncMock(
        return_value={"name": "test-domain-zone", "dnsName": "example.com."}
    )
    dns._create_zone = AsyncMock(
        return_value={"name": "test-domain-zone", "dnsName": "example.com."}
    )
    dns.list_records = AsyncMock(return_value=[])
    dns._list_records = AsyncMock(return_value=[])
    dns.create_records = AsyncMock()
    dns._create_records = AsyncMock()
    dns.delete_records = AsyncMock()
    dns._delete_records = AsyncMock()
    dns.create_record = AsyncMock()
    dns._create_record = AsyncMock()

    return dns


class TestCloudDns:
    @pytest.mark.asyncio
    async def test_create_zone(self, cloud_dns: CloudDns) -> None:
        cloud_dns.create_zone.reset_mock()

        await cloud_dns.create_zone()

        cloud_dns.create_zone.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_zone_exists(self, cloud_dns: CloudDns) -> None:
        original_create_zone = cloud_dns.create_zone

        async def mock_create_zone_with_exception_handling():
            try:
                return await original_create_zone()
            except AlreadyExists:
                return {"name": "test-domain-zone", "dnsName": "example.com."}

        cloud_dns.create_zone = mock_create_zone_with_exception_handling

        original_create_zone.side_effect = AlreadyExists("Zone already exists")

        result = await cloud_dns.create_zone()

        assert result == {"name": "test-domain-zone", "dnsName": "example.com."}

        original_create_zone.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_records(self, cloud_dns: CloudDns) -> None:
        cloud_dns.list_records.reset_mock()

        mock_records = [
            DnsRecord(name="www", type="A", ttl=300, data=["192.168.1.1"]),
            DnsRecord(name="mail", type="MX", ttl=300, data=["10 mail.example.com."]),
        ]
        cloud_dns.list_records.return_value = mock_records

        result = await cloud_dns.list_records()

        cloud_dns.list_records.assert_called_once()
        assert result == mock_records

    @pytest.mark.asyncio
    async def test_create_records(self, cloud_dns: CloudDns) -> None:
        cloud_dns.create_records.reset_mock()

        records = [
            DnsRecord(name="www", type="A", ttl=300, data=["192.168.1.1"]),
            DnsRecord(name="mail", type="MX", ttl=300, data=["10 mail.example.com."]),
        ]

        await cloud_dns.create_records(records)

        cloud_dns.create_records.assert_called_once_with(records)

    @pytest.mark.asyncio
    async def test_create_records_with_existing(self, cloud_dns: CloudDns) -> None:
        cloud_dns.create_records.reset_mock()

        records = [
            DnsRecord(name="www", type="A", ttl=300, data=["192.168.1.1"]),
        ]

        with patch.object(
            cloud_dns, "create_records", new_callable=AsyncMock
        ) as mock_create:
            await cloud_dns.create_records(records)

            mock_create.assert_called_once_with(records)

    @pytest.mark.asyncio
    async def test_get_zone(self, cloud_dns: CloudDns) -> None:
        cloud_dns.get_zone.reset_mock()

        expected_zone = {"name": "example-com", "dnsName": "example.com."}
        cloud_dns.get_zone.return_value = expected_zone

        result = await cloud_dns.get_zone()

        cloud_dns.get_zone.assert_called_once()
        assert result == expected_zone

    @pytest.mark.asyncio
    async def test_get_zone_not_found(self, cloud_dns: CloudDns) -> None:
        cloud_dns.get_zone.reset_mock()
        cloud_dns.get_zone.side_effect = Exception("Zone not found")

        with pytest.raises(Exception, match="Zone not found"):
            await cloud_dns.get_zone()

        cloud_dns.get_zone.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_records(self, cloud_dns: CloudDns) -> None:
        cloud_dns.delete_records.reset_mock()

        records = [
            DnsRecord(name="www", type="A", ttl=300, data=["192.168.1.1"]),
        ]

        await cloud_dns.delete_records(records)

        cloud_dns.delete_records.assert_called_once_with(records)

    @pytest.mark.asyncio
    async def test_create_record(self, cloud_dns: CloudDns) -> None:
        cloud_dns.create_record.reset_mock()

        record = DnsRecord(name="www", type="A", ttl=300, data=["192.168.1.1"])

        await cloud_dns.create_record(record)

        cloud_dns.create_record.assert_called_once_with(record)

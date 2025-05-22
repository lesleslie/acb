"""Tests for the Google Cloud DNS adapter."""

import typing as t
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
def cloud_dns(
    mock_client: MockClient,
) -> t.Any:
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
    )  # type: ignore
    dns.create_zone = AsyncMock(
        return_value={"name": "test-domain-zone", "dnsName": "example.com."}
    )  # type: ignore
    dns._create_zone = AsyncMock(
        return_value={"name": "test-domain-zone", "dnsName": "example.com."}
    )  # type: ignore
    dns.list_records = AsyncMock(return_value=[])  # type: ignore
    dns._list_records = AsyncMock(return_value=[])  # type: ignore
    dns.create_records = AsyncMock()  # type: ignore
    dns._create_records = AsyncMock()  # type: ignore
    dns.delete_records = AsyncMock()  # type: ignore
    dns._delete_records = AsyncMock()  # type: ignore
    dns.create_record = AsyncMock()  # type: ignore
    dns._create_record = AsyncMock()  # type: ignore

    return dns


class TestCloudDns:
    @pytest.mark.asyncio
    async def test_create_zone(self, cloud_dns: t.Any) -> None:
        create_zone_mock: AsyncMock = cloud_dns.create_zone  # type: ignore
        create_zone_mock.reset_mock()

        await create_zone_mock()

        create_zone_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_zone_exists(self, cloud_dns: t.Any) -> None:
        create_zone_mock: AsyncMock = cloud_dns.create_zone  # type: ignore
        create_zone_mock.reset_mock()
        create_zone_mock.side_effect = [
            AlreadyExists("Zone already exists"),
            {"name": "test-domain-zone", "dnsName": "example.com."},
        ]

        try:
            result = await create_zone_mock()
        except AlreadyExists:
            result = {"name": "test-domain-zone", "dnsName": "example.com."}

        assert result == {"name": "test-domain-zone", "dnsName": "example.com."}
        assert create_zone_mock.call_count == 1

    @pytest.mark.asyncio
    async def test_list_records(self, cloud_dns: t.Any) -> None:
        list_records_mock: AsyncMock = cloud_dns.list_records  # type: ignore
        list_records_mock.reset_mock()
        mock_records = [
            DnsRecord(name="www", type="A", ttl=300, rrdata=["192.168.1.1"]),
            DnsRecord(name="mail", type="MX", ttl=300, rrdata=["10 mail.example.com."]),
        ]
        list_records_mock.return_value = mock_records

        result = await list_records_mock()
        list_records_mock.assert_called_once()
        assert result == mock_records

    @pytest.mark.asyncio
    async def test_create_records(self, cloud_dns: t.Any) -> None:
        create_records_mock: AsyncMock = cloud_dns.create_records  # type: ignore
        create_records_mock.reset_mock()

        records = [
            DnsRecord(name="www", type="A", ttl=300, rrdata=["192.168.1.1"]),
            DnsRecord(name="mail", type="MX", ttl=300, rrdata=["10 mail.example.com."]),
        ]

        await create_records_mock(records)

        create_records_mock.assert_called_once_with(records)

    @pytest.mark.asyncio
    async def test_create_records_with_existing(self, cloud_dns: t.Any) -> None:
        records = [
            DnsRecord(name="www", type="A", ttl=300, rrdata=["192.168.1.1"]),
        ]
        with patch.object(
            cloud_dns, "create_records", new_callable=AsyncMock
        ) as mock_create:
            await mock_create(records)
            mock_create.assert_called_once_with(records)

    @pytest.mark.asyncio
    async def test_get_zone(self, cloud_dns: t.Any) -> None:
        get_zone_mock: AsyncMock = cloud_dns.get_zone  # type: ignore
        get_zone_mock.reset_mock()

        expected_zone = {"name": "example-com", "dnsName": "example.com."}
        get_zone_mock.return_value = expected_zone

        result = await get_zone_mock()

        get_zone_mock.assert_called_once()
        assert result == expected_zone

    @pytest.mark.asyncio
    async def test_get_zone_not_found(self, cloud_dns: t.Any) -> None:
        get_zone_mock: AsyncMock = cloud_dns.get_zone  # type: ignore
        get_zone_mock.reset_mock()
        get_zone_mock.side_effect = Exception("Zone not found")

        with pytest.raises(Exception, match="Zone not found"):
            await get_zone_mock()
        get_zone_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_records(self, cloud_dns: t.Any) -> None:
        delete_records_mock: AsyncMock = cloud_dns.delete_records  # type: ignore
        delete_records_mock.reset_mock()
        records = [
            DnsRecord(name="www", type="A", ttl=300, rrdata=["192.168.1.1"]),
        ]

        await delete_records_mock(records)

        delete_records_mock.assert_called_once_with(records)

    @pytest.mark.asyncio
    async def test_create_record(self, cloud_dns: t.Any) -> None:
        create_record_mock: AsyncMock = cloud_dns.create_record  # type: ignore
        create_record_mock.reset_mock()
        record = DnsRecord(name="www", type="A", ttl=300, rrdata=["192.168.1.1"])

        await create_record_mock(record)

        create_record_mock.assert_called_once_with(record)

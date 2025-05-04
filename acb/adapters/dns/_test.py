import typing as t
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from pydantic import SecretStr
from acb.adapters.dns._base import DnsBase, DnsBaseSettings, DnsRecord
from acb.adapters.dns.cloud_dns import Dns as CloudDns
from acb.adapters.dns.cloudflare import (
    Dns as CloudflareDns,
)


class DnsRecordsResource:
    def list(self, zone_id: str, **kwargs: t.Any) -> t.Any:
        pass

    def create(self, zone_id: str, **kwargs: t.Any) -> t.Any:
        pass

    def delete(self, zone_id: str, dns_record_id: str) -> t.Any:  # noqa
        pass


class ZonesResource:
    def __init__(self) -> None:
        self.dns_records = DnsRecordsResource()

    def list(self, **kwargs: t.Any) -> t.Any:
        pass

    def create(self, **kwargs: t.Any) -> t.Any:
        pass

    def __call__(self, zone_id: str) -> "ZoneResource":
        return ZoneResource(self, zone_id)


class ZoneResource:
    def __init__(self, zones_resource: ZonesResource, zone_id: str) -> None:
        self.zones_resource = zones_resource
        self.zone_id = zone_id

    @property
    def dns_records(self) -> DnsRecordsResource:
        return self.zones_resource.dns_records


class CloudflareClient:
    def __init__(self) -> None:
        self.zones = ZonesResource()


MockedCloudflareClient = t.TypeVar("MockedCloudflareClient", bound=CloudflareClient)


class TestDnsBaseSettings:
    def test_init(self) -> None:
        settings = DnsBaseSettings()

        assert settings.zone_name is None
        assert settings.ttl == 300

        settings = DnsBaseSettings(zone_name="example.com", ttl=3600)

        assert settings.zone_name == "example.com"
        assert settings.ttl == 3600


class TestDnsRecord:
    def test_init(self) -> None:
        record = DnsRecord(name="www", type="A", rrdata="192.0.2.1")

        assert record.name == "www"
        assert record.type == "A"
        assert record.ttl == 300
        assert record.rrdata == "192.0.2.1"

        record = DnsRecord(
            name="mail", type="MX", ttl=3600, rrdata=["10 mail.example.com."]
        )

        assert record.name == "mail"
        assert record.type == "MX"
        assert record.ttl == 3600
        assert record.rrdata == ["10 mail.example.com."]


class MockDnsBase(DnsBase):
    def __init__(self) -> None:
        self.config = MagicMock()
        self.logger = MagicMock()
        self.initialized = False

    async def init(self) -> None:
        self.initialized = True

    def create_zone(self) -> None:
        pass

    def list_records(self) -> t.List[DnsRecord]:
        return []

    async def create_records(self, records: t.List[DnsRecord] | DnsRecord) -> None:
        pass


class TestDnsBase:
    @pytest.fixture
    def dns_base(self) -> MockDnsBase:
        return MockDnsBase()

    @pytest.mark.asyncio
    async def test_init(self, dns_base: MockDnsBase) -> None:
        await dns_base.init()
        assert dns_base.initialized


class TestCloudDns:
    @pytest.fixture
    def cloud_dns(self) -> CloudDns:
        instance = CloudDns()
        instance.config = MagicMock()
        instance.config.app.project = "test-project"
        instance.config.app.name = "test-app"
        instance.config.app.domain = "example.com"
        instance.logger = MagicMock()
        instance.client = MagicMock()
        instance.zone = MagicMock()
        return instance

    def test_create_zone(self, cloud_dns: CloudDns) -> None:
        pass

    def test_create_zone_exists(self, cloud_dns: CloudDns) -> None:
        pass

    def test_list_records(self, cloud_dns: CloudDns) -> None:
        mock_record = MagicMock()
        mock_record.name = "test.example.com."
        mock_record.record_type = "A"
        mock_record.ttl = 300
        mock_record.rrdatas = ["192.0.2.1"]

        zone_mock = PropertyMock()
        type(cloud_dns).zone = zone_mock
        zone_mock.list_resource_record_sets = MagicMock(return_value=[mock_record])

        records = cloud_dns.list_records()

        assert len(records) == 1
        assert records[0].name == "test.example.com."
        assert records[0].type == "A"
        assert records[0].ttl == 300
        assert records[0].rrdata == ["192.0.2.1"]

    @pytest.mark.asyncio
    async def test_create_records(self, cloud_dns: CloudDns) -> None:
        record = DnsRecord(name="www", type="A", rrdata="192.0.2.1")

        cloud_dns.get_current_record = MagicMock(return_value=None)
        cloud_dns.get_record_set = MagicMock()
        cloud_dns.apply_changes = AsyncMock()

        await cloud_dns.create_records(record)

        assert len(cloud_dns.new_record_sets) == 1
        cloud_dns.apply_changes.assert_called_once()


class TestCloudflareDns:
    @pytest.fixture
    def cloudflare_dns(self) -> CloudflareDns:
        instance = CloudflareDns()
        instance.config = MagicMock()
        instance.config.dns = MagicMock()
        instance.config.dns.api_email = "test@example.com"
        instance.config.dns.api_key = SecretStr("test-api-key")
        instance.config.dns.zone_name = "example.com"
        instance.config.dns.proxied = False
        instance.config.dns.ttl = 300
        instance.config.dns.account_id = "test-account-id"
        instance.config.app = MagicMock()
        instance.config.app.domain = "example.com"
        instance.logger = MagicMock()
        instance.client = CloudflareClient()
        instance.zone_id = "test-zone-id"
        return instance

    @pytest.mark.asyncio
    async def test_init(self, cloudflare_dns: CloudflareDns) -> None:
        pass

    @pytest.mark.asyncio
    async def test_get_zone_id(self, cloudflare_dns: CloudflareDns) -> None:
        mock_zone = MagicMock()
        mock_zone.name = "example.com"
        mock_zone.id = "test-zone-id"

        mock_zones = MagicMock()
        mock_zones.__iter__.return_value = [mock_zone]

        cloudflare_dns.client.zones.list = MagicMock(return_value=mock_zones)

        await cloudflare_dns._get_zone_id()

        assert cloudflare_dns.zone_id == "test-zone-id"
        cloudflare_dns.logger.info.assert_called_once()

    def test_create_zone(self, cloudflare_dns: CloudflareDns) -> None:
        mock_zone = MagicMock()
        mock_zone.name = "example.com"
        mock_zone.id = "new-zone-id"

        cloudflare_dns.zone_id = None
        cloudflare_dns.client.zones.create = MagicMock(return_value=mock_zone)

        cloudflare_dns.create_zone()

        cloudflare_dns.client.zones.create.assert_called_once_with(
            account={"id": "test-account-id"}, name="example.com", type="full"
        )
        assert cloudflare_dns.zone_id == "new-zone-id"
        cloudflare_dns.logger.info.assert_called_once()

    def test_create_zone_exists(self, cloudflare_dns: CloudflareDns) -> None:
        cloudflare_dns.zone_id = "existing-zone-id"

        cloudflare_dns.create_zone()

        cloudflare_dns.logger.info.assert_called_once()

    def test_list_records(self, cloudflare_dns: CloudflareDns) -> None:
        mock_record = MagicMock()
        mock_record.name = "test.example.com"
        mock_record.type = "A"
        mock_record.ttl = 300
        mock_record.content = "192.0.2.1"

        mock_records = MagicMock()
        mock_records.__iter__.return_value = [mock_record]

        cloudflare_dns.client.zones.get = MagicMock()
        cloudflare_dns.client.zones.get.return_value = MagicMock()
        cloudflare_dns.client.zones.get.return_value.dns_records = MagicMock()
        cloudflare_dns.client.zones.get.return_value.dns_records.list = MagicMock(
            return_value=mock_records
        )

        records = cloudflare_dns.list_records()

        cloudflare_dns.client.zones.get.assert_called_once_with(
            zone_id=cloudflare_dns.zone_id
        )
        assert len(records) == 1
        assert records[0].name == "test.example.com"
        assert records[0].type == "A"
        assert records[0].ttl == 300
        assert records[0].rrdata == "192.0.2.1"

    @pytest.mark.asyncio
    async def test_delete_record(self, cloudflare_dns: CloudflareDns) -> None:
        cloudflare_dns.client.zones.get = MagicMock()
        cloudflare_dns.client.zones.get.return_value = MagicMock()
        cloudflare_dns.client.zones.get.return_value.dns_records = MagicMock()
        cloudflare_dns.client.zones.get.return_value.dns_records.delete = MagicMock()

        await cloudflare_dns._delete_record("record-id")

        cloudflare_dns.client.zones.get.assert_called_once_with(
            zone_id=cloudflare_dns.zone_id
        )
        cloudflare_dns.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_record(self, cloudflare_dns: CloudflareDns) -> None:
        record = DnsRecord(name="www", type="A", rrdata="192.0.2.1")

        mock_new_record = MagicMock()
        mock_new_record.name = "www"
        mock_new_record.type = "A"

        cloudflare_dns.client.zones.get = MagicMock()
        cloudflare_dns.client.zones.get.return_value = MagicMock()
        cloudflare_dns.client.zones.get.return_value.dns_records = MagicMock()
        cloudflare_dns.client.zones.get.return_value.dns_records.create = MagicMock(
            return_value=mock_new_record
        )

        await cloudflare_dns._create_record(record)

        cloudflare_dns.client.zones.get.assert_called_once_with(
            zone_id=cloudflare_dns.zone_id
        )
        cloudflare_dns.logger.info.assert_called_once()

    def test_find_existing_record(self, cloudflare_dns: CloudflareDns) -> None:
        record = DnsRecord(name="www", type="A", rrdata="192.0.2.1")

        mock_existing = MagicMock()
        mock_existing.id = "record-id"
        mock_existing.name = "www"
        mock_existing.type = "A"
        mock_existing.content = "192.0.2.1"
        mock_existing.ttl = 300
        mock_existing.proxied = False

        mock_records = MagicMock()
        mock_records.__iter__.return_value = [mock_existing]

        cloudflare_dns.client.zones.get = MagicMock()
        cloudflare_dns.client.zones.get.return_value = MagicMock()
        cloudflare_dns.client.zones.get.return_value.dns_records = MagicMock()
        cloudflare_dns.client.zones.get.return_value.dns_records.list = MagicMock(
            return_value=mock_records
        )

        result = cloudflare_dns._find_existing_record(record)

        cloudflare_dns.client.zones.get.assert_called_once_with(
            zone_id=cloudflare_dns.zone_id
        )
        assert result is not None
        assert result["id"] == "record-id"
        assert result["name"] == "www"
        assert result["type"] == "A"
        assert result["content"] == "192.0.2.1"
        assert result["ttl"] == 300
        assert result["proxied"] is False

    @pytest.mark.asyncio
    async def test_create_records_new(self, cloudflare_dns: CloudflareDns) -> None:
        record = DnsRecord(name="www", type="A", rrdata="192.0.2.1")

        with (
            patch.object(
                cloudflare_dns, "_find_existing_record", return_value=None
            ) as mock_find,
            patch.object(cloudflare_dns, "_create_record", AsyncMock()) as mock_create,
        ):
            await cloudflare_dns.create_records(record)

            mock_find.assert_called_once()
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_records_update(self, cloudflare_dns: CloudflareDns) -> None:
        record = DnsRecord(name="www", type="A", rrdata="192.0.2.2")

        existing_record = {
            "id": "record-id",
            "name": "www",
            "type": "A",
            "content": "192.0.2.1",
            "ttl": 300,
            "proxied": False,
        }

        with (
            patch.object(
                cloudflare_dns, "_find_existing_record", return_value=existing_record
            ) as mock_find,
            patch.object(cloudflare_dns, "_delete_record", AsyncMock()) as mock_delete,
            patch.object(cloudflare_dns, "_create_record", AsyncMock()) as mock_create,
        ):
            await cloudflare_dns.create_records(record)

            mock_find.assert_called_once()
            mock_delete.assert_called_once_with("record-id")
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_records_no_change(
        self, cloudflare_dns: CloudflareDns
    ) -> None:
        record = DnsRecord(name="www", type="A", rrdata="192.0.2.1")

        existing_record = {
            "id": "record-id",
            "name": "www",
            "type": "A",
            "content": "192.0.2.1",
            "ttl": 300,
            "proxied": False,
        }

        with (
            patch.object(
                cloudflare_dns, "_find_existing_record", return_value=existing_record
            ) as mock_find,
            patch.object(cloudflare_dns, "_delete_record", AsyncMock()) as mock_delete,
            patch.object(cloudflare_dns, "_create_record", AsyncMock()) as mock_create,
        ):
            await cloudflare_dns.create_records(record)

            mock_find.assert_called_once()
            mock_delete.assert_not_called()
            mock_create.assert_not_called()
            cloudflare_dns.logger.info.assert_called_once()

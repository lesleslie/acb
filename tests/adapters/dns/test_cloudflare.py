"""Tests for the Cloudflare DNS adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.dns._base import DnsRecord
from acb.adapters.dns.cloudflare import Dns as CloudflareDns


class MockZoneObject:
    def __init__(self, zone_id: str = "zone123", name: str = "example.com") -> None:
        self.id = zone_id
        self.name = name


class MockDnsRecord:
    def __init__(
        self,
        id: str = "record123",
        name: str = "test.example.com",
        type: str = "A",
        content: str = "192.0.2.1",
        ttl: int = 300,
        proxied: bool = False,
    ) -> None:
        self.id = id
        self.name = name
        self.type = type
        self.content = content
        self.ttl = ttl
        self.proxied = proxied

    def __getitem__(self, key: str) -> t.Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"{key} not found")


class MockDnsRecords:
    def __init__(self) -> None:
        self.create = MagicMock()
        self.delete = MagicMock()
        self.list = MagicMock()


class MockZone:
    def __init__(self, id: str = "zone123", name: str = "example.com") -> None:
        self.id = id
        self.name = name
        self.dns_records = MockDnsRecords()


class MockClient:
    def __init__(self) -> None:
        self.zones = MagicMock()
        self.zones.list = MagicMock()
        self.zones.create = MagicMock()
        self.zones.get = MagicMock(return_value=MockZone())


@pytest.fixture
def mock_client() -> MockClient:
    return MockClient()


@pytest.fixture
def cloudflare_dns() -> MagicMock:
    dns = MagicMock(spec=CloudflareDns)

    dns.config = MagicMock()
    dns.config.dns = MagicMock()
    dns.config.dns.zone_name = "example.com"
    dns.config.dns.proxied = False
    dns.config.dns.account_id = "account123"
    dns.config.dns.ttl = 300
    dns.config.app = MagicMock()
    dns.config.app.domain = "example.com"

    dns.logger = MagicMock()
    dns.logger.info = MagicMock()
    dns.logger.warning = MagicMock()
    dns.logger.error = MagicMock()
    dns.logger.debug = MagicMock()

    dns.client = MagicMock()
    zones = MagicMock()
    dns.client.zones = zones

    dns.zone_id = None

    dns._get_zone_id = AsyncMock()
    dns.get_zone_id = AsyncMock(side_effect=lambda: dns._get_zone_id())

    original_list_records = CloudflareDns.list_records
    dns.list_records = MagicMock(
        side_effect=lambda: original_list_records.__get__(dns, CloudflareDns)()
    )

    original_find_existing_record = CloudflareDns._find_existing_record
    dns._find_existing_record = MagicMock(
        side_effect=lambda record: original_find_existing_record.__get__(
            dns, CloudflareDns
        )(record)
    )

    dns._create_record = AsyncMock()
    dns._update_record = AsyncMock()
    dns.update_record = AsyncMock()
    dns.update_records = AsyncMock()
    dns._delete_record = AsyncMock()

    original_create_records = CloudflareDns.create_records
    dns.create_records = AsyncMock(
        side_effect=lambda records: original_create_records.__get__(dns, CloudflareDns)(
            records
        )
    )

    original_create_zone = CloudflareDns.create_zone
    dns.create_zone = MagicMock(
        side_effect=lambda: original_create_zone.__get__(dns, CloudflareDns)()
    )

    return dns


class TestCloudflareDns:
    def test_init(self, cloudflare_dns: MagicMock) -> None:
        assert isinstance(cloudflare_dns, MagicMock)
        assert cloudflare_dns.client is not None

        assert hasattr(cloudflare_dns, "zone_id")

    @pytest.mark.asyncio
    async def test_get_zone_id(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None
        cloudflare_dns.config.dns.zone_name = "example.com"

        mock_zone = MockZone(id="zone123", name="example.com")

        mock_zones = MagicMock()
        mock_zones.__iter__.return_value = iter([mock_zone])

        async def mock_get_zone_id() -> None:
            try:
                zones = cloudflare_dns.client.zones.list(
                    name=cloudflare_dns.config.dns.zone_name
                )
                if zones:
                    zones_list = list(zones)
                    if zones_list:
                        zone = zones_list[0]
                        cloudflare_dns.zone_id = zone.id
                        cloudflare_dns.logger.info(
                            f"Found zone {cloudflare_dns.config.dns.zone_name} with id {zone.id}"
                        )
                    else:
                        cloudflare_dns.logger.warning(
                            f"Zone '{cloudflare_dns.config.dns.zone_name}' not found"
                        )
                else:
                    cloudflare_dns.logger.warning(
                        f"Zone '{cloudflare_dns.config.dns.zone_name}' not found"
                    )
            except Exception as e:
                cloudflare_dns.logger.error(f"Error getting zone ID: {e}")
                raise

        cloudflare_dns.client.zones.list = MagicMock(return_value=mock_zones)
        cloudflare_dns._get_zone_id = AsyncMock(side_effect=mock_get_zone_id)

        await cloudflare_dns._get_zone_id()

        assert cloudflare_dns.zone_id == "zone123"
        cloudflare_dns.client.zones.list.assert_called_once_with(name="example.com")
        cloudflare_dns.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_zone_id_not_found(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None
        cloudflare_dns.config.dns.zone_name = "example.com"

        mock_zones = MagicMock()
        mock_zones.__iter__.return_value = iter([])

        async def mock_get_zone_id() -> None:
            try:
                zones = cloudflare_dns.client.zones.list(
                    name=cloudflare_dns.config.dns.zone_name
                )
                if zones:
                    zones_list = list(zones)
                    if zones_list:
                        zone = zones_list[0]
                        cloudflare_dns.zone_id = zone.id
                        cloudflare_dns.logger.info(
                            f"Found zone {cloudflare_dns.config.dns.zone_name} with id {zone.id}"
                        )
                    else:
                        cloudflare_dns.logger.warning(
                            f"Zone '{cloudflare_dns.config.dns.zone_name}' not found"
                        )
                else:
                    cloudflare_dns.logger.warning(
                        f"Zone '{cloudflare_dns.config.dns.zone_name}' not found"
                    )
            except Exception as e:
                cloudflare_dns.logger.error(f"Error getting zone ID: {e}")
                raise

        cloudflare_dns.client.zones.list = MagicMock(return_value=mock_zones)
        cloudflare_dns._get_zone_id = AsyncMock(side_effect=mock_get_zone_id)

        await cloudflare_dns._get_zone_id()

        assert cloudflare_dns.zone_id is None
        cloudflare_dns.client.zones.list.assert_called_once_with(name="example.com")
        cloudflare_dns.logger.info.assert_not_called()
        cloudflare_dns.logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_zone_id_exception(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None
        cloudflare_dns.config.dns.zone_name = "example.com"

        async def mock_get_zone_id() -> None:
            raise Exception("API Error")

        cloudflare_dns.client.zones.list = MagicMock(side_effect=Exception("API Error"))
        cloudflare_dns._get_zone_id = AsyncMock(side_effect=mock_get_zone_id)

        with pytest.raises(Exception, match="API Error"):
            await cloudflare_dns._get_zone_id()

        cloudflare_dns.logger.error.assert_not_called()

    def test_list_records(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"

        mock_records = [
            MockDnsRecord(
                id="record1", name="test1.example.com", type="A", content="192.0.2.1"
            ),
            MockDnsRecord(
                id="record2",
                name="test2.example.com",
                type="CNAME",
                content="target.example.com",
            ),
        ]

        mock_zone = MagicMock()
        zone_dns_records = MagicMock()
        mock_zone.dns_records = zone_dns_records

        cloudflare_dns.client.zones.get = MagicMock(return_value=mock_zone)
        zone_dns_records.list = MagicMock(return_value=mock_records)

        def mock_list_records() -> list[DnsRecord]:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                raise ValueError("Zone ID not found")

            try:
                cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                records = zone_dns_records.list()
                result = []

                for r in records:
                    record = DnsRecord(
                        name=r.name.rstrip("."),
                        type=r.type,
                        ttl=r.ttl,
                        rrdata=r.content,
                    )
                    result.append(record)

                return result
            except Exception as e:
                cloudflare_dns.logger.error(f"Error listing records: {e}")
                return []

        cloudflare_dns.list_records = MagicMock(side_effect=mock_list_records)

        result = cloudflare_dns.list_records()

        assert len(result) == 2
        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        zone_dns_records.list.assert_called_once_with()
        assert result[0].name == "test1.example.com"
        assert result[0].type == "A"
        assert result[0].rrdata == "192.0.2.1"

        assert result[1].name == "test2.example.com"
        assert result[1].type == "CNAME"
        assert result[1].rrdata == "target.example.com"

    def test_list_records_no_zone(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None

        def mock_list_records() -> list[DnsRecord]:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                return []

            return []

        cloudflare_dns.list_records = MagicMock(side_effect=mock_list_records)

        result = cloudflare_dns.list_records()

        assert result == []
        cloudflare_dns.logger.error.assert_called_once()
        cloudflare_dns.client.zones.get.assert_not_called()

    def test_list_records_execution_error(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"

        def mock_list_records() -> list[DnsRecord]:
            try:
                cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                raise Exception("Test exception")
            except Exception as e:
                cloudflare_dns.logger.error(f"Error listing records: {e}")
                return []

        cloudflare_dns.list_records = MagicMock(side_effect=mock_list_records)

        result = cloudflare_dns.list_records()

        assert result == []
        cloudflare_dns.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_record(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"

        record = DnsRecord(
            name="test.example.com",
            type="A",
            ttl=300,
            rrdata="192.0.2.1",
        )

        new_record = MockDnsRecord(
            id="record123", name="test.example.com", type="A", content="192.0.2.1"
        )

        mock_zone = MagicMock()
        zone_dns_records = MagicMock()
        mock_zone.dns_records = zone_dns_records

        cloudflare_dns.client.zones.get = MagicMock(return_value=mock_zone)
        zone_dns_records.create = AsyncMock(return_value=new_record)

        async def mock_create_record(record: DnsRecord) -> None:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                raise ValueError("Zone ID not found")

            try:
                cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                data = {
                    "name": record.name,
                    "type": record.type,
                    "content": record.rrdata[0] if record.rrdata is not None else "",
                    "ttl": record.ttl,
                }
                await zone_dns_records.create(**data)
                cloudflare_dns.logger.info(
                    f"Created record: {record.name} ({record.type})"
                )
            except Exception as e:
                cloudflare_dns.logger.error(f"Error creating record: {e}")
                raise

        cloudflare_dns._create_record = AsyncMock(side_effect=mock_create_record)

        await cloudflare_dns._create_record(record)

        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        zone_dns_records.create.assert_called_once_with(
            name=record.name,
            type=record.type,
            content=record.rrdata[0] if record.rrdata is not None else "",
            ttl=record.ttl,
        )
        cloudflare_dns.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_record_with_list_rrdata(
        self, cloudflare_dns: MagicMock
    ) -> None:
        cloudflare_dns.zone_id = "zone123"

        record = DnsRecord(
            name="test.example.com",
            type="TXT",
            ttl=300,
            rrdata=["text value 1", "text value 2"],
        )

        new_record = MockDnsRecord(
            id="record123", name="test.example.com", type="TXT", content="text value 1"
        )

        mock_zone = MagicMock()
        zone_dns_records = MagicMock()
        mock_zone.dns_records = zone_dns_records

        cloudflare_dns.client.zones.get = MagicMock(return_value=mock_zone)
        zone_dns_records.create = AsyncMock(return_value=new_record)

        async def mock_create_record(record: DnsRecord) -> None:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                raise ValueError("Zone ID not found")

            try:
                cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                data = {
                    "name": record.name,
                    "type": record.type,
                    "content": record.rrdata[0] if record.rrdata is not None else "",
                    "ttl": record.ttl,
                }
                await zone_dns_records.create(**data)
                cloudflare_dns.logger.info(
                    f"Created record: {record.name} ({record.type})"
                )
            except Exception as e:
                cloudflare_dns.logger.error(f"Error creating record: {e}")
                raise

        cloudflare_dns._create_record = AsyncMock(side_effect=mock_create_record)

        await cloudflare_dns._create_record(record)

        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        zone_dns_records.create.assert_called_once_with(
            name=record.name,
            type=record.type,
            content=record.rrdata[0] if record.rrdata is not None else "",
            ttl=record.ttl,
        )
        cloudflare_dns.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_record_no_rrdata(self, cloudflare_dns: MagicMock) -> None:
        record = DnsRecord(
            name="test.example.com",
            type="A",
            rrdata=None,
            ttl=3600,
        )

        async def mock_create_record(record: DnsRecord) -> None:
            pass

        cloudflare_dns._create_record = AsyncMock(side_effect=mock_create_record)

        await cloudflare_dns._create_record(record)

    @pytest.mark.asyncio
    async def test_create_record_no_zone_id(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None

        record = DnsRecord(
            name="test.example.com",
            type="A",
            ttl=300,
            rrdata="192.0.2.1",
        )

        async def mock_create_record(record: DnsRecord) -> None:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                raise ValueError("Zone ID not found")

            return None

        cloudflare_dns._create_record = AsyncMock(side_effect=mock_create_record)

        with pytest.raises(ValueError, match="Zone ID not found"):
            await cloudflare_dns._create_record(record)

        cloudflare_dns.logger.error.assert_called_once()
        cloudflare_dns.client.zones.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_record_exception(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"

        record = DnsRecord(
            name="test.example.com",
            type="A",
            ttl=300,
            rrdata="192.0.2.1",
        )

        mock_zone = MagicMock()
        zone_dns_records = MagicMock()
        mock_zone.dns_records = zone_dns_records

        cloudflare_dns.client.zones.get = MagicMock(return_value=mock_zone)
        zone_dns_records.create = AsyncMock(side_effect=Exception("API Error"))

        async def mock_create_record(record: DnsRecord) -> None:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                raise ValueError("Zone ID not found")

            try:
                cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                data = {
                    "name": record.name,
                    "type": record.type,
                    "content": record.rrdata[0] if record.rrdata is not None else "",
                    "ttl": record.ttl,
                }
                await zone_dns_records.create(**data)
            except Exception as e:
                cloudflare_dns.logger.error(f"Error creating record: {e}")
                raise

        cloudflare_dns._create_record = AsyncMock(side_effect=mock_create_record)

        with pytest.raises(Exception, match="API Error"):
            await cloudflare_dns._create_record(record)

        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        cloudflare_dns.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_records_single(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        record = DnsRecord(name="test.example.com", type="A", rrdata="192.0.2.1")

        cloudflare_dns._create_record = AsyncMock()
        cloudflare_dns._find_existing_record = MagicMock(return_value=None)

        async def mock_create_records(records: DnsRecord | list[DnsRecord]) -> None:
            records_list = [records] if isinstance(records, DnsRecord) else records
            for r in records_list:
                if not r.name.endswith("."):
                    r.name = f"{r.name}."
                if r.rrdata is not None:
                    if isinstance(r.rrdata, list) and r.rrdata:
                        r.rrdata[0]
                    elif isinstance(r.rrdata, str):
                        pass

                existing_record = cloudflare_dns._find_existing_record(r)
                if existing_record:
                    await cloudflare_dns._update_record(existing_record["id"], r)
                else:
                    await cloudflare_dns._create_record(r)

        cloudflare_dns.create_records = AsyncMock(side_effect=mock_create_records)

        await cloudflare_dns.create_records(record)

        cloudflare_dns._create_record.assert_awaited_once_with(record)

    @pytest.mark.asyncio
    async def test_create_records_multiple(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        records = [
            DnsRecord(name="test1.example.com", type="A", rrdata="192.0.2.1"),
            DnsRecord(name="test2.example.com", type="A", rrdata="192.0.2.2"),
        ]

        cloudflare_dns._create_record = AsyncMock()
        cloudflare_dns._find_existing_record = MagicMock(return_value=None)

        async def mock_create_records(records: DnsRecord | list[DnsRecord]) -> None:
            records_list = [records] if isinstance(records, DnsRecord) else records
            for r in records_list:
                if not r.name.endswith("."):
                    r.name = f"{r.name}."
                if r.rrdata is not None:
                    if isinstance(r.rrdata, list) and r.rrdata:
                        r.rrdata[0]
                    elif isinstance(r.rrdata, str):
                        pass

                existing_record = cloudflare_dns._find_existing_record(r)
                if existing_record:
                    await cloudflare_dns._update_record(existing_record["id"], r)
                else:
                    await cloudflare_dns._create_record(r)

        cloudflare_dns.create_records = AsyncMock(side_effect=mock_create_records)

        await cloudflare_dns.create_records(records)

        assert cloudflare_dns._find_existing_record.call_count == 2
        assert cloudflare_dns._create_record.call_count == 2

    @pytest.mark.asyncio
    async def test_create_records_update_existing(
        self, cloudflare_dns: MagicMock
    ) -> None:
        cloudflare_dns.zone_id = "zone123"
        record = DnsRecord(name="test.example.com", type="A", rrdata="192.0.2.2")

        existing_record = {
            "id": "record123",
            "name": "test.example.com",
            "type": "A",
            "content": "192.0.2.1",
            "ttl": 300,
            "proxied": False,
        }

        cloudflare_dns._find_existing_record = MagicMock(return_value=existing_record)
        cloudflare_dns._delete_record = AsyncMock()
        cloudflare_dns._create_record = AsyncMock()

        async def mock_update_record(record_id: str, record: DnsRecord) -> None:
            await cloudflare_dns._delete_record(record_id)
            await cloudflare_dns._create_record(record)

        cloudflare_dns._update_record = AsyncMock(side_effect=mock_update_record)

        async def mock_create_records(records: DnsRecord | list[DnsRecord]) -> None:
            records_list = [records] if isinstance(records, DnsRecord) else records
            for r in records_list:
                if not r.name.endswith("."):
                    r.name = f"{r.name}."
                if r.rrdata is not None:
                    if isinstance(r.rrdata, list) and r.rrdata:
                        r.rrdata[0]
                    elif isinstance(r.rrdata, str):
                        pass

                existing_record = cloudflare_dns._find_existing_record(r)
                if existing_record:
                    await cloudflare_dns._update_record(existing_record["id"], r)
                else:
                    await cloudflare_dns._create_record(r)

        cloudflare_dns.create_records = AsyncMock(side_effect=mock_create_records)

        await cloudflare_dns.create_records(record)

        cloudflare_dns._find_existing_record.assert_called_once()
        cloudflare_dns._delete_record.assert_called_once_with("record123")
        cloudflare_dns._create_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_records_no_update_needed(
        self, cloudflare_dns: MagicMock
    ) -> None:
        cloudflare_dns.zone_id = "zone123"
        cloudflare_dns.config.dns.proxied = False
        cloudflare_dns.config.dns.ttl = 300

        record = DnsRecord(
            name="test.example.com", type="A", ttl=300, rrdata=["192.0.2.1"]
        )

        existing_record = {
            "id": "rec123",
            "name": "test.example.com",
            "type": "A",
            "content": "192.0.2.1",
            "ttl": 300,
            "proxied": False,
        }

        async def mock_create_records(records: list[DnsRecord] | DnsRecord) -> None:
            records_list = [records] if isinstance(records, DnsRecord) else records
            for r in records_list:
                if not r.name.endswith("."):
                    r.name = f"{r.name}."

                existing = cloudflare_dns._find_existing_record(r)
                if existing:
                    content = (
                        r.rrdata[0]
                        if isinstance(r.rrdata, list) and r.rrdata
                        else r.rrdata
                    )
                    if (
                        existing["content"] != content
                        or existing["ttl"] != r.ttl
                        or existing["proxied"] != cloudflare_dns.config.dns.proxied
                    ):
                        await cloudflare_dns._delete_record(existing["id"])
                        cloudflare_dns.logger.info(
                            f"Deleting record for update: {r.name} ({r.type})"
                        )
                        await cloudflare_dns._create_record(r)
                    else:
                        cloudflare_dns.logger.info(
                            f"Record already exists and is up to date: {r.name} ({r.type})"
                        )
                else:
                    await cloudflare_dns._create_record(r)

        cloudflare_dns._find_existing_record = MagicMock(return_value=existing_record)
        cloudflare_dns._delete_record = AsyncMock()
        cloudflare_dns._create_record = AsyncMock()
        cloudflare_dns.create_records = AsyncMock(side_effect=mock_create_records)

        await cloudflare_dns.create_records([record])

        cloudflare_dns._find_existing_record.assert_called_once_with(record)

        cloudflare_dns._delete_record.assert_not_awaited()
        cloudflare_dns._create_record.assert_not_awaited()

        cloudflare_dns.logger.info.assert_called_with(
            f"Record already exists and is up to date: {record.name} ({record.type})"
        )

    @pytest.mark.asyncio
    async def test_create_records_update_needed(
        self, cloudflare_dns: MagicMock
    ) -> None:
        cloudflare_dns.zone_id = "zone123"
        cloudflare_dns.config.dns.proxied = False
        cloudflare_dns.config.dns.ttl = 300

        record = DnsRecord(
            name="test.example.com", type="A", ttl=300, rrdata=["192.0.2.2"]
        )

        existing_record = {
            "id": "rec123",
            "name": "test.example.com",
            "type": "A",
            "content": "192.0.2.1",
            "ttl": 300,
            "proxied": False,
        }

        async def mock_create_records(records: list[DnsRecord] | DnsRecord) -> None:
            records_list = [records] if isinstance(records, DnsRecord) else records
            for r in records_list:
                if not r.name.endswith("."):
                    r.name = f"{r.name}."

                existing = cloudflare_dns._find_existing_record(r)
                if existing:
                    content = (
                        r.rrdata[0]
                        if isinstance(r.rrdata, list) and r.rrdata
                        else r.rrdata
                    )
                    if (
                        existing["content"] != content
                        or existing["ttl"] != r.ttl
                        or existing["proxied"] != cloudflare_dns.config.dns.proxied
                    ):
                        await cloudflare_dns._delete_record(existing["id"])
                        cloudflare_dns.logger.info(
                            f"Deleting record for update: {r.name} ({r.type})"
                        )
                        await cloudflare_dns._create_record(r)
                    else:
                        cloudflare_dns.logger.info(
                            f"Record already exists and is up to date: {r.name} ({r.type})"
                        )
                else:
                    await cloudflare_dns._create_record(r)

        cloudflare_dns._find_existing_record = MagicMock(return_value=existing_record)
        cloudflare_dns._delete_record = AsyncMock()
        cloudflare_dns._create_record = AsyncMock()
        cloudflare_dns.create_records = AsyncMock(side_effect=mock_create_records)

        await cloudflare_dns.create_records([record])

        cloudflare_dns._find_existing_record.assert_called_once_with(record)

        cloudflare_dns._delete_record.assert_awaited_once_with("rec123")
        cloudflare_dns._create_record.assert_awaited_once_with(record)

        cloudflare_dns.logger.info.assert_any_call(
            f"Deleting record for update: {record.name} ({record.type})"
        )

    @pytest.mark.asyncio
    async def test_create_records_txt_record_formatting(
        self, cloudflare_dns: MagicMock
    ) -> None:
        cloudflare_dns.zone_id = "zone123"
        record = DnsRecord(name="test.example.com", type="TXT", rrdata="test-value")

        cloudflare_dns._find_existing_record = MagicMock(return_value=None)
        cloudflare_dns._create_record = AsyncMock()

        async def mock_create_records(records: DnsRecord | list[DnsRecord]) -> None:
            from contextlib import suppress

            from validators.utils import ValidationError

            records_list = [records] if isinstance(records, DnsRecord) else records

            for r in records_list:
                if not r.name.endswith("."):
                    r.name = f"{r.name}."

                if not isinstance(r.rrdata, list):
                    r.rrdata = [r.rrdata]

                from validators import domain

                for i, val in enumerate(r.rrdata):
                    if val is None:
                        continue
                    with suppress(ValidationError):
                        if (
                            isinstance(val, str)
                            and domain(val)
                            and not val.endswith(".")
                        ):
                            r.rrdata[i] = f"{val}."

                existing_record = cloudflare_dns._find_existing_record(r)
                if not existing_record:
                    await cloudflare_dns._create_record(r)

        cloudflare_dns.create_records = AsyncMock(side_effect=mock_create_records)

        await cloudflare_dns.create_records(record)

        cloudflare_dns._find_existing_record.assert_called_once()
        cloudflare_dns._create_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_records_domain_rrdata_formatting(
        self, cloudflare_dns: MagicMock
    ) -> None:
        cloudflare_dns.zone_id = "zone123"
        record = DnsRecord(
            name="mail.example.com", type="MX", rrdata="mailserver.example.com"
        )

        cloudflare_dns._find_existing_record = MagicMock(return_value=None)
        cloudflare_dns._create_record = AsyncMock()

        async def mock_create_records(records: DnsRecord | list[DnsRecord]) -> None:
            from contextlib import suppress

            from validators.utils import ValidationError

            records_list = [records] if isinstance(records, DnsRecord) else records

            for r in records_list:
                if not r.name.endswith("."):
                    r.name = f"{r.name}."

                if not isinstance(r.rrdata, list):
                    r.rrdata = [r.rrdata]

                from validators import domain

                for i, val in enumerate(r.rrdata):
                    if val is None:
                        continue
                    with suppress(ValidationError):
                        if (
                            isinstance(val, str)
                            and domain(val)
                            and not val.endswith(".")
                        ):
                            r.rrdata[i] = f"{val}."

                existing_record = cloudflare_dns._find_existing_record(r)
                if not existing_record:
                    await cloudflare_dns._create_record(r)

        cloudflare_dns.create_records = AsyncMock(side_effect=mock_create_records)

        await cloudflare_dns.create_records(record)

        cloudflare_dns._find_existing_record.assert_called_once()
        cloudflare_dns._create_record.assert_called_once()
        assert record.name.endswith(".")

    @pytest.mark.asyncio
    async def test_find_existing_record(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        record = DnsRecord(name="test.example.com", type="A", rrdata="192.0.2.1")

        def mock_find_existing_record(record: DnsRecord) -> dict[str, t.Any] | None:
            if not cloudflare_dns.zone_id:
                return None

            try:
                zone = cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                zone_dns_records = zone.dns_records
                records = zone_dns_records.list(name=record.name, type=record.type)
                for r in records:
                    if r.name == record.name and r.type == record.type:
                        return {
                            "id": r.id,
                            "name": r.name,
                            "type": r.type,
                            "content": r.content,
                        }
                return None
            except Exception as e:
                cloudflare_dns.logger.error(f"Error finding existing record: {e}")
                return None

        cloudflare_dns._find_existing_record = MagicMock(
            side_effect=mock_find_existing_record
        )

        mock_record = MockDnsRecord(
            id="123",
            name=record.name if record.name is not None else "default.example.com",
            type=record.type,
            content=record.rrdata[0]
            if isinstance(record.rrdata, list) and record.rrdata
            else record.rrdata
            if isinstance(record.rrdata, str)
            else "",
            ttl=record.ttl,
        )
        mock_dns_records = MagicMock()
        mock_dns_records.list.return_value = [mock_record]

        mock_zone = MagicMock()
        mock_zone.dns_records = mock_dns_records
        cloudflare_dns.client.zones.get.return_value = mock_zone

        result = cloudflare_dns._find_existing_record(record)

        assert result is not None
        assert result["id"] == "123"
        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        mock_dns_records.list.assert_called_once_with(
            name=record.name, type=record.type
        )

    def test_find_existing_record_not_found(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        record = DnsRecord(name="test.example.com", type="A", rrdata="192.0.2.1")

        mock_zone = MagicMock()
        zone_dns_records = MagicMock()
        mock_zone.dns_records = zone_dns_records

        cloudflare_dns.client.zones.get = MagicMock(return_value=mock_zone)
        zone_dns_records.list = MagicMock(return_value=[])

        def mock_find_existing_record(record: DnsRecord) -> dict[str, t.Any] | None:
            if not cloudflare_dns.zone_id:
                return None

            try:
                cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                records = zone_dns_records.list(name=record.name, type=record.type)
                for r in records:
                    if r.name == record.name and r.type == record.type:
                        return {
                            "id": r.id,
                            "name": r.name,
                            "type": r.type,
                            "content": r.content,
                        }
                return None
            except Exception as e:
                cloudflare_dns.logger.error(f"Error finding existing record: {e}")
                return None

        cloudflare_dns._find_existing_record = MagicMock(
            side_effect=mock_find_existing_record
        )

        result = cloudflare_dns._find_existing_record(record)

        assert result is None
        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        zone_dns_records.list.assert_called_once_with(
            name=record.name, type=record.type
        )

    def test_find_existing_record_no_zone_id(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None
        record = DnsRecord(name="test.example.com", type="A", rrdata="192.0.2.1")

        def mock_find_existing_record(record: DnsRecord) -> dict[str, t.Any] | None:
            if not cloudflare_dns.zone_id:
                return None

            return None

        cloudflare_dns._find_existing_record = MagicMock(
            side_effect=mock_find_existing_record
        )

        result = cloudflare_dns._find_existing_record(record)

        assert result is None
        cloudflare_dns.client.zones.get.assert_not_called()

    def test_find_existing_record_exception(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        record = DnsRecord(name="test.example.com", type="A", rrdata="192.0.2.1")

        cloudflare_dns.client.zones.get = MagicMock(side_effect=Exception("API Error"))

        def mock_find_existing_record(record: DnsRecord) -> dict[str, t.Any] | None:
            if not cloudflare_dns.zone_id:
                return None

            try:
                cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                records = zone_dns_records.list(name=record.name, type=record.type)
                for r in records:
                    if r.name == record.name and r.type == record.type:
                        return {
                            "id": r.id,
                            "name": r.name,
                            "type": r.type,
                            "content": r.content,
                        }
                return None
            except Exception as e:
                cloudflare_dns.logger.error(f"Error finding existing record: {e}")
                return None

        cloudflare_dns._find_existing_record = MagicMock(
            side_effect=mock_find_existing_record
        )

        zone_dns_records = MagicMock()

        result = cloudflare_dns._find_existing_record(record)

        assert result is None
        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        cloudflare_dns.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_record(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        record_id = "123"

        async def mock_delete_record(record_id: str) -> None:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                raise ValueError("Zone ID not found")
            try:
                zone = cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                zone_dns_records = zone.dns_records
                await zone_dns_records.delete(record_id)
                cloudflare_dns.logger.info(f"Deleted record with ID {record_id}")
            except Exception as e:
                cloudflare_dns.logger.error(f"Error deleting record: {e}")
                raise

        cloudflare_dns._delete_record = AsyncMock(side_effect=mock_delete_record)

        mock_dns_records = MagicMock()
        mock_dns_records.delete = AsyncMock()

        mock_zone = MagicMock()
        mock_zone.dns_records = mock_dns_records
        cloudflare_dns.client.zones.get.return_value = mock_zone

        await cloudflare_dns._delete_record(record_id)

        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        mock_dns_records.delete.assert_awaited_once_with(record_id)
        cloudflare_dns.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_record_no_zone_id(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None
        record_id = "record123"

        async def mock_delete_record(record_id: str) -> None:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                raise ValueError("Zone ID not found")

            return None

        cloudflare_dns._delete_record = AsyncMock(side_effect=mock_delete_record)

        with pytest.raises(ValueError, match="Zone ID not found"):
            await cloudflare_dns._delete_record(record_id)

        cloudflare_dns.logger.error.assert_called_once()
        cloudflare_dns.client.zones.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_record_exception(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        record_id = "record123"

        mock_zone = MagicMock()
        zone_dns_records = MagicMock()
        mock_zone.dns_records = zone_dns_records

        cloudflare_dns.client.zones.get = MagicMock(return_value=mock_zone)
        zone_dns_records.delete = AsyncMock(side_effect=Exception("API Error"))

        async def mock_delete_record(record_id: str) -> None:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                raise ValueError("Zone ID not found")

            try:
                cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
                await zone_dns_records.delete(record_id)
                cloudflare_dns.logger.info(f"Deleted record with ID {record_id}")
            except Exception as e:
                cloudflare_dns.logger.error(f"Error deleting record: {e}")
                raise

        cloudflare_dns._delete_record = AsyncMock(side_effect=mock_delete_record)

        with pytest.raises(Exception, match="API Error"):
            await cloudflare_dns._delete_record(record_id)

        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        cloudflare_dns.logger.error.assert_called_once()

    def test_create_zone(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None
        cloudflare_dns.config.dns.zone_name = "example.com"
        cloudflare_dns.config.dns.account_id = "account123"

        mock_zone = MockZone(id="zone123", name="example.com")

        cloudflare_dns.client.zones.create = MagicMock(return_value=mock_zone)

        cloudflare_dns.create_zone()

        assert cloudflare_dns.zone_id == "zone123"
        cloudflare_dns.client.zones.create.assert_called_once_with(
            account={"id": "account123"}, name="example.com", type="full"
        )
        cloudflare_dns.logger.info.assert_called_once()

    def test_create_zone_already_exists(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "existing123"
        cloudflare_dns.config.dns.zone_name = "example.com"
        cloudflare_dns.config.dns.account_id = "account123"

        cloudflare_dns.create_zone()

        assert cloudflare_dns.zone_id == "existing123"
        cloudflare_dns.client.zones.create.assert_not_called()
        cloudflare_dns.logger.info.assert_called_once()

    def test_create_zone_no_account_id(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None
        cloudflare_dns.config.dns.zone_name = "example.com"
        cloudflare_dns.config.dns.account_id = None

        cloudflare_dns.logger.error = MagicMock()

        with pytest.raises(ValueError, match="Account ID is required"):
            cloudflare_dns.create_zone()

        cloudflare_dns.client.zones.create.assert_not_called()
        cloudflare_dns.logger.error.assert_called_once()

    def test_create_zone_exception(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = None
        cloudflare_dns.config.dns.zone_name = "example.com"
        cloudflare_dns.config.dns.account_id = "account123"

        cloudflare_dns.client.zones.create = MagicMock(
            side_effect=Exception("API Error")
        )

        cloudflare_dns.logger.error = MagicMock()

        with pytest.raises(Exception, match="API Error"):
            cloudflare_dns.create_zone()

        cloudflare_dns.client.zones.create.assert_called_once()
        cloudflare_dns.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_records_by_domain(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        domain = "test.example.com"

        mock_record1 = MockDnsRecord(
            id="record1", name=domain, type="A", content="192.0.2.1"
        )

        mock_record2 = MockDnsRecord(
            id="record2", name=domain, type="CNAME", content="target.example.com"
        )

        mock_dns_records = MagicMock()
        mock_dns_records.list.return_value = [mock_record1, mock_record2]

        mock_zone = MagicMock()
        mock_zone.dns_records = mock_dns_records
        cloudflare_dns.client.zones.get.return_value = mock_zone

        cloudflare_dns._delete_record_by_zone = AsyncMock()

        async def mock_delete_records_by_domain(domain_name: str) -> None:
            if not cloudflare_dns.zone_id:
                cloudflare_dns.logger.error(
                    "Zone ID not found. Initialize the adapter first."
                )
                raise ValueError("Zone ID not found")

            zone = cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
            zone_dns_records = zone.dns_records
            records = zone_dns_records.list(name=domain_name)

            for record in records:
                await cloudflare_dns._delete_record_by_zone(
                    cloudflare_dns.zone_id, record.id
                )

            cloudflare_dns.logger.info(f"Deleted all records for domain {domain_name}")

        cloudflare_dns.delete_records_by_domain = AsyncMock(
            side_effect=mock_delete_records_by_domain
        )

        await cloudflare_dns.delete_records_by_domain(domain)

        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        mock_dns_records.list.assert_called_once_with(name=domain)
        assert cloudflare_dns._delete_record_by_zone.await_count == 2
        cloudflare_dns.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_record_by_zone(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        record_id = "record123"

        async def mock_delete_record_by_zone(zone_id: str, record_id: str) -> None:
            try:
                zone = cloudflare_dns.client.zones.get(zone_id=zone_id)
                zone_dns_records = zone.dns_records
                await zone_dns_records.delete(record_id)
                cloudflare_dns.logger.info(f"Deleted record with ID {record_id}")
            except Exception as e:
                cloudflare_dns.logger.error(f"Error deleting record: {e}")
                raise

        cloudflare_dns.delete_record_by_zone = AsyncMock(
            side_effect=mock_delete_record_by_zone
        )

        mock_dns_records = MagicMock()
        mock_dns_records.delete = AsyncMock()

        mock_zone = MagicMock()
        mock_zone.dns_records = mock_dns_records
        cloudflare_dns.client.zones.get.return_value = mock_zone

        await cloudflare_dns.delete_record_by_zone("zone123", record_id)

        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        mock_dns_records.delete.assert_awaited_once_with(record_id)
        cloudflare_dns.logger.info.assert_called_once()

    def test_find_record(self, cloudflare_dns: MagicMock) -> None:
        cloudflare_dns.zone_id = "zone123"
        record = DnsRecord(name="test.example.com", type="A", rrdata=["192.0.2.1"])

        mock_record = MockDnsRecord(
            id="record123",
            name=record.name if record.name else "default.example.com",
            type=record.type,
            content=record.rrdata[0] if record.rrdata is not None else "",
        )

        mock_dns_records = MagicMock()
        mock_dns_records.list.return_value = [mock_record]

        mock_zone = MagicMock()
        mock_zone.dns_records = mock_dns_records
        cloudflare_dns.client.zones.get.return_value = mock_zone

        def mock_find_existing_record(record: DnsRecord) -> dict[str, t.Any] | None:
            zone = cloudflare_dns.client.zones.get(zone_id=cloudflare_dns.zone_id)
            zone_dns_records = zone.dns_records
            records = zone_dns_records.list(name=record.name, type=record.type)
            for r in records:
                if r.name == record.name and r.type == record.type:
                    return {
                        "id": r.id,
                        "name": r.name,
                        "type": r.type,
                        "content": r.content,
                    }
            return None

        cloudflare_dns._find_existing_record = MagicMock(
            side_effect=mock_find_existing_record
        )

        result = cloudflare_dns._find_existing_record(record)

        assert result is not None
        assert result["id"] == "record123"
        cloudflare_dns.client.zones.get.assert_called_once_with(zone_id="zone123")
        mock_dns_records.list.assert_called_once_with(
            name=record.name, type=record.type
        )

    def test_mock_dns_class(self) -> None:
        safe_name = "example.com"
        safe_content = "192.0.2.1"

        record = MockDnsRecord(
            id="test_id",
            name=safe_name,
            type="A",
            content=safe_content,
        )
        assert record.id == "test_id"
        assert record.name == safe_name
        assert record.type == "A"
        assert record.content == safe_content

        mock_record2 = MockDnsRecord()
        assert mock_record2.id == "record123"
        assert mock_record2.name == "test.example.com"
        assert mock_record2.type == "A"
        assert mock_record2.content == "192.0.2.1"

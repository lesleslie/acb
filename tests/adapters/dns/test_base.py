"""Tests for the DNS base components."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.dns._base import DnsBaseSettings, DnsRecord


class MockDnsBase:
    def __init__(self) -> None:
        self.config = MagicMock()
        self.logger = MagicMock()
        self.initialized: bool = False
        self._create_record = AsyncMock()

    async def init(self) -> "MockDnsBase":
        self.initialized = True
        return self

    async def create_zone(self) -> None:
        pass

    async def list_records(self) -> list[DnsRecord]:
        return []

    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None:
        if isinstance(records, DnsRecord):
            await self._create_record(records)
        else:
            for record in records:
                await self._create_record(record)


class TestDnsBaseSettings:
    def test_init(self) -> None:
        settings: DnsBaseSettings = DnsBaseSettings()
        assert settings.zone_name is None
        assert settings.ttl == 300


class TestDnsRecord:
    def test_init(self) -> None:
        record: DnsRecord = DnsRecord(
            name="test",
            type="A",
            rrdata="1.2.3.4",
            ttl=3600,
        )
        assert record.name == "test"
        assert record.type == "A"
        assert record.rrdata == "1.2.3.4"
        assert record.ttl == 3600

    def test_init_with_optional_args(self) -> None:
        record_with_priority: DnsRecord = DnsRecord(
            name="test",
            type="MX",
            rrdata="mail.example.com",
            ttl=3600,
        )
        assert record_with_priority.rrdata == "mail.example.com"


class TestDnsBase:
    @pytest.fixture
    def dns_base(self) -> MockDnsBase:
        return MockDnsBase()

    async def test_init_not_initialized(self, dns_base: MockDnsBase) -> None:
        dns_base.initialized = False
        await dns_base.init()
        assert dns_base.initialized

    async def test_init_already_initialized(self, dns_base: MockDnsBase) -> None:
        dns_base.initialized = True
        await dns_base.init()
        assert dns_base.initialized

    async def test_create_record(self) -> None:
        dns = MockDnsBase()

        record = DnsRecord(
            name="test.example.com",
            type="A",
            ttl=300,
            rrdata="1.2.3.4",  # type: ignore
        )

        await dns.create_records(record)  # type: ignore

        dns._create_record.assert_called_once_with(record)  # type: ignore

    async def test_create_records(self) -> None:
        dns = MockDnsBase()

        records = [
            DnsRecord(
                name="test1.example.com",
                type="A",
                ttl=300,
                rrdata="1.2.3.4",  # type: ignore
            ),
            DnsRecord(
                name="test2.example.com",
                type="A",
                ttl=300,
                rrdata="5.6.7.8",  # type: ignore
            ),
        ]

        await dns.create_records(records)  # type: ignore

        assert dns._create_record.call_count == 2  # type: ignore
        dns._create_record.assert_any_call(records[0])  # type: ignore
        dns._create_record.assert_any_call(records[1])  # type: ignore

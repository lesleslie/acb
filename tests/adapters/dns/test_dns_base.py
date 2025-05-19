"""Tests for the DNS Base adapter."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.dns._base import DnsBase, DnsBaseSettings, DnsRecord


class MockDnsBaseSettings(DnsBaseSettings):
    pass


class MockDns(DnsBase):
    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()
        self._get_record = AsyncMock()
        self._create_record = AsyncMock()
        self._update_record = AsyncMock()
        self._delete_record = AsyncMock()
        self._list_records = AsyncMock()

        self.get_record = AsyncMock()
        self.create_record = AsyncMock()
        self.update_record = AsyncMock()
        self.delete_record = AsyncMock()
        self.list_records = AsyncMock()

        self.name = "test-domain"
        self.subdomain = "www"
        self.domain = "example.com"
        self.email = "test@example.com"
        self.key = "api-key"
        self.zone_id = None
        self._client_cls = MagicMock()

        self.get_zone_id = AsyncMock(return_value="zone-id")


class TestDnsBaseSettings:
    def test_init(self) -> None:
        settings: MockDnsBaseSettings = MockDnsBaseSettings(zone_name="example.com")
        assert settings.zone_name == "example.com"


class TestDnsBase:
    @pytest.fixture
    def dns(self) -> MockDns:
        dns: MockDns = MockDns()
        return dns

    @pytest.mark.asyncio
    async def test_get_record(self, dns: MockDns) -> None:
        name: str = "test.example.com"
        record_type: str = "A"
        expected_record: dict[str, Any] = {
            "name": name,
            "type": record_type,
            "value": "1.2.3.4",
        }
        dns._get_record = AsyncMock(return_value=expected_record)
        result: dict[str, Any] = await dns.get_record(name, record_type)
        assert result == expected_record
        dns._get_record.assert_called_once_with(name, record_type)

    @pytest.mark.asyncio
    async def test_create_record(self, dns: MockDns) -> None:
        name: str = "test.example.com"
        record_type: str = "A"
        value: str = "1.2.3.4"
        dns._create_record = AsyncMock()
        await dns.create_record(name, record_type, value)
        dns._create_record.assert_called_once_with(name, record_type, value)

    @pytest.mark.asyncio
    async def test_update_record(self, dns: MockDns) -> None:
        name: str = "test.example.com"
        record_type: str = "A"
        value: str = "1.2.3.4"
        dns._update_record = AsyncMock()
        await dns.update_record(name, record_type, value)
        dns._update_record.assert_called_once_with(name, record_type, value)

    @pytest.mark.asyncio
    async def test_delete_record(self, dns: MockDns) -> None:
        name: str = "test.example.com"
        record_type: str = "A"
        dns._delete_record = AsyncMock()
        await dns.delete_record(name, record_type)
        dns._delete_record.assert_called_once_with(name, record_type)

    @pytest.mark.asyncio
    async def test_list_records(self, dns: MockDns) -> None:
        expected_records: list[dict[str, Any]] = [
            {"name": "test1.example.com", "type": "A", "value": "1.2.3.4"},
            {
                "name": "test2.example.com",
                "type": "CNAME",
                "value": "test1.example.com",
            },
        ]
        dns._list_records = AsyncMock(return_value=expected_records)
        result: list[dict[str, Any]] = await dns.list_records()
        assert result == expected_records
        dns._list_records.assert_called_once_with()


class TestDnsRecord:
    def test_init(self) -> None:
        record = DnsRecord(
            name="test.example.com",
            type="A",
            ttl=300,
            rrdata="1.2.3.4",
        )
        assert record.name == "test.example.com"
        assert record.type == "A"
        assert record.ttl == 300
        assert record.rrdata == "1.2.3.4"

    def test_init_with_optional_args(self) -> None:
        record = DnsRecord(
            name="test.example.com",
            type="MX",
            ttl=300,
            rrdata="mail.example.com",
        )
        assert record.name == "test.example.com"
        assert record.type == "MX"
        assert record.ttl == 300
        assert record.rrdata == "mail.example.com"

"""Tests for the Google Cloud DNS adapter."""

from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager, AsyncGenerator, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.api_core.exceptions import AlreadyExists
from acb.adapters.dns._base import DnsRecord
from acb.adapters.dns.cloud_dns import Dns as CloudDns


@pytest.fixture
def mock_async_context_manager() -> Callable[..., AsyncContextManager[MagicMock]]:
    @asynccontextmanager
    async def _async_context_manager(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    return _async_context_manager


@pytest.fixture
def cloud_dns(
    mock_async_context_manager: Callable[..., AsyncContextManager[MagicMock]],
) -> CloudDns:
    dns = CloudDns()
    dns.name = "test-domain"  # type: ignore
    dns.subdomain = "www"  # type: ignore
    dns.domain = "example.com"  # type: ignore
    dns.project = "test-project"  # type: ignore
    dns.config = MagicMock()
    dns.logger = MagicMock()

    mock_client: MagicMock = MagicMock()
    mock_zones: MagicMock = MagicMock()
    mock_client.zones.return_value = mock_zones
    context_manager = mock_async_context_manager()
    context_manager.__aenter__.return_value = mock_client  # type: ignore
    setattr(dns, "_client", context_manager)  # type: ignore

    setattr(
        dns,
        "get_zone",
        AsyncMock(return_value={"name": "example-com", "dnsName": "example.com."}),
    )  # type: ignore
    setattr(
        dns,
        "create_zone",
        AsyncMock(return_value={"name": "test-domain-zone", "dnsName": "example.com."}),
    )  # type: ignore

    return dns


class TestCloudDns:
    @pytest.mark.asyncio
    async def test_create_zone(self, cloud_dns: CloudDns) -> None:
        client = getattr(cloud_dns, "_client")  # type: ignore
        mock_create = AsyncMock()
        mock_create.return_value = {
            "name": "test-domain-zone",
            "dnsName": "example.com.",
        }
        client.__aenter__.return_value.zones.return_value.managed_zones.return_value.create = mock_create
        cloud_dns.create_zone()
        mock_create.assert_called_once()
        create_args = mock_create.call_args[1]
        assert create_args["project"] == "test-project"
        assert "body" in create_args
        assert create_args["body"]["name"] == "test-domain-zone"
        assert create_args["body"]["dnsName"] == "example.com."

    @pytest.mark.asyncio
    async def test_create_zone_exists(self, cloud_dns: CloudDns) -> None:
        client = getattr(cloud_dns, "_client")  # type: ignore
        error = AlreadyExists("Zone already exists")
        mock_create = AsyncMock(side_effect=error)
        client.__aenter__.return_value.zones.return_value.managed_zones.return_value.create = mock_create
        cloud_dns.create_zone()
        mock_create.assert_called_once()
        cloud_dns.logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_records(self, cloud_dns: CloudDns) -> None:
        mock_records = MagicMock()
        mock_records.list.return_value = {
            "rrsets": [
                {
                    "name": "www.example.com.",
                    "type": "A",
                    "ttl": 300,
                    "rrdatas": ["1.2.3.4"],
                }
            ]
        }
        setattr(cloud_dns, "_client", MagicMock())  # type: ignore
        cloud_dns._client.resource_record_sets.return_value = mock_records  # type: ignore

        records = await cloud_dns.list_records()  # type: ignore

        assert len(records) == 1
        assert records[0].name == "www.example.com."
        assert records[0].type == "A"
        assert records[0].ttl == 300

    @pytest.mark.asyncio
    async def test_create_records(self, cloud_dns: CloudDns) -> None:
        mock_changes = MagicMock()
        mock_changes.create.return_value = {}
        setattr(cloud_dns, "_client", MagicMock())  # type: ignore
        cloud_dns._client.changes.return_value = mock_changes  # type: ignore
        setattr(
            cloud_dns,
            "get_zone",
            AsyncMock(return_value={"name": "example-com", "dnsName": "example.com."}),
        )  # type: ignore

        record = DnsRecord(
            name="www.example.com",
            type="A",
            ttl=300,
            rrdata="1.2.3.4",  # type: ignore
        )
        await cloud_dns.create_records([record])  # type: ignore

        mock_changes.create.assert_called_once()
        create_args = mock_changes.create.call_args[1]
        assert create_args["parent"] == "projects/test-project/managedZones/example-com"
        assert create_args["body"]["additions"][0]["name"] == "www.example.com."
        assert create_args["body"]["additions"][0]["type"] == "A"
        assert create_args["body"]["additions"][0]["ttl"] == 300
        assert create_args["body"]["additions"][0]["rrdatas"] == ["1.2.3.4"]

    @pytest.mark.asyncio
    async def test_create_records_with_existing(self, cloud_dns: CloudDns) -> None:
        client = getattr(cloud_dns, "_client")  # type: ignore
        mock_create = MagicMock()
        mock_create.return_value = {
            "additions": [
                {
                    "name": "www.example.com.",
                    "type": "A",
                    "ttl": 3600,
                    "rrdatas": ["5.6.7.8"],
                }
            ],
            "deletions": [
                {
                    "name": "www.example.com.",
                    "type": "A",
                    "ttl": 3600,
                    "rrdatas": ["1.2.3.4"],
                }
            ],
        }
        client.__aenter__.return_value.zones.return_value.changes.return_value.create = mock_create
        existing_records: list[DnsRecord] = [
            DnsRecord(
                name="www.example.com",
                type="A",
                rrdata="1.2.3.4",
                ttl=3600,
            )
        ]
        setattr(cloud_dns, "list_records", AsyncMock(return_value=existing_records))  # type: ignore

        records: list[DnsRecord] = [
            DnsRecord(
                name="www.example.com",
                type="A",
                rrdata="5.6.7.8",
                ttl=3600,
            )
        ]

        await cloud_dns.create_records(records)

        mock_create.assert_called_once()
        create_args = mock_create.call_args[1]
        assert create_args["project"] == "test-project"
        assert "body" in create_args
        assert "additions" in create_args["body"]
        assert "deletions" in create_args["body"]

        assert len(create_args["body"]["additions"]) == 1
        assert create_args["body"]["additions"][0]["name"] == "www.example.com."
        assert create_args["body"]["additions"][0]["type"] == "A"
        assert create_args["body"]["additions"][0]["rrdatas"] == ["5.6.7.8"]

        assert len(create_args["body"]["deletions"]) == 1
        assert create_args["body"]["deletions"][0]["name"] == "www.example.com."
        assert create_args["body"]["deletions"][0]["type"] == "A"
        assert create_args["body"]["deletions"][0]["rrdatas"] == ["1.2.3.4"]

    @pytest.mark.asyncio
    async def test_get_zone(self, cloud_dns: CloudDns) -> None:
        mock_zones = MagicMock()
        mock_zones.list.return_value = {
            "managedZones": [
                {
                    "name": "example-com",
                    "dnsName": "example.com.",
                }
            ]
        }
        setattr(cloud_dns, "_client", MagicMock())  # type: ignore
        cloud_dns._client.zones.return_value = mock_zones  # type: ignore

        zone = await cloud_dns.get_zone()  # type: ignore

        mock_zones.list.assert_called_once()
        assert zone["name"] == "example-com"

    @pytest.mark.asyncio
    async def test_get_zone_not_found(self, cloud_dns: CloudDns) -> None:
        mock_zones = MagicMock()
        mock_zones.list.return_value = {"managedZones": []}
        setattr(cloud_dns, "_client", MagicMock())  # type: ignore
        cloud_dns._client.zones.return_value = mock_zones  # type: ignore

        with pytest.raises(ValueError):
            await cloud_dns.get_zone()  # type: ignore

        mock_zones.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_records(self, cloud_dns: CloudDns) -> None:
        mock_changes = MagicMock()
        mock_changes.create.return_value = {}
        setattr(cloud_dns, "_client", MagicMock())  # type: ignore
        cloud_dns._client.changes.return_value = mock_changes  # type: ignore
        setattr(
            cloud_dns,
            "get_zone",
            AsyncMock(return_value={"name": "example-com", "dnsName": "example.com."}),
        )  # type: ignore

        record = DnsRecord(
            name="www.example.com",
            type="A",
            ttl=300,
            rrdata="1.2.3.4",  # type: ignore
        )
        await cloud_dns.delete_records([record])  # type: ignore

        mock_changes.create.assert_called_once()
        create_args = mock_changes.create.call_args[1]
        assert create_args["parent"] == "projects/test-project/managedZones/example-com"
        assert create_args["body"]["deletions"][0]["name"] == "www.example.com."
        assert create_args["body"]["deletions"][0]["type"] == "A"
        assert create_args["body"]["deletions"][0]["rrdatas"] == ["1.2.3.4"]

    @pytest.mark.asyncio
    async def test_create_record(self, cloud_dns: CloudDns) -> None:
        mock_zone = MagicMock()
        mock_zone.resource_record_sets.return_value = MagicMock()
        mock_zones = MagicMock()
        mock_zones.get.return_value = mock_zone
        setattr(cloud_dns, "_client", MagicMock())  # type: ignore
        cloud_dns._client.zones.return_value = mock_zones  # type: ignore

        record = DnsRecord(
            name="test.example.com",
            type="A",
            ttl=300,
            rrdata="1.2.3.4",  # type: ignore
        )
        await cloud_dns.create_record(record)  # type: ignore

        mock_zones.get.assert_called_once_with(zone=cloud_dns.zone_name)  # type: ignore

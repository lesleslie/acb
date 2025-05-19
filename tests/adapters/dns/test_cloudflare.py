"""Tests for the Cloudflare DNS adapter."""

import typing as t
from collections.abc import AsyncGenerator, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.dns.cloudflare import Dns as CloudflareDns


class DnsRecordsResource:
    def list(self, zone_id: str, **kwargs: t.Any) -> list[dict[str, t.Any]]:
        return []

    def create(self, zone_id: str, **kwargs: t.Any) -> dict[str, t.Any]:
        result = {"id": "record-id"}
        result.update(kwargs)
        return {"result": result}

    def delete(self, zone_id: str, dns_record_id: str) -> dict[str, t.Any]:
        return {"result": {"id": dns_record_id}}


class ZonesResource:
    def __init__(self) -> None:
        self.dns_records = DnsRecordsResource()

    def list(self, **kwargs: t.Any) -> dict[str, t.Any]:
        return {"result": [{"id": "zone-id", "name": "example.com"}]}

    def create(self, **kwargs: t.Any) -> dict[str, t.Any]:
        result = {"id": "zone-id"}
        result.update(kwargs)
        return {"result": result}

    def __call__(self, zone_id: str) -> "ZoneResource":
        return ZoneResource(self, zone_id)


class ZoneResource:
    def __init__(self, zones_resource: ZonesResource, zone_id: str) -> None:
        self.zones_resource = zones_resource
        self.zone_id = zone_id

    def dns_records(self) -> DnsRecordsResource:
        return self.zones_resource.dns_records


class CloudflareClient:
    def __init__(self) -> None:
        self.zones = ZonesResource()


MockedCloudflareClient = t.TypeVar("MockedCloudflareClient", bound=CloudflareClient)


@pytest.fixture
def mock_async_context_manager():  # type: ignore
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _async_context_manager(*args: t.Any, **kwargs: t.Any):  # type: ignore
        mock = MagicMock(*args, **kwargs)
        yield mock

    return _async_context_manager


@pytest.fixture
def cloudflare_dns(
    mock_async_context_manager: Callable[..., AsyncGenerator[MagicMock, None]],
) -> CloudflareDns:
    dns = CloudflareDns()
    dns.name = "test-domain"  # type: ignore  # Not defined in CloudflareDns
    dns.subdomain = "www"  # type: ignore  # Not defined in CloudflareDns
    dns.domain = "example.com"  # type: ignore  # Not defined in CloudflareDns
    dns.email = "test@example.com"  # type: ignore  # Not defined in CloudflareDns
    dns.key = "cloudflare-api-key"  # type: ignore  # Not defined in CloudflareDns
    dns.config = MagicMock()
    dns.logger = MagicMock()
    dns._client_cls = MagicMock()  # type: ignore  # Not defined in CloudflareDns
    dns.get_zone_id = AsyncMock()  # type: ignore  # Not defined in CloudflareDns
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
    async def test_get_zone_id(
        self,
        cloudflare_dns: CloudflareDns,
        mock_client: MagicMock,
        mock_async_context_manager: Callable[..., AsyncGenerator[MagicMock, None]],
    ) -> None:
        cloudflare_dns.client = mock_client
        mock_client.zones.get = MagicMock()
        mock_client.zones.get.return_value = mock_async_context_manager(
            MagicMock(
                json=MagicMock(
                    return_value={
                        "result": [
                            {
                                "id": "zone-id",
                                "name": "example.com",
                            }
                        ]
                    }
                )
            )
        )

        zone_id = await cloudflare_dns.get_zone_id()  # type: ignore

        assert zone_id == "zone-id"
        mock_client.zones.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_zone_id_not_found(
        self,
        cloudflare_dns: CloudflareDns,
        mock_client: MagicMock,
        mock_async_context_manager: Callable[..., AsyncGenerator[MagicMock, None]],
    ) -> None:
        cloudflare_dns.client = mock_client
        mock_client.zones.get = MagicMock()
        mock_client.zones.get.return_value = mock_async_context_manager(
            MagicMock(json=MagicMock(return_value={"result": []}))
        )

        with pytest.raises(ValueError):
            await cloudflare_dns.get_zone_id()  # type: ignore

        mock_client.zones.get.assert_called_once()

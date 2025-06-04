import typing as t

from pydantic import BaseModel
from acb.config import AdapterBase, Settings


class DnsRecord(BaseModel):
    name: str | None = None
    type: str = "TXT"
    ttl: int = 300
    rrdata: str | list[t.Any] | None = None


class DnsBaseSettings(Settings):
    zone_name: str | None = None
    ttl: int = 300


class DnsProtocol(t.Protocol):
    client: t.Any | None = None
    zone: t.Any | None = None

    def create_zone(self) -> None: ...

    def list_records(self) -> list[DnsRecord]: ...

    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None: ...


class DnsBase(AdapterBase): ...

import typing as t

from pydantic import BaseModel
from acb.config import AdapterBase, Settings


class DnsRecord(BaseModel):
    name: t.Optional[str] = None
    type: str = "TXT"
    ttl: int = 300
    rrdata: t.Optional[str | list[t.Any]] = None


class DnsBaseSettings(Settings): ...


class DnsBase(AdapterBase):
    client: t.Optional[t.Any] = None
    zone: t.Optional[t.Any] = None

    def create_zone(self) -> None: ...

    def list_records(self) -> list[DnsRecord]: ...

    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None: ...

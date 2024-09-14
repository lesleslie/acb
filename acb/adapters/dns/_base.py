import typing as t
from abc import ABC, abstractmethod

from pydantic import BaseModel
from acb.config import AdapterBase, Settings


class DnsRecord(BaseModel):
    name: t.Optional[str] = None
    type: str = "TXT"
    ttl: int = 300
    rrdata: t.Optional[str | list[t.Any]] = None


class DnsBaseSettings(Settings): ...


class DnsBase(AdapterBase, ABC):
    client: t.Optional[t.Any] = None
    zone: t.Optional[t.Any] = None

    @abstractmethod
    def create_zone(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_records(self) -> list[DnsRecord]:
        raise NotImplementedError

    @abstractmethod
    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None:
        raise NotImplementedError

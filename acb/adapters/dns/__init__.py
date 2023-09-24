import typing as t
from abc import ABC
from abc import abstractmethod

from acb.config import ac
from acb.config import Settings
from pydantic import BaseModel


class DnsRecord(BaseModel):
    name: t.Optional[str] = None
    type: str = "TXT"
    ttl: int = 300
    rrdata: t.Optional[str | list[t.Any]] = None

    def model_post_init(self, __context: t.Any) -> None:
        self.name = f"mail.{ac.app.domain}"


class DnsBaseSettings(Settings):
    ...


class DnsBase(ABC):
    client: t.Optional[t.Any] = None
    zone: t.Optional[t.Any] = None

    @abstractmethod
    async def init(self) -> None:
        ...

    @abstractmethod
    async def create_zone(self) -> None:
        ...

    @abstractmethod
    async def list_records(self):
        ...

    @abstractmethod
    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None:
        ...

import typing as t
from abc import ABC
from abc import abstractmethod

from acb.config import Config
from acb.config import Settings
from acb.depends import depends
from pydantic import BaseModel


class DnsRecord(BaseModel):
    name: t.Optional[str] = None
    type: str = "TXT"
    ttl: int = 300
    rrdata: t.Optional[str | list[t.Any]] = None

    @depends.inject
    def model_post_init(self, __context: t.Any, config: Config = depends()) -> None:
        self.name = f"mail.{self.config.app.domain}"


class DnsBaseSettings(Settings):
    ...


class DnsBase(ABC):
    config: Config = depends()
    client: t.Optional[t.Any] = None
    zone: t.Optional[t.Any] = None

    @abstractmethod
    async def init(self) -> t.NoReturn:
        raise NotImplementedError

    @abstractmethod
    async def create_zone(self) -> t.NoReturn:
        raise NotImplementedError

    @abstractmethod
    async def list_records(self) -> t.NoReturn:
        raise NotImplementedError

    @abstractmethod
    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> t.NoReturn:
        raise NotImplementedError

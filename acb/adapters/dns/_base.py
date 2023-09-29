import typing as t
from abc import ABC
from abc import abstractmethod

from acb.config import Config
from acb.config import Settings
from acb.depends import depends
from acb.adapters.dns import DnsRecord
from acb.adapters.logger import Logger


class DnsBaseSettings(Settings):
    ...


class DnsBase(ABC):
    config: Config = depends()
    logger: Logger = depends()  # type: ignore
    client: t.Optional[t.Any] = None
    zone: t.Optional[t.Any] = None

    @abstractmethod
    async def init(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_zone(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_records(self) -> list[DnsRecord]:
        raise NotImplementedError

    @abstractmethod
    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None:
        raise NotImplementedError

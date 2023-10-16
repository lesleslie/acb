from abc import ABC
from abc import abstractmethod
from acb import depends

from acb.config import Settings
from acb.config import Config


class FtpServerBaseSettings(Settings):
    port: int = 8021
    max_connections: int = 42


class FtpServerBase(ABC):
    config: Config = depends()  # type: ignore

    @abstractmethod
    async def init(self) -> None:
        raise NotImplementedError

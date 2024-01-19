from abc import ABC, abstractmethod
from acb.config import AppSettings as AppConfigSettings
from acb.config import Config
from acb.adapters.logger import Logger
from acb.depends import depends


class AppBaseSettings(AppConfigSettings):
    ...


class AppBase(ABC):
    config: Config = depends()
    logger: Logger = depends()  # type: ignore

    @abstractmethod
    async def init(self) -> None:
        raise NotImplementedError

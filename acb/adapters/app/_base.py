from abc import ABC, abstractmethod
from acb.config import AppSettings as AppConfigSettings


class AppBaseSettings(AppConfigSettings):
    ...


class AppBase(ABC):
    @abstractmethod
    async def init(self):
        ...

    # @abstractmethod
    # async def main(self):
    #     ...

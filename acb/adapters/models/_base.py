from abc import ABC
from abc import abstractmethod

from acb.config import Settings


class ModelsBaseSettings(Settings):
    ...


class ModelsBase(ABC):
    @abstractmethod
    async def init(self) -> None:
        raise NotImplementedError

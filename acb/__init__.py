from contextvars import ContextVar
from pathlib import Path


from aiopath import AsyncPath
from pydantic import BaseModel

base_path: AsyncPath = AsyncPath(Path.cwd())
tmp_path = base_path / "tmp"


class Action(BaseModel, arbitrary_types_allowed=True):
    name: str
    pkg: str = "acb"
    module: str = ""
    path: AsyncPath = AsyncPath(__file__) / "actions"


action_registry: ContextVar[list[Action]] = ContextVar("action_registry", default=[])


class Adapter(BaseModel, arbitrary_types_allowed=True):
    name: str
    category: str
    required: bool = False
    enabled: bool = False
    installed: bool = False
    pkg: str = "acb"
    module: str = ""
    path: AsyncPath = AsyncPath(Path(__file__) / "adapters")

    def __str__(self) -> str:
        return self.__repr__()


adapter_registry: ContextVar[list[Adapter]] = ContextVar("adapter_registry", default=[])

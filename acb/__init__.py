from contextvars import ContextVar
from pathlib import Path

from aiopath import AsyncPath
from pydantic import BaseModel

base_path: AsyncPath = AsyncPath(Path.cwd())
tmp_path = base_path / "tmp"


class Action(BaseModel, arbitrary_types_allowed=True):
    name: str
    path: AsyncPath = AsyncPath(Path.cwd())
    pkg: str = path.parent.stem


action_registry: ContextVar[list[Action]] = ContextVar("action_registry", default=[])


class Adapter(BaseModel, arbitrary_types_allowed=True):
    name: str
    category: str
    required: bool = False
    enabled: bool = False
    installed: bool = False
    path: AsyncPath = AsyncPath(Path.cwd())
    pkg: str = path.parent.stem


adapter_registry: ContextVar[list[Adapter]] = ContextVar("adapter_registry", default=[])

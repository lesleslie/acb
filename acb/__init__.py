import asyncio
import os
from contextvars import ContextVar
from inspect import currentframe

import nest_asyncio
from anyio import Path as AsyncPath
from pydantic import BaseModel
from acb.actions import Action, register_actions
from acb.adapters import Adapter, register_adapters

nest_asyncio.apply()

_deployed: bool = os.getenv("DEPLOYED", "False").lower() == "true"
_testing: bool = os.getenv("TESTING", "False").lower() == "true"


class Pkg(BaseModel, arbitrary_types_allowed=True):
    name: str
    path: AsyncPath
    actions: list[Action] = []
    adapters: list[Adapter] = []


pkg_registry: ContextVar[list[Pkg]] = ContextVar("pkg_registry", default=[])


def register_pkg() -> None:
    path = AsyncPath(currentframe().f_back.f_code.co_filename).parent
    name = path.stem
    registry = pkg_registry.get()
    if name not in [p.name for p in registry]:
        actions = asyncio.run(register_actions(path))
        adapters = asyncio.run(register_adapters(path))
        pkg = Pkg(name=name, path=path, actions=actions, adapters=adapters)
        registry.append(pkg)

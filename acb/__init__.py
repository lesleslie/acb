import os
from contextvars import ContextVar
from inspect import currentframe

from aiopath import AsyncPath
from pydantic import BaseModel
from acb.actions import Action, register_actions
from acb.adapters import Adapter, register_adapters

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
        actions = register_actions()
        adapters = register_adapters()
        pkg = Pkg(name=name, path=path, actions=actions, adapters=adapters)
        if pkg.name == "acb":
            registry.append(pkg)
        else:
            registry.insert(1, pkg)

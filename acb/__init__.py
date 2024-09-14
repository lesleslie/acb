from contextvars import ContextVar
from inspect import currentframe
from pathlib import Path

from pydantic import BaseModel
from acb.actions import Action, register_actions
from acb.adapters import Adapter, register_adapters


class Pkg(BaseModel):
    name: str
    actions: list[Action] = []
    adapters: list[Adapter] = []


pkg_registry: ContextVar[list[Pkg]] = ContextVar("pkg_registry", default=[])


def register_pkg() -> None:
    name = Path(currentframe().f_back.f_code.co_filename).parent.stem
    registry = pkg_registry.get()
    if name not in [p.name for p in registry]:
        actions = register_actions()
        adapters = register_adapters()
        pkg = Pkg(name=name, actions=actions, adapters=adapters)
        if pkg.name == "acb":
            registry.insert(0, pkg)
        else:
            registry.append(Pkg(name=name, actions=actions, adapters=adapters))

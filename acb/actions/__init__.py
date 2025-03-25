from contextvars import ContextVar
from importlib import import_module, util
from inspect import currentframe
from pathlib import Path
from typing import Protocol, runtime_checkable

from aiopath import AsyncPath
from pydantic import BaseModel


class ActionNotFound(Exception): ...


class Action(BaseModel):
    name: str
    pkg: str = "acb"
    module: str = ""
    methods: list[str] = []
    path: AsyncPath = AsyncPath(__file__) / "actions"

    class Config:
        arbitrary_types_allowed = True


action_registry: ContextVar[list[Action]] = ContextVar("action_registry", default=[])


@runtime_checkable
class ActionProtocol(Protocol):
    def __getattr__(self, item: str) -> Action: ...


class Actions:
    def __getattr__(self, item: str) -> Action:
        if item in self.__dict__:
            return self.__dict__[item]
        raise ActionNotFound(f"Action {item} not found")


actions = Actions()


def create_action(path: Path) -> Action:
    return Action(
        name=path.stem,
        module=".".join(path.parts[-3:]).removesuffix(".py"),
        pkg=path.parent.parent.parent.stem,
        path=AsyncPath(path),
    )


def register_actions() -> list[Action]:
    caller_file = currentframe().f_back.f_back.f_code.co_filename
    actions_path = Path(caller_file).parent / "actions"

    if not actions_path.exists():
        actions_path = Path(__file__).parent

    found_actions: dict[str, Path] = {
        a.stem: a
        for a in actions_path.iterdir()
        if a.is_dir() and not a.name.startswith("_")
    }

    registry = action_registry.get()
    _actions: list[Action] = []

    for action_name, path in found_actions.items():
        action_index = next(
            (i for i, a in enumerate(registry) if a.name == action_name), None
        )
        if action_index is not None:
            registry.pop(action_index)

        _action = create_action(path=AsyncPath(path))
        registry.append(_action)

        try:
            module = import_module(_action.module)
        except ModuleNotFoundError:
            spec = util.spec_from_file_location(_action.path.stem, _action.path)
            if spec and spec.loader:
                module = util.module_from_spec(spec)
                spec.loader.exec_module(module)
            else:
                continue

        if hasattr(module, "__all__"):
            _action.methods = module.__all__
            for attr in [a for a in dir(module) if a in module.__all__]:
                setattr(actions, attr, getattr(module, attr))

        _actions.append(_action)

    return _actions

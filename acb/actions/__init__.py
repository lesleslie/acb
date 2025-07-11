import typing as t
from contextvars import ContextVar
from importlib import import_module, util

from anyio import Path as AsyncPath
from pydantic import BaseModel, ConfigDict


class ActionNotFound(Exception): ...


class Action(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    pkg: str = "acb"
    module: str = ""
    methods: list[str] = []
    path: AsyncPath = AsyncPath(__file__) / "actions"


action_registry: ContextVar[list[Action]] = ContextVar("action_registry", default=[])


@t.runtime_checkable
class ActionProtocol(t.Protocol):
    def __getattr__(self, item: str) -> Action: ...


class Actions:
    def __getattr__(self, item: str) -> Action:
        if item in self.__dict__:
            return self.__dict__[item]
        msg = f"Action {item} not found"
        raise ActionNotFound(msg)


actions = Actions()


def create_action(path: AsyncPath) -> Action:
    return Action(
        name=path.stem,
        module=".".join(path.parts[-3:]).removesuffix(".py"),
        pkg=path.parent.parent.parent.stem,
        path=path,
    )


async def register_actions(path: AsyncPath) -> list[Action]:
    actions_path = path / "actions"
    if not await actions_path.exists():
        return []
    found_actions: dict[str, AsyncPath] = {
        a.stem: a
        async for a in actions_path.iterdir()
        if await a.is_dir() and (not a.name.startswith("_"))
    }
    registry = action_registry.get()
    _actions: list[Action] = []
    for action_name, path in found_actions.items():
        action_index = next(
            (i for i, a in enumerate(registry) if a.name == action_name),
            None,
        )
        if action_index is not None:
            registry.pop(action_index)
        _action = create_action(path=path)
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

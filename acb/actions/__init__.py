from contextvars import ContextVar
from pathlib import Path

from aiopath import AsyncPath
from pydantic import BaseModel

root_path: AsyncPath = AsyncPath(Path.cwd())


class Action(BaseModel, arbitrary_types_allowed=True):
    name: str
    pkg: str = "acb"
    module: str = ""
    path: AsyncPath = AsyncPath(__file__) / "actions"


action_registry: ContextVar[list[Action]] = ContextVar("action_registry", default=[])


class AdapterNotFound(Exception):
    pass


def register_actions() -> list[Action]:
    actions_path = Path(root_path / "actions")
    if not actions_path.exists():
        actions_path = Path(__file__).parent
    actions = {
        a.stem: a
        for a in actions_path.iterdir()
        if a.is_file() and not a.name.startswith("_")
    }
    _actions = []
    for action_name, path in actions.items():
        action = next((a for a in action_registry.get() if a.name == action_name), None)
        if action:
            del action
        _action = Action(name=action_name, path=AsyncPath(path))
        action_registry.get().append(_action)
        _actions.append(_action)
    return _actions

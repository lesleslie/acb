from pathlib import Path

from acb import Action
from acb import action_registry
from acb import base_path
from aiopath import AsyncPath


def register_actions() -> None:
    _actions_path = Path(base_path / "actions")
    if not _actions_path.exists():
        _actions_path = Path(__file__).parent
    _pkg = _actions_path.parent.name
    _actions = {
        a.stem: a
        for a in _actions_path.iterdir()
        if a.is_file() and not a.name.startswith("_")
    }
    _pkg_path = _actions_path.parent
    for action_name, path in _actions.items():
        _action = next(
            (a for a in action_registry.get() if a.name == action_name), None
        )
        if _action:
            del _action
        action_registry.get().append(Action(name=action_name, path=AsyncPath(path)))


register_actions()

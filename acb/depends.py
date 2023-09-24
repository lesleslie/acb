from bevy import dependency as depends
from bevy import inject as inject_depends
from bevy import get_repository
import typing as t


__all__: list[str] = [
    "depends",
    "inject_depends",
    "get_repo",
]


def get_repo() -> t.Any:
    return get_repository()

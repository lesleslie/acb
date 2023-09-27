import typing as t

from bevy import dependency
from bevy import get_repository
from bevy import inject as inject_dependency


class Depends:
    @staticmethod
    def inject(func):
        return inject_dependency(func)

    @staticmethod
    def set(cls: t.TypeVar, value: t.Any) -> t.Any:
        return get_repository().set(cls, value)

    @staticmethod
    def get(cls: t.TypeVar) -> t.Any:
        return get_repository().get(cls)

    def __call__(self, *args, **kwargs):
        return dependency()


depends = Depends()

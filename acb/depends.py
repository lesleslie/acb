import typing as t

from bevy import dependency
from bevy import get_repository
from bevy import inject as inject_dependency


class Depends:
    @staticmethod
    def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        return inject_dependency(func)

    @staticmethod
    def set(class_: t.Any) -> t.Any:
        return get_repository().set(class_, class_())

    @staticmethod
    def get(class_: t.Any) -> t.Any:
        return get_repository().get(class_)

    def __call__(self, *args: t.Any, **kwargs: t.Any):
        return dependency()


depends = Depends()

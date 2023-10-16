import typing as t
from inspect import currentframe
from pathlib import Path

from bevy import dependency
from bevy import get_repository
from bevy import inject as inject_dependency


get_module_name = Path(currentframe().f_back.f_back.f_back.f_code.co_filename).parent


class Depends:
    @staticmethod
    def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        return inject_dependency(func)

    @staticmethod
    def set(class_: t.Any, value: t.Any = None) -> t.Any:
        return get_repository().set(
            t.Annotated[class_, get_module_name], value or class_()
        )

    @staticmethod
    def get(class_: t.Any) -> t.Any:
        return get_repository().get(class_)

    def __call__(self, *args: t.Any, **kwargs: t.Any):
        return dependency()


depends = Depends()

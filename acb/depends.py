import asyncio
import typing as t
from contextlib import suppress
from inspect import stack

from bevy import dependency, get_repository
from bevy import inject as inject_dependency


@t.runtime_checkable
class DependsProtocol(t.Protocol):
    @staticmethod
    def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]: ...
    @staticmethod
    def set(class_: t.Any, instance: t.Any = None) -> t.Any: ...
    @staticmethod
    def get(*args: t.Any) -> t.Any: ...
    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any: ...


class Depends:
    @staticmethod
    def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        return inject_dependency(func)

    @staticmethod
    def set(class_: t.Any, instance: t.Any = None) -> t.Any:
        if instance is None:
            return get_repository().set(class_, class_())
        return get_repository().set(class_, instance)

    @staticmethod
    def get(category: t.Any = None) -> t.Any:
        if not category:
            with suppress(AttributeError, IndexError):
                context = stack()[1][4]
                if context:
                    category = next(
                        c.strip()
                        for c in context[0].split("=")[0].strip().lower().split(",")
                    ).removeprefix("self.")
        class_ = category
        if isinstance(class_, str):
            with suppress(Exception):
                result = get_repository().get(class_)
                if result is not None:
                    return result
            from .adapters import _import_adapter

            try:
                asyncio.get_running_loop()
                import nest_asyncio

                if nest_asyncio:
                    nest_asyncio.apply()
                class_ = asyncio.run(_import_adapter(class_))
            except RuntimeError:
                class_ = asyncio.run(_import_adapter(class_))
        return get_repository().get(class_)

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return dependency()


depends = Depends()

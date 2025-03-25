from typing import Any, Callable, Protocol, cast, runtime_checkable

from bevy import dependency, get_repository
from bevy import inject as inject_dependency


@runtime_checkable
class DependsProtocol(Protocol):
    @staticmethod
    def inject(func: Callable[..., Any]) -> Callable[..., Any]: ...

    @staticmethod
    def set(class_: Any) -> Any: ...

    @staticmethod
    def get(class_: Any) -> Any: ...

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


class Depends:
    @staticmethod
    def inject(func: Callable[..., Any]) -> Callable[..., Any]:
        return inject_dependency(func)

    @staticmethod
    def set(class_: Any) -> Any:
        return get_repository().set(class_, class_())

    @staticmethod
    def get(class_: Any) -> Any:
        if isinstance(class_, str):
            from acb.adapters import import_adapter

            class_ = import_adapter(class_)
        return cast(class_, get_repository().get(class_))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return dependency()


depends = Depends()

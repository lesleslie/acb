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
            if callable(class_) and not isinstance(class_, type):
                return get_repository().set(class_, class_())
            else:
                return get_repository().set(class_, class_())
        else:
            return get_repository().set(class_, instance)

    @staticmethod
    def get(*args: t.Any) -> t.Any:
        classes: t.List[t.Any] = []

        if not args or args[0] is None:
            _classes: t.List[str] = []
            with suppress(AttributeError, IndexError):
                _classes = [
                    c.strip()
                    for c in (
                        stack()[1][4][0].split("=")[0].strip().lower()  # type: ignore
                    ).split(",")
                ]
                _classes = [c.removeprefix("self.") for c in _classes]

            from acb.adapters import import_adapter

            config = False
            index = 0
            if "config" in _classes:
                index = _classes.index("config")
                del _classes[index]
                config = True
            if _classes:
                _classes = import_adapter(_classes)  # type: ignore
                classes = [_classes]
            if config:
                from acb.config import Config

                classes.insert(index, Config)  # type: ignore

        elif args and all(isinstance(arg, str) for arg in args):
            from acb.adapters import import_adapter

            _classes = import_adapter(list(args))  # type: ignore
            classes = [_classes]

        else:
            classes = [args[0]]

        classes = [t.cast(t.Any, get_repository().get(c)) for c in classes]
        return classes[0] if len(classes) < 2 else classes

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return dependency()


depends = Depends()

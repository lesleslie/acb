import typing as t
from inspect import stack

from bevy import dependency, get_repository
from bevy import inject as inject_dependency


@t.runtime_checkable
class DependsProtocol(t.Protocol):
    @staticmethod
    def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]: ...

    @staticmethod
    def set(class_: t.Any) -> t.Any: ...

    @staticmethod
    def get(class_: t.Any) -> t.Any: ...

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any: ...


class Depends:
    @staticmethod
    def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        return inject_dependency(func)

    @staticmethod
    def set(class_: t.Any) -> t.Any:
        return get_repository().set(class_, class_())

    @staticmethod
    def get(class_: t.Any = None) -> t.Any:
        classes = []
        if not class_ or isinstance(class_, str):
            _classes = []
            if not class_:
                _classes = [
                    c.strip()
                    for c in (
                        stack()[1][4][0].split("=")[0].strip().lower()  # type: ignore
                    ).split(",")
                ]
                _classes = [c.removeprefix("self.") for c in _classes]
            elif isinstance(class_, str):
                _classes = [class_]
            from acb.adapters import import_adapter

            config = False
            index = 0
            if "config" in _classes:
                index = _classes.index("config")
                del _classes[index]
                config = True
            if _classes:
                _classes = import_adapter(_classes)
                classes = [_classes] if not isinstance(_classes, list) else _classes
            if config:
                from acb.config import Config

                classes.insert(index, Config)  # type: ignore
        else:
            classes = [class_]
        classes = [t.cast(c, get_repository().get(c)) for c in classes]
        return classes[0] if len(classes) < 2 else classes

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return dependency()


depends = Depends()

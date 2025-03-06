import typing as t

from acb.config import Settings


class LoggerBaseSettings(Settings):
    verbose: bool = False
    deployed_level: str = "WARNING"
    log_level: t.Optional[str] = "INFO"


class LoggerBase:
    def debug(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    async def init(self) -> None: ...

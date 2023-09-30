import logging
from contextvars import ContextVar

from acb.config import enabled_adapters
from acb.config import import_adapter
from acb.depends import depends

__all__: list[str] = [
    "register_loggers",
    "logger_registry",
    "Logger",
    "LoggerSettings",
]

Logger, LoggerSettings = import_adapter()

logger_registry: ContextVar[set[str]] = ContextVar("registered_loggers", default=set())


class InterceptHandler(logging.Handler):
    def __init__(self, logger_name: str) -> None:
        super().__init__()
        self.logger_name = logger_name

    @depends.inject
    def emit(
        self, record: logging.LogRecord, logger: Logger = depends()  # type: ignore
    ) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
            enabled_logger = enabled_adapters.get()["logger"]
            if enabled_logger == "loguru":
                logger.patch(
                    lambda record: record.update(name=self.logger_name)  # type: ignore
                ).opt(
                    depth=depth,
                    exception=record.exc_info,
                ).log(
                    level, record.getMessage()
                )
            # elif enabled_logger == "structlog":
            #     ...


def register_loggers(loggers: list[str]) -> None:
    for logger in loggers:
        _logger = logging.getLogger(logger)
        _logger.handlers.clear()
        _logger.handlers = [InterceptHandler(_logger.name)]
    return logger_registry.get().update(loggers)

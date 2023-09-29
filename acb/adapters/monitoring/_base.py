import typing as t
from time import perf_counter

from acb.adapters.logger import Logger
from acb.config import Settings
from acb.depends import depends


class MonitoringBaseSettings(Settings):
    ...


class MonitoringBase:
    ...


@depends.inject
def timeit(func: t.Any, logger: Logger = depends()) -> t.Any:  # type: ignore
    def wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        logger.debug(f"Function '{func.__name__}' executed in {end - start} s")
        return result

    return wrapped

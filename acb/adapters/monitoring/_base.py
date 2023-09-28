from acb.config import Settings
from time import perf_counter
from acb.config import logger
import typing as t


class MonitoringBaseSettings(Settings):
    ...


class MonitoringBase:
    ...


def timeit(func: t.Any) -> t.Any:
    def wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        logger.debug(f"Function '{func.__name__}' executed in {end - start} s")
        return result

    return wrapped

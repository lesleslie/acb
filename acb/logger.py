import logging
import sys
from time import perf_counter

# from acb.config import ac
from loguru import logger


# def get_mod():
#     # frame = stack()[3][0]
#     # frame = logging.currentframe()
#     mod_logger = stack()[3][0]
#     mod = getmodule(mod_logger)
#     mod = Path(mod.__file__).parent
#     if mod.stem == ac.basedir.stem:
#         mod = Path(mod.__file__)
#     return mod
#
#
# def log_debug(s):
#     mod = get_mod()
#     debug_mod = dict(ac.debug.model_fields).get(mod.stem)
#     if debug_mod:
#         if ac.deployed:
#             return (
#             logger.patch(lambda record: record.update(
#             name=mod.__name__)).debug(s)
#             )
#         return colorizedStderrPrint(s)
#
#
# ic.configureOutput(prefix="    debug:  ", includeContext=True,
# outputFunction=log_debug)
# if ac.deployed:
#     ic.configureOutput(prefix="", includeContext=False, outputFunction=log_debug)


# async def apformat(obj, sort_dicts: bool = False) -> None:  # make purple
#     mod = get_mod()
#     debug_mod = dict(ac.debug.model_fields).get(mod.stem)
#     if not ac.deployed and not ac.debug.production and debug_mod:
#         await aprint(pformat(obj, sort_dicts=sort_dicts))


def timeit(func):
    def wrapped(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        logger.debug(f"Function '{func.__name__}' executed in {end - start} s")
        return result

    return wrapped


class InterceptHandler(logging.Handler):
    def __init__(self, logger_name: str) -> None:
        self.logger_name = logger_name
        super().__init__()

    def emit(self, record) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.patch(lambda record: record.update(name=self.logger_name)).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())


logger_format = dict(
    time="<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
    level=" <level>{level:>8}</level>",
    sep=" <b><w>in</w></b> ",
    name="{name:>20}",
    line="<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
    message="  <level>{message}</level>",
)
# level_per_module = {
#     m: "DEBUG" if v is True else "INFO" for (m, v) in ac.debug.model_dump().items()
# }

log_format = "".join(logger_format.values())
configs = dict(
    # filter=level_per_module,
    format=log_format,
    enqueue=True,
    backtrace=True,
)
logger.remove()
# logging.getLogger("uvicorn").handlers.clear()
logger.add(sys.stderr, **configs)
logger.level("DEBUG", color="<cyan>")
_loggers = []
# _loggers = ["uvicorn.access", "uvicorn.error"]
# if ac.debug.sql:
#     _loggers.extend(
#         [
#             "sqlalchemy.engine",
#             "sqlalchemy.orm",
#             "sqlalchemy.pool",
#             "sqlalchemy.dialects",
#         ]
#     )
# if ac.debug.cache:
#     _loggers.extend(["httpx_caching"])
for _log in _loggers:
    _logger = logging.getLogger(_log)
    _logger.handlers.clear()
    _logger.handlers = [InterceptHandler(_logger.name)]

# if ac.debug.logger:
#     logger.debug("debug")
#     logger.info("info")
#     logger.warning("warning")
#     logger.error("error")
#     logger.critical("critical")
#     pprint(level_per_module)

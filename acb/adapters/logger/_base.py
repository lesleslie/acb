import typing as t

from acb.config import Config
from acb.config import Settings
from acb.depends import depends



class LoggerBaseSettings(Settings):
    loggers: dict[str, list[str]] = {}

    @depends.inject
    def model_post_init(self, __context: t.Any, config: Config = depends()) -> None:
        for adapter in config.enabled_adapters:
            self.loggers.update({adapter: getattr(config, adapter).loggers})
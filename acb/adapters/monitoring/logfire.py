from logfire import (
    configure,
    instrument_httpx,
    instrument_pydantic,
    instrument_redis,
    instrument_sqlalchemy,
    instrument_system_metrics,
    loguru_handler,
)
from pydantic import SecretStr
from acb.adapters import get_installed_adapters
from acb.depends import depends

from ._base import MonitoringBase, MonitoringBaseSettings


class MonitoringSettings(MonitoringBaseSettings):
    logfire_token: SecretStr = SecretStr("secret")


class Monitoring(MonitoringBase):
    async def init(self) -> None:
        configure(
            token=self.config.monitoring.logfire_token.get_secret_value(),
            service_name=self.config.app.name,
            service_version=self.config.app.version,
        )
        instrument_pydantic(record="all")
        for adapter in [a.name for a in get_installed_adapters()]:
            match adapter:
                case "loguru":
                    from loguru import logger

                    logger.configure(handlers=[loguru_handler()])
                case "httpx":
                    instrument_httpx()
                case "redis":
                    instrument_redis()
                case "sqlalchemy":
                    sql = depends.get()
                    instrument_sqlalchemy(engine=sql.engine)
                case _:
                    pass
        instrument_system_metrics()


depends.set(Monitoring)

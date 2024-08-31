import typing as t

from logfire import (
    PydanticPlugin,
    configure,
    instrument_httpx,
    instrument_redis,
    instrument_sqlalchemy,
    instrument_system_metrics,
    loguru_handler,
)
from pydantic import SecretStr
from acb.adapters import get_installed_adapters, import_adapter
from acb.depends import depends
from ._base import MonitoringBase, MonitoringBaseSettings


class MonitoringSettings(MonitoringBaseSettings):
    project_name: t.Optional[str] = None
    logfire_token: t.Optional[SecretStr] = None


class Monitoring(MonitoringBase):
    @depends.inject
    async def init(self) -> None:
        configure(
            token=self.config.monitoring.logfire_token.get_secret_value(),
            project_name=self.config.monitoring.project_name or self.config.app.project,
            service_name=self.config.app.name,
            service_version=self.config.app.version,
            trace_sample_rate=self.config.monitoring.traces_sample_rate,
            pydantic_plugin=PydanticPlugin(record="all"),
        )
        for adapter in [a.name for a in get_installed_adapters()]:
            match adapter:
                case "loguru":
                    self.logger.configure(handlers=[loguru_handler()])
                case "httpx":
                    instrument_httpx()
                case "redis":
                    instrument_redis()
                case "sqlalchemy":
                    sql = depends.get(import_adapter("sql"))
                    instrument_sqlalchemy(engine=sql.engine)
                case _:
                    pass
        instrument_system_metrics()


depends.set(Monitoring)

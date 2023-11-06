from functools import cached_property

from acb.adapters.logger import Logger
from acb.depends import depends
from aioftp import AsyncPathIO
from aioftp import Server
from ._base import FtpdBase
from ._base import FtpdBaseSettings


class FtpdSettings(FtpdBaseSettings):
    ...


class Ftpd(FtpdBase):
    @cached_property
    def server(self) -> Server:
        return Server(
            path_io_factory=AsyncPathIO(),  # type: ignore
            maximum_connections=self.config.ftp.max_connections,
        )

    @depends.inject
    async def init(self, logger: Logger = depends()) -> None:  # type: ignore
        try:
            await self.server.start()
            logger.info(f"FTP server started on port {self.config.ftpd.port}")
        except Exception as exc:
            await self.server.close()
            raise SystemExit(f"\nError starting ftp server: {exc}\n")


depends.set(Ftpd)

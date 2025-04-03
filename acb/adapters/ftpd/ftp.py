from functools import cached_property

from aioftp import AsyncPathIO, Server
from acb.depends import depends
from acb.logger import Logger

from ._base import FtpdBase, FtpdBaseSettings


class FtpdSettings(FtpdBaseSettings): ...


class Ftpd(FtpdBase):
    @cached_property
    def server(self) -> Server:
        return Server(
            path_io_factory=AsyncPathIO(),  # type: ignore
            maximum_connections=self.config.ftp.max_connections,
        )

    @depends.inject
    async def init(self, logger: Logger = depends()) -> None:
        try:
            await self.server.start()
            logger.info(f"FTP server started on port {self.config.ftpd.port}")
        except Exception as exc:
            await self.server.close()
            raise SystemExit(f"\nError starting ftp server: {exc}\n")


depends.set(Ftpd)

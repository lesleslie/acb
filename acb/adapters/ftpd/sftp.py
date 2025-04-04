from asyncssh import Error, SFTPServer, listen
from pydantic import SecretStr
from acb.depends import depends
from acb.logger import Logger

from ._base import FtpdBase, FtpdBaseSettings


class FtpdSettings(FtpdBaseSettings):
    port: int = 8022
    server_host_keys: SecretStr
    authorized_client_keys: SecretStr


class Ftpd(FtpdBase):
    @depends.inject
    async def init(self, logger: Logger = depends()) -> None:
        try:
            await listen(
                "",
                self,
                server_host_keys=[
                    self.config.ftp_server.server_host_keys.get_secret_value()
                ],
                authorized_client_keys=(
                    self.config.ftp_server.authorized_client_keys.get_secret_value()
                ),
                sftp_factory=SFTPServer,
            )
            logger.info(f"FTP server started on port {self.config.ftpd.port}")
        except (OSError, Error) as exc:
            raise SystemExit(f"\nError starting sftp server: {exc}\n")


depends.set(Ftpd)

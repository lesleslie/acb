from asyncssh import Error
from asyncssh import listen
from asyncssh import SFTPServer
from pydantic import SecretStr
from ._base import FtpdBase
from ._base import FtpdBaseSettings
from acb.depends import depends
from acb.adapters import import_adapter

Logger = import_adapter()


class FtpdSettings(FtpdBaseSettings):
    port: int = 8022
    server_host_keys: SecretStr
    authorized_client_keys: SecretStr


class Ftpd(FtpdBase):
    @depends.inject
    async def init(self, logger: Logger = depends()) -> None:  # type: ignore
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
            # close server?
            raise SystemExit(f"\nError starting sftp server: {exc}\n")


depends.set(Ftpd)

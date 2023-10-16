from asyncssh import Error
from asyncssh import listen
from asyncssh import SFTPServer
from pydantic import SecretStr
from ._base import FtpServerBase
from ._base import FtpServerBaseSettings


class FtpServerSettings(FtpServerBaseSettings):
    port: int = 8022
    server_host_keys: SecretStr
    authorized_client_keys: SecretStr


class FtpServer(FtpServerBase):
    async def init(self) -> None:
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
        except (OSError, Error) as exc:
            # close server?
            raise SystemExit(f"\nError starting sftp server: {str(exc)}\n")

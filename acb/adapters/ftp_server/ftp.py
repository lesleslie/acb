from functools import cached_property

from aioftp import AsyncPathIO
from aioftp import Server
from ._base import FtpServerBase
from ._base import FtpServerBaseSettings


class FtpServerSettings(FtpServerBaseSettings):
    ...


# class AsyncPathIO(AbstractPathIO):
#     def __init__(self, *args, executor=None, **kwargs) -> None:
#         super().__init__(*args, **kwargs)
#         self.executor = executor
#
#     async def exists(self, path: AsyncPath) -> bool:
#         return await path.exists()
#
#     async def is_dir(self, path: AsyncPath):
#         return path.is_dir()
#
#     async def is_file(self, path: AsyncPath):
#         return path.is_file()
#
#     async def mkdir(self, path: AsyncPath, *, parents=False, exist_ok=False):
#         return path.mkdir(parents=parents, exist_ok=exist_ok)
#
#     async def rmdir(self, path: AsyncPath) -> t.Coroutine[t.Any, t.Any, None]:
#         return await path.rmdir()
#
#     async def unlink(self, path: AsyncPath) -> t.Coroutine[t.Any, t.Any, None]:
#         return await path.unlink()
#
#     @staticmethod
#     @override
#     async def list(path: AsyncPath) -> t.Any:
#         return path.rglob("*")
#
#     async def stat(self, path: AsyncPath) -> t.Any:
#         return await path.stat()
#
#     @asynccontextmanager
#     async def _open(self, path: AsyncPath, *args, **kwargs):
#         return path.open(*args, **kwargs)
#
#     async def seek(self, file: BytesIO, *args, **kwargs):
#         return file.seek(*args, **kwargs)
#
#     async def write(self, file: BytesIO, *args, **kwargs):
#         return file.write(*args, **kwargs)
#
#     async def read(self, file: BytesIO, *args, **kwargs):
#         return file.read(*args, **kwargs)
#
#     async def close(self, file: BytesIO):
#         return file.close()
#
#     async def rename(self, source, destination):
#         return source.rename(destination)


class FtpServer(FtpServerBase):
    @cached_property
    def server(self) -> Server:
        return Server(
            path_io_factory=AsyncPathIO(),
            maximum_connections=self.config.ftp.max_connections,
        )

    async def init(self) -> None:
        try:
            await self.server.start()
        except Exception as exc:
            await self.server.close()
            raise SystemExit(f"\nError starting ftp server: {str(exc)}\n")

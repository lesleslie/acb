from abc import abstractmethod
from pathlib import Path

import typing as t
from contextlib import asynccontextmanager
from pydantic import Field, SecretStr

from acb.config import AdapterBase, Settings


class FileInfo:
    def __init__(
        self,
        name: str,
        size: int = 0,
        is_dir: bool = False,
        is_file: bool | None = None,
        is_symlink: bool = False,
        permissions: str = "",
        mtime: float = 0.0,
        owner: str = "",
        group: str = "",
    ) -> None:
        self.name = name
        self.size = size
        self.is_dir = is_dir
        self.is_file = is_file if is_file is not None else not is_dir
        self.is_symlink = is_symlink
        self.permissions = permissions
        self.mtime = mtime
        self.owner = owner
        self.group = group


class FtpdBaseSettings(Settings):
    host: str = "127.0.0.1"
    port: int = 8021
    max_connections: int = 42
    username: str = "ftpuser"
    password: SecretStr = Field(default=SecretStr("ftppass"))
    anonymous: bool = False
    root_dir: str = "tmp/ftp"
    use_tls: bool = False
    cert_file: str | None = None
    key_file: str | None = None


class FtpdProtocol(t.Protocol):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def upload(self, local_path: Path, remote_path: str) -> None:
        pass

    @abstractmethod
    async def download(self, remote_path: str, local_path: Path) -> None:
        pass

    @abstractmethod
    async def list_dir(self, path: str) -> list[FileInfo]:
        pass

    @abstractmethod
    async def mkdir(self, path: str) -> None:
        pass

    @abstractmethod
    async def rmdir(self, path: str, recursive: bool = False) -> None:
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        pass

    @abstractmethod
    async def rename(self, old_path: str, new_path: str) -> None:
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        pass

    @abstractmethod
    async def stat(self, path: str) -> FileInfo:
        pass

    @abstractmethod
    async def read_text(self, path: str) -> str:
        pass

    @abstractmethod
    async def read_bytes(self, path: str) -> bytes:
        pass

    @abstractmethod
    async def write_text(self, path: str, content: str) -> None:
        pass

    @abstractmethod
    async def write_bytes(self, path: str, content: bytes) -> None:
        pass

    @abstractmethod
    @asynccontextmanager
    async def connect(self) -> t.AsyncGenerator["FtpdProtocol"]:
        yield self


class FtpdBase(AdapterBase):
    async def init(self) -> None:
        await self.start()

    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def upload(self, local_path: Path, remote_path: str) -> None:
        pass

    @abstractmethod
    async def download(self, remote_path: str, local_path: Path) -> None:
        pass

    @abstractmethod
    async def list_dir(self, path: str) -> list[FileInfo]:
        pass

    @abstractmethod
    async def mkdir(self, path: str) -> None:
        pass

    @abstractmethod
    async def rmdir(self, path: str, recursive: bool = False) -> None:
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        pass

    @abstractmethod
    async def rename(self, old_path: str, new_path: str) -> None:
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        pass

    @abstractmethod
    async def stat(self, path: str) -> FileInfo:
        pass

    @abstractmethod
    async def read_text(self, path: str) -> str:
        pass

    @abstractmethod
    async def read_bytes(self, path: str) -> bytes:
        pass

    @abstractmethod
    async def write_text(self, path: str, content: str) -> None:
        pass

    @abstractmethod
    async def write_bytes(self, path: str, content: bytes) -> None:
        pass

    @abstractmethod
    @asynccontextmanager
    async def connect(self) -> t.AsyncGenerator["FtpdBase"]:
        yield self

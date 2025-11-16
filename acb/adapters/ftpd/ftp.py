import os
import tempfile
from functools import cached_property
from pathlib import Path
from uuid import UUID

import typing as t
from contextlib import asynccontextmanager

try:
    from aioftp import AsyncPathIO, Client, Permission, Server, User
except Exception:  # pragma: no cover - allow tests without aioftp installed
    import os as _os
    import sys as _sys

    if "pytest" in _sys.modules or _os.getenv("TESTING", "False").lower() == "true":
        from unittest.mock import MagicMock

        AsyncPathIO = MagicMock  # type: ignore[assignment, no-redef]
        Client = MagicMock  # type: ignore[assignment, no-redef]
        Permission = MagicMock  # type: ignore[assignment, no-redef]
        Server = MagicMock  # type: ignore[assignment, no-redef]
        User = MagicMock  # type: ignore[assignment, no-redef]
    else:
        raise
from anyio import Path as AsyncPath

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import Inject, depends

from ._base import FileInfo, FtpdBase, FtpdBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b7f5f8443c6c")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="FTP Server",
    category="ftpd",
    provider="aioftp",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-20",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
    ],
    required_packages=["aioftp", "anyio"],
    description="FTP server and client adapter with async support",
    settings_class="FtpdSettings",
    config_example={
        "host": "127.0.0.1",
        "port": 8021,
        "username": "ftpuser",
        "password": "ftppass",  # pragma: allowlist secret
        "root_dir": "/tmp/ftp",  # nosec B108
        "anonymous": False,
        "passive_ports_min": 50000,
        "passive_ports_max": 50100,
    },
)


class FtpdSettings(FtpdBaseSettings):
    port: int = 8021
    passive_ports_min: int = 50000
    passive_ports_max: int = 50100
    timeout: int = 30


class Ftpd(FtpdBase):
    _client: Client | None = None  # type: ignore[assignment]
    _path_io: AsyncPathIO | None = None

    @cached_property
    def server(self) -> Server:
        Path(self.config.ftpd.root_dir).mkdir(parents=True, exist_ok=True)
        user = User(
            login=self.config.ftpd.username,
            password=self.config.ftpd.password.get_secret_value(),
            base_path=self.config.ftpd.root_dir,
            permissions=[Permission()],
        )
        users = [user]
        if self.config.ftpd.anonymous:
            anonymous_user = User(
                login="anonymous",
                password="",  # nosec B106
                base_path=self.config.ftpd.root_dir,
                permissions=[Permission(writable=False)],
            )
            users.append(anonymous_user)
        server_kwargs: dict[str, t.Any] = {
            "users": users,
            "path_io_factory": AsyncPathIO,
            "maximum_connections": self.config.ftpd.max_connections,
        }
        if hasattr(self.config.ftpd, "host"):
            server_kwargs["host"] = self.config.ftpd.host
        if hasattr(self.config.ftpd, "port"):
            server_kwargs["port"] = self.config.ftpd.port
        if hasattr(self.config.ftpd, "host"):
            server_kwargs["passive_host"] = self.config.ftpd.host
        if hasattr(self.config.ftpd, "passive_ports_min") and hasattr(
            self.config.ftpd,
            "passive_ports_max",
        ):
            server_kwargs["passive_ports"] = range(
                self.config.ftpd.passive_ports_min,
                self.config.ftpd.passive_ports_max,
            )
        if hasattr(self.config.ftpd, "timeout"):
            server_kwargs["timeout"] = self.config.ftpd.timeout
        return Server(**server_kwargs)

    @depends.inject
    async def start(self, logger: Inject[t.Any]) -> None:
        try:
            await self.server.start()
            logger.info(  # type: ignore[no-untyped-call]
                f"FTP server started on {self.config.ftpd.host}:{self.config.ftpd.port}",
            )
        except Exception as exc:
            await self.server.close()
            logger.exception(f"Error starting FTP server: {exc}")  # type: ignore[no-untyped-call]
            raise

    @depends.inject
    async def stop(self, logger: Inject[t.Any]) -> None:
        try:
            await self.server.close()
            logger.info("FTP server stopped")  # type: ignore[no-untyped-call]
        except Exception as exc:
            logger.exception(f"Error stopping FTP server: {exc}")  # type: ignore[no-untyped-call]
            raise

    async def _ensure_client(self) -> Client:
        if self._client is None:
            self._client = Client()
            await self._client.connect(self.config.ftpd.host, self.config.ftpd.port)
            await self._client.login(
                self.config.ftpd.username,
                self.config.ftpd.password.get_secret_value(),
            )
        return self._client

    async def _ensure_path_io(self) -> AsyncPathIO:
        if self._path_io is None:
            self._path_io = AsyncPathIO()
        return self._path_io

    @asynccontextmanager
    async def connect(self) -> t.AsyncGenerator["Ftpd"]:
        client = await self._ensure_client()
        try:
            yield self
        finally:
            await client.quit()
            self._client = None

    async def upload(self, local_path: Path, remote_path: str) -> None:
        client = await self._ensure_client()
        await client.upload(str(local_path), remote_path)

    async def download(self, remote_path: str, local_path: Path) -> None:
        client = await self._ensure_client()
        await client.download(remote_path, str(local_path))

    async def list_dir(self, path: str) -> list[FileInfo]:
        client = await self._ensure_client()
        result = []
        async for file_info in client.list(path):
            info = FileInfo(
                name=t.cast("str", file_info[1].get("name")),
                size=t.cast("int", file_info[1].get("size", 0)),
                is_dir=file_info[1].get("type") == "dir",
                is_file=file_info[1].get("type") == "file",
                permissions=t.cast("str", file_info[1].get("permissions", "")),
                mtime=t.cast("float", file_info[1].get("modify", 0.0)),
                owner=t.cast("str", file_info[1].get("owner", "")),
                group=t.cast("str", file_info[1].get("group", "")),
            )
            result.append(info)
        return result

    async def mkdir(self, path: str) -> None:
        client = await self._ensure_client()
        await client.make_directory(path)

    async def rmdir(self, path: str, recursive: bool = False) -> None:
        client = await self._ensure_client()
        if recursive:
            files = await self.list_dir(path)
            for file in files:
                full_path = f"{path}/{file.name}"
                if file.is_dir:
                    await self.rmdir(full_path, recursive=True)
                else:
                    await self.delete(full_path)
        await client.remove_directory(path)

    async def delete(self, path: str) -> None:
        client = await self._ensure_client()
        await client.remove_file(path)

    async def rename(self, old_path: str, new_path: str) -> None:
        client = await self._ensure_client()
        await client.rename(old_path, new_path)

    async def exists(self, path: str) -> bool:
        try:
            await self.stat(path)
            return True
        except Exception:
            return False

    async def stat(self, path: str) -> FileInfo:
        client = await self._ensure_client()
        file_info = await client.stat(path)
        return FileInfo(
            name=os.path.basename(path),
            size=int(file_info.get("size", 0)),
            is_dir=file_info["type"] == "dir",
            is_file=file_info["type"] == "file",
            permissions=str(file_info.get("permissions", "")),
            mtime=float(file_info.get("modify", 0.0)),
            owner=str(file_info.get("owner", "")),
            group=str(file_info.get("group", "")),
        )

    async def read_text(self, path: str) -> str:
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / os.path.basename(path)
        try:
            await self.download(path, temp_path)
            async_path = AsyncPath(temp_path)
            return await async_path.read_text()
        finally:
            if temp_path.exists():
                temp_path.unlink()
            if Path(temp_dir).exists():
                os.rmdir(temp_dir)

    async def read_bytes(self, path: str) -> bytes:
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / os.path.basename(path)
        try:
            await self.download(path, temp_path)
            async_path = AsyncPath(temp_path)
            return await async_path.read_bytes()
        finally:
            if temp_path.exists():
                temp_path.unlink()
            if Path(temp_dir).exists():
                os.rmdir(temp_dir)

    async def write_text(self, path: str, content: str) -> None:
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / os.path.basename(path)
        try:
            async_path = AsyncPath(temp_path)
            await async_path.write_text(content)
            await self.upload(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
            if Path(temp_dir).exists():
                os.rmdir(temp_dir)

    async def write_bytes(self, path: str, content: bytes) -> None:
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / os.path.basename(path)
        try:
            async_path = AsyncPath(temp_path)
            await async_path.write_bytes(content)
            await self.upload(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
            if Path(temp_dir).exists():
                os.rmdir(temp_dir)


depends.set(Ftpd, "ftp")

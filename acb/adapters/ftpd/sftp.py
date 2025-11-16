from __future__ import annotations

import os
from functools import cached_property
from pathlib import Path
from uuid import UUID

import asyncio
import typing as t
from contextlib import asynccontextmanager, suppress

try:
    import asyncssh
    from asyncssh import (
        Error,
        SFTPClient,
        SFTPServer,
        SSHClientConnection,
        SSHServerConnection,
        SSHServerProcess,
    )
except Exception:  # pragma: no cover - allow tests without asyncssh installed
    import os as _os
    import sys as _sys

    if "pytest" in _sys.modules or _os.getenv("TESTING", "False").lower() == "true":
        from unittest.mock import MagicMock

        asyncssh = MagicMock()  # type: ignore[assignment, no-redef]
        Error = Exception  # type: ignore[assignment, no-redef]
        SFTPClient = MagicMock  # type: ignore[assignment, no-redef]
        SFTPServer = MagicMock  # type: ignore[assignment, no-redef]
        SSHClientConnection = MagicMock  # type: ignore[assignment, no-redef]
        SSHServerConnection = MagicMock  # type: ignore[assignment, no-redef]
        SSHServerProcess = MagicMock  # type: ignore[assignment, no-redef]
    else:
        raise
from acb.adapters import AdapterStatus

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b80fef01e7c2")
MODULE_STATUS = AdapterStatus.STABLE
from pydantic import Field

from acb.depends import Inject, depends

from ._base import FileInfo, FtpdBase, FtpdBaseSettings


class FtpdSettings(FtpdBaseSettings):
    port: int = 8022
    server_host_keys: list[str] = Field(default_factory=list)
    authorized_client_keys: str | None = None
    known_hosts: str | None = None
    client_keys: list[str] = Field(default_factory=list)


class SFTPHandler(SFTPServer):  # type: ignore[misc]
    def __init__(self, conn: SSHServerConnection) -> None:
        conn.get_extra_info("ftpd_root_dir")
        super().__init__(t.cast("t.Any", conn), chroot=None)


class Ftpd(FtpdBase):
    _server: t.Any = None  # type: ignore[assignment]
    _client: SSHClientConnection | None = None  # type: ignore[assignment]
    _sftp_client: SFTPClient | None = None
    _server_task: asyncio.Task[t.Any] | None = None
    _server_acceptor: asyncssh.SSHAcceptor | None = None

    @cached_property
    def server_factory(self) -> t.Callable[..., t.Any]:
        return SFTPHandler

    @depends.inject
    async def start(self, logger: Inject[t.Any]) -> None:
        try:
            Path(self.config.ftpd.root_dir).mkdir(parents=True, exist_ok=True)
            self._server_acceptor = await asyncssh.create_server(
                self._create_server_connection,
                self.config.ftpd.host,
                self.config.ftpd.port,
                server_host_keys=self.config.ftpd.server_host_keys,
                authorized_client_keys=self.config.ftpd.authorized_client_keys,
                sftp_factory=self.server_factory,
                process_factory=self._process_factory,
                encoding=None,
            )
            logger.info(  # type: ignore[no-untyped-call]
                f"SFTP server started on {self.config.ftpd.host}:{self.config.ftpd.port}",
            )
        except (OSError, Error) as exc:
            logger.exception(f"Error starting SFTP server: {exc}")  # type: ignore[no-untyped-call]
            raise

    def _create_server_connection(self) -> asyncssh.SSHServer:
        class ServerConnection(asyncssh.SSHServer):  # type: ignore[misc]
            def __init__(self, config: t.Any) -> None:
                self.config = config

            def connection_made(self, conn: SSHServerConnection) -> None:
                conn.set_extra_info(ftpd_root_dir=self.config.ftpd.root_dir)

            def begin_auth(self, username: str) -> bool:
                return not (self.config.ftpd.anonymous and username == "anonymous")

            def password_auth_supported(self) -> bool:
                return True

            def validate_password(self, username: str, password: str) -> bool:
                if username == self.config.ftpd.username:
                    return password == self.config.ftpd.password.get_secret_value()
                return False

        return ServerConnection(self.config)

    def _process_factory(self, process: SSHServerProcess[t.Any]) -> None:
        process.exit(0)

    @depends.inject
    async def stop(self, logger: Inject[t.Any]) -> None:
        try:
            if self._server and self._server_acceptor:
                self._server_acceptor.close()
                await self._server_acceptor.wait_closed()
                self._server_acceptor = None
            logger.info("SFTP server stopped")  # type: ignore[no-untyped-call]
        except Exception as exc:
            logger.exception(f"Error stopping SFTP server: {exc}")  # type: ignore[no-untyped-call]
            raise

    async def _ensure_client(self) -> SFTPClient:
        if self._client is None or self._sftp_client is None:
            self._client = await asyncssh.connect(
                self.config.ftpd.host,
                self.config.ftpd.port,
                username=self.config.ftpd.username,
                password=self.config.ftpd.password.get_secret_value(),
                known_hosts=self.config.ftpd.known_hosts,
                client_keys=self.config.ftpd.client_keys or None,
                encoding=None,
            )
            self._sftp_client = await self._client.start_sftp_client()
        return self._sftp_client

    @asynccontextmanager
    async def connect(self) -> t.AsyncGenerator[Ftpd]:
        client = await self._ensure_client()
        try:
            yield self
        finally:
            if client:
                with suppress(AttributeError, Exception):
                    await client.__aexit__(None, None, None)
            if self._client:
                self._client.close()
            self._sftp_client = None
            self._client = None

    async def upload(self, local_path: Path, remote_path: str) -> None:
        client = await self._ensure_client()
        await client.put(str(local_path), remote_path)

    async def download(self, remote_path: str, local_path: Path) -> None:
        client = await self._ensure_client()
        await client.get(remote_path, str(local_path))

    async def list_dir(self, path: str) -> list[FileInfo]:
        client = await self._ensure_client()
        result = []
        for file_attr in await client.listdir(path):
            info = FileInfo(
                name=getattr(file_attr, "filename", file_attr),
                size=getattr(file_attr, "size", 0) or 0,
                is_dir=getattr(file_attr, "is_dir", bool)(),
                is_file=getattr(file_attr, "is_file", lambda: True)(),
                is_symlink=getattr(file_attr, "is_symlink", bool)(),
                permissions=str(getattr(file_attr, "permissions", 0)),
                mtime=getattr(file_attr, "mtime", 0.0) or 0.0,
                owner=str(getattr(file_attr, "uid", 0)),
                group=str(getattr(file_attr, "gid", 0)),
            )
            result.append(info)
        return result

    async def mkdir(self, path: str) -> None:
        client = await self._ensure_client()
        await client.mkdir(path)

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
        await client.rmdir(path)

    async def delete(self, path: str) -> None:
        client = await self._ensure_client()
        await client.remove(path)

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
        file_attr = await client.stat(path)
        return FileInfo(
            name=os.path.basename(path),
            size=getattr(file_attr, "size", 0) or 0,
            is_dir=getattr(file_attr, "is_dir", bool)(),
            is_file=getattr(file_attr, "is_file", lambda: True)(),
            is_symlink=getattr(file_attr, "is_symlink", bool)(),
            permissions=str(getattr(file_attr, "permissions", 0)),
            mtime=getattr(file_attr, "mtime", 0.0) or 0.0,
            owner=str(getattr(file_attr, "uid", 0)),
            group=str(getattr(file_attr, "gid", 0)),
        )

    async def read_text(self, path: str) -> str:
        return (await self.read_bytes(path)).decode()

    async def read_bytes(self, path: str) -> bytes:
        client = await self._ensure_client()
        async with client.open(path, "rb") as f:
            return await f.read()

    async def write_text(self, path: str, content: str) -> None:
        await self.write_bytes(path, content.encode())

    async def write_bytes(self, path: str, content: bytes) -> None:
        client = await self._ensure_client()
        async with client.open(path, "wb") as f:
            await f.write(content)


depends.set(Ftpd, "sftp")

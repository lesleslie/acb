import typing as t
from typing import BinaryIO
from uuid import UUID

from anyio import Path as AsyncPath
from fsspec.asyn import AsyncFileSystem
from fsspec.implementations.asyn_wrapper import AsyncFileSystemWrapper
from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.local import LocalFileSystem
from acb.adapters import AdapterStatus
from acb.depends import depends

from ._base import StorageBase, StorageBaseSettings

MODULE_ID = UUID("0197ff45-2d3a-7890-a4b2-1c8f6e9d2a73")
MODULE_STATUS = AdapterStatus.STABLE


class StorageSettings(StorageBaseSettings): ...


class Storage(StorageBase):
    file_system: t.Any = DirFileSystem

    def __init__(self, root_dir: str | None = None, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self.root_dir = root_dir

    async def _create_client(self) -> AsyncFileSystem:
        if self.root_dir is not None:
            path = self.root_dir
        else:
            try:
                path = (
                    str(self.config.storage.local_path)
                    if hasattr(self.config, "storage")
                    else "."
                )
            except AttributeError:
                path = "."
        fs = LocalFileSystem(auto_mkdir=True, asynchronous=False)
        dirfs = self.file_system(path=path, fs=fs)
        return AsyncFileSystemWrapper(dirfs)

    @property
    def client(self) -> t.Any:
        if self._client is None:
            msg = "Client not initialized. Call get_client() first."
            raise RuntimeError(msg)
        return self._client

    async def get_client(self) -> t.Any:
        return await self._ensure_client()

    async def init(self) -> None:
        self._initialized = True
        await super().init()

    async def put_file(self, path: str, content: bytes) -> bool:
        try:
            if self.root_dir:
                full_path = AsyncPath(self.root_dir) / path
                await full_path.parent.mkdir(parents=True, exist_ok=True)
                await full_path.write_bytes(content)
                return True
            try:
                if isinstance(content, str):
                    content_bytes = content.encode("utf-8")
                else:
                    content_bytes = content
                with self.client.open(path, "wb") as f_obj:
                    f = t.cast("BinaryIO", f_obj)
                    f.write(content_bytes)
                return True
            except Exception as e:
                self.logger.exception(f"Error putting file {path}: {e}")
                return False
        except Exception as e:
            self.logger.exception(f"Error putting file {path}: {e}")
            return False

    async def get_file(self, path: str) -> bytes | None:
        try:
            if self.root_dir:
                return await self._get_file_from_root_dir(path)
            return await self._get_file_from_client(path)
        except Exception as e:
            self.logger.exception(f"Error getting file {path}: {e}")
            return None

    async def _get_file_from_root_dir(self, path: str) -> bytes | None:
        if self.root_dir is None:
            return None
        full_path = AsyncPath(self.root_dir) / path
        if not await full_path.exists():
            return None
        return await full_path.read_bytes()

    async def _get_file_from_client(self, path: str) -> bytes | None:
        if not await self.file_exists(path):
            return None
        try:
            with self.client.open(path, "rb") as f:
                content = f.read()
                if isinstance(content, str):
                    return content.encode("utf-8")
                return content
        except Exception as e:
            self.logger.exception(f"Error getting file {path}: {e}")
            return None

    async def delete_file(self, path: str) -> bool:
        try:
            if self.root_dir:
                full_path = AsyncPath(self.root_dir) / path
                if not await full_path.exists():
                    return False
                await full_path.unlink()
                return True
            if not await self.file_exists(path):
                return False
            try:
                self.client.rm(path)
                return True
            except Exception as e:
                self.logger.exception(f"Error deleting file {path}: {e}")
                return False
        except Exception as e:
            self.logger.exception(f"Error deleting file {path}: {e}")
            return False

    async def file_exists(self, path: str) -> bool:
        try:
            if self.root_dir:
                full_path = AsyncPath(self.root_dir) / path
                return await full_path.exists() and await full_path.is_file()
            try:
                return self.client.exists(path)
            except Exception as e:
                self.logger.exception(f"Error checking if file exists {path}: {e}")
                return False
        except Exception as e:
            self.logger.exception(f"Error checking if file exists {path}: {e}")
            return False

    async def create_directory(self, path: str) -> bool:
        try:
            if self.root_dir:
                full_path = AsyncPath(self.root_dir) / path
                await full_path.mkdir(parents=True, exist_ok=True)
                return True
            try:
                self.client.mkdir(path, create_parents=True)
                return True
            except Exception as e:
                self.logger.exception(f"Error creating directory {path}: {e}")
                return False
        except Exception as e:
            self.logger.exception(f"Error creating directory {path}: {e}")
            return False

    async def directory_exists(self, path: str) -> bool:
        try:
            if self.root_dir:
                full_path = AsyncPath(self.root_dir) / path
                return await full_path.exists() and await full_path.is_dir()
            try:
                return self.client.exists(path) and self.client.isdir(path)
            except Exception as e:
                self.logger.exception(f"Error checking if directory exists {path}: {e}")
                return False
        except Exception as e:
            self.logger.exception(f"Error checking if directory exists {path}: {e}")
            return False


depends.set(Storage)

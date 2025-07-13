import typing as t
from uuid import UUID

from fsspec.implementations.memory import MemoryFileSystem
from acb.adapters import AdapterStatus
from acb.depends import depends

from ._base import StorageBase, StorageBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b7c8fab944af")
MODULE_STATUS = AdapterStatus.STABLE


class StorageSettings(StorageBaseSettings): ...


class Storage(StorageBase):
    file_system: t.Any = MemoryFileSystem

    async def init(self) -> None:
        self._initialized = True
        self._files: dict[str, bytes] = {}
        self._directories: set[str] = set()
        await super().init()

    async def put_file(self, path: str, content: bytes) -> bool:
        if not hasattr(self, "_files"):
            self._files: dict[str, bytes] = {}
        if not hasattr(self, "_directories"):
            self._directories: set[str] = set()
        self._files[path] = content
        parts = path.split("/")
        if len(parts) > 1:
            directory = "/".join(parts[:-1])
            self._directories.add(directory)
        return True

    async def get_file(self, path: str) -> bytes | None:
        if not hasattr(self, "_files"):
            self._files: dict[str, bytes] = {}
        return self._files.get(path)

    async def delete_file(self, path: str) -> bool:
        if not hasattr(self, "_files"):
            self._files: dict[str, bytes] = {}
        if path in self._files:
            del self._files[path]
            return True
        return False

    async def file_exists(self, path: str) -> bool:
        if not hasattr(self, "_files"):
            self._files: dict[str, bytes] = {}
        return path in self._files

    async def create_directory(self, path: str) -> bool:
        if not hasattr(self, "_directories"):
            self._directories: set[str] = set()
        self._directories.add(path)
        return True

    async def directory_exists(self, path: str) -> bool:
        if not hasattr(self, "_directories"):
            self._directories: set[str] = set()
            return False
        return path in self._directories


depends.set(Storage)

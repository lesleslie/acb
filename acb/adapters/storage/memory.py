from uuid import UUID

import typing as t
from fsspec.implementations.memory import MemoryFileSystem

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import StorageBase, StorageBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b7c8fab944af")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Memory Storage",
    category="storage",
    provider="memory",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-20",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.BULK_OPERATIONS,
    ],
    required_packages=["fsspec"],
    description="In-memory storage adapter for testing and caching",
    settings_class="StorageSettings",
    config_example={
        "root_dir": "/tmp/memory_storage",  # nosec B108
    },
)


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
            self._files = {}
        if not hasattr(self, "_directories"):
            self._directories = set()
        self._files[path] = content
        parts = path.split("/")
        if len(parts) > 1:
            directory = "/".join(parts[:-1])
            self._directories.add(directory)
        return True

    async def get_file(self, path: str) -> bytes | None:
        if not hasattr(self, "_files"):
            self._files = {}
        return self._files.get(path)

    async def delete_file(self, path: str) -> bool:
        if not hasattr(self, "_files"):
            self._files = {}
        if path in self._files:
            del self._files[path]
            return True
        return False

    async def file_exists(self, path: str) -> bool:
        if not hasattr(self, "_files"):
            self._files = {}
        return path in self._files

    async def create_directory(self, path: str) -> bool:
        if not hasattr(self, "_directories"):
            self._directories = set()
        self._directories.add(path)
        return True

    async def directory_exists(self, path: str) -> bool:
        if not hasattr(self, "_directories"):
            self._directories = set()
            return False
        return path in self._directories


depends.set(Storage, "memory")

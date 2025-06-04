"""Mock implementations of storage adapters for testing."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from acb.adapters.storage._base import StorageBase


class MockFileStorage(StorageBase):
    def __init__(self, root_dir: str | Path | None = None) -> None:  # nosec B108
        if root_dir is None:
            root_dir = Path(tempfile.mkdtemp(prefix="mock_storage_"))
        self._root_dir = str(root_dir)
        self._files: dict[str, bytes] = {}
        self._directories: set[str] = set()
        self._initialized = True
        self.config = MagicMock()
        self.config.app.name = "test"

    async def put_file(self, path: str, content: bytes) -> bool:
        parent_dir = os.path.dirname(path)
        if parent_dir:
            await self.create_directory(parent_dir)

        self._files[path] = content
        return True

    async def get_file(self, path: str) -> bytes | None:
        return self._files.get(path)

    async def delete_file(self, path: str) -> bool:
        if path in self._files:
            del self._files[path]
            return True
        return False

    async def file_exists(self, path: str) -> bool:
        return path in self._files

    async def list_files(self, prefix: str | None = None) -> list[str]:
        if prefix is None:
            return list(self._files.keys())

        return [path for path in self._files if path.startswith(prefix)]

    async def get_file_url(self, path: str) -> str:
        return f"file://{self._root_dir}/{path}"

    async def get_file_size(self, path: str) -> int | None:
        if path in self._files:
            return len(self._files[path])
        return None

    async def copy_file(self, source_path: str, dest_path: str) -> bool:
        if source_path in self._files:
            self._files[dest_path] = self._files[source_path]
            return True
        return False

    async def move_file(self, source_path: str, dest_path: str) -> bool:
        if source_path in self._files:
            self._files[dest_path] = self._files[source_path]
            del self._files[source_path]
            return True
        return False

    async def create_directory(self, path: str) -> bool:
        self._directories.add(path)

        parts = path.split("/")
        for i in range(1, len(parts)):
            parent = "/".join(parts[:i])
            if parent:
                self._directories.add(parent)

        return True

    async def delete_directory(self, path: str) -> bool:
        if path not in self._directories:
            return False

        self._directories.remove(path)

        files_to_delete = [
            file_path for file_path in self._files if file_path.startswith(f"{path}/")
        ]
        for file_path in files_to_delete:
            del self._files[file_path]

        dirs_to_delete = [
            dir_path
            for dir_path in self._directories
            if dir_path.startswith(f"{path}/")
        ]
        for dir_path in dirs_to_delete:
            self._directories.remove(dir_path)

        return True

    async def list_directories(self, prefix: str | None = None) -> list[str]:
        if prefix is None:
            return sorted(list(self._directories))

        return sorted([path for path in self._directories if path.startswith(prefix)])

    async def directory_exists(self, path: str) -> bool:
        return path in self._directories

    async def init(self) -> None:
        self._initialized = True


class MockMemoryStorage(StorageBase):
    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}
        self._directories: set[str] = set()
        self._initialized = True
        self.config = MagicMock()
        self.config.app.name = "test"

    async def put_file(self, path: str, content: bytes) -> bool:
        parent_dir = os.path.dirname(path)
        if parent_dir:
            await self.create_directory(parent_dir)

        self._files[path] = content
        return True

    async def get_file(self, path: str) -> bytes | None:
        return self._files.get(path)

    async def delete_file(self, path: str) -> bool:
        if path in self._files:
            del self._files[path]
            return True
        return False

    async def file_exists(self, path: str) -> bool:
        return path in self._files

    async def list_files(self, prefix: str | None = None) -> list[str]:
        if prefix is None:
            return list(self._files.keys())

        return [path for path in self._files if path.startswith(prefix)]

    async def get_file_url(self, path: str) -> str:
        return f"memory://storage/{path}"

    async def get_file_size(self, path: str) -> int | None:
        if path in self._files:
            return len(self._files[path])
        return None

    async def copy_file(self, source_path: str, dest_path: str) -> bool:
        if source_path in self._files:
            self._files[dest_path] = self._files[source_path]
            return True
        return False

    async def move_file(self, source_path: str, dest_path: str) -> bool:
        if source_path in self._files:
            self._files[dest_path] = self._files[source_path]
            del self._files[source_path]
            return True
        return False

    async def create_directory(self, path: str) -> bool:
        self._directories.add(path)

        parts = path.split("/")
        for i in range(1, len(parts)):
            parent = "/".join(parts[:i])
            if parent:
                self._directories.add(parent)

        return True

    async def delete_directory(self, path: str) -> bool:
        if path not in self._directories:
            return False

        self._directories.remove(path)

        files_to_delete = [
            file_path for file_path in self._files if file_path.startswith(f"{path}/")
        ]
        for file_path in files_to_delete:
            del self._files[file_path]

        dirs_to_delete = [
            dir_path
            for dir_path in self._directories
            if dir_path.startswith(f"{path}/")
        ]
        for dir_path in dirs_to_delete:
            self._directories.remove(dir_path)

        return True

    async def list_directories(self, prefix: str | None = None) -> list[str]:
        if prefix is None:
            return sorted(list(self._directories))

        return sorted([path for path in self._directories if path.startswith(prefix)])

    async def directory_exists(self, path: str) -> bool:
        return path in self._directories

    async def init(self) -> None:
        self._initialized = True

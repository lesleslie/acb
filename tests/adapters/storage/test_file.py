"""Simplified tests for the File Storage adapter."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.test_interfaces import StorageTestInterface


class MockFileStorage:
    def __init__(self, root_dir: str | None = None) -> None:
        self.root_dir: str = root_dir if root_dir is not None else "."
        self._initialized: bool = False
        self._files: dict[str, bytes] = {}
        self._directories: set[str] = set()

    async def init(self) -> "MockFileStorage":
        self._initialized = True
        return self

    async def put_file(self, path: str, content: bytes) -> bool:
        parent_dir: str = "/".join(path.split("/")[:-1])
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

    async def create_directory(self, path: str) -> bool:
        self._directories.add(path)
        parts: list[str] = path.split("/")
        for i in range(1, len(parts)):
            parent: str = "/".join(parts[:i])
            if parent:
                self._directories.add(parent)
        return True

    async def directory_exists(self, path: str) -> bool:
        return path in self._directories


@pytest.fixture
def mock_path() -> MagicMock:
    mock_path: MagicMock = MagicMock(spec=Path)
    mock_path.__truediv__.return_value = mock_path
    mock_path.exists.return_value = True
    mock_path.is_file.return_value = True
    mock_path.is_dir.return_value = True
    return mock_path


@pytest.fixture
async def storage(tmp_path: Path) -> MockFileStorage:
    storage: MockFileStorage = MockFileStorage(root_dir=str(tmp_path / "mock_storage"))
    await storage.init()
    return storage


class TestFileStorage(StorageTestInterface):
    pass

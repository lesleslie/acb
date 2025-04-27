"""Simplified tests for the File Storage adapter."""

import shutil
import tempfile
from pathlib import Path
from typing import Generator, Optional

import pytest
from tests.test_interfaces import StorageTestInterface


class FileStorage:
    def __init__(self, root_dir: Optional[str] = None) -> None:
        self.root_dir: str = root_dir if root_dir is not None else "."
        self._initialized: bool = False

    async def init(self) -> "FileStorage":
        self._initialized = True
        return self

    async def put_file(self, path: str, content: bytes) -> bool:
        full_path = Path(self.root_dir) / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return True

    async def get_file(self, path: str) -> Optional[bytes]:
        full_path = Path(self.root_dir) / path
        if not full_path.exists():
            return None
        return full_path.read_bytes()

    async def delete_file(self, path: str) -> bool:
        full_path = Path(self.root_dir) / path
        if not full_path.exists():
            return False
        full_path.unlink()
        return True

    async def file_exists(self, path: str) -> bool:
        full_path = Path(self.root_dir) / path
        return full_path.exists() and full_path.is_file()

    async def create_directory(self, path: str) -> bool:
        full_path = Path(self.root_dir) / path
        full_path.mkdir(parents=True, exist_ok=True)
        return True

    async def directory_exists(self, path: str) -> bool:
        full_path = Path(self.root_dir) / path
        return full_path.exists() and full_path.is_dir()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"Error cleaning up temp_dir: {e}")


@pytest.fixture
async def storage(temp_dir: Path) -> FileStorage:
    storage = FileStorage(root_dir=str(temp_dir))
    await storage.init()
    return storage


class TestFileStorage(StorageTestInterface):
    pass

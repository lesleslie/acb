import hashlib
import json
import os
import typing as t
from pathlib import Path
from warnings import catch_warnings

from anyio import Path as AsyncPath
from blake3 import blake3
from google_crc32c import value as crc32c_value

__all__: list[str] = ["hash"]
with catch_warnings(action="ignore", category=RuntimeWarning):
    from google_crc32c import value as crc32c_value


class Blake3Hasher:
    def __init__(self) -> None:
        self._hasher = blake3()

    def update(self, data: bytes | str) -> "Blake3Hasher":
        if isinstance(data, str):
            data = data.encode()
        self._hasher.update(data)
        return self

    def finalize(self) -> t.Any:
        return self._hasher.digest()

    def hexdigest(self) -> str:
        return self._hasher.hexdigest()


class Hash:
    @staticmethod
    def create_blake3() -> Blake3Hasher:
        return Blake3Hasher()

    @staticmethod
    async def blake3(
        obj: Path
        | AsyncPath
        | list[str]
        | bytes
        | str
        | dict[str, t.Any]
        | None = None,
    ) -> str:
        if obj is None:
            raise TypeError("Cannot hash None value")
        if isinstance(obj, Path | AsyncPath):
            path = AsyncPath(obj)
            if not await path.exists():
                raise FileNotFoundError(f"File not found: {obj}")
            obj = await path.read_bytes()
        elif isinstance(obj, str) and (os.path.sep in obj or obj.startswith(".")):
            path = AsyncPath(obj)
            if not await path.exists():
                raise FileNotFoundError(f"File not found: {obj}")
            obj = await path.read_bytes()
        elif isinstance(obj, dict):
            obj = json.dumps(obj, sort_keys=True).encode()
        elif isinstance(obj, list):
            obj = "".join([str(a) for a in obj]).encode()
        elif isinstance(obj, str):
            obj = obj.encode()
        return blake3(obj).hexdigest()

    @staticmethod
    async def crc32c(obj: Path | AsyncPath | str | bytes | dict[str, t.Any]) -> str:
        if isinstance(obj, Path | AsyncPath):
            path = AsyncPath(obj)
            if not await path.exists():
                raise FileNotFoundError(f"File not found: {obj}")
            obj = await path.read_bytes()
        elif isinstance(obj, str) and (os.path.sep in obj or obj.startswith(".")):
            path = AsyncPath(obj)
            if not await path.exists():
                raise FileNotFoundError(f"File not found: {obj}")
            obj = await path.read_bytes()
        elif isinstance(obj, dict):
            obj = json.dumps(obj, sort_keys=True).encode()
        elif isinstance(obj, str):
            obj = obj.encode()
        return f"{crc32c_value(obj):08x}"

    @staticmethod
    async def md5(
        obj: Path | AsyncPath | str | bytes | dict[str, t.Any],
        usedforsecurity: bool = False,
    ) -> str:
        if isinstance(obj, Path | AsyncPath):
            path = AsyncPath(obj)
            if not await path.exists():
                raise FileNotFoundError(f"File not found: {obj}")
            obj = await path.read_bytes()
        elif isinstance(obj, str) and (os.path.sep in obj or obj.startswith(".")):
            path = AsyncPath(obj)
            if not await path.exists():
                raise FileNotFoundError(f"File not found: {obj}")
            obj = await path.read_bytes()
        elif isinstance(obj, dict):
            obj = json.dumps(obj, sort_keys=True).encode()
        elif isinstance(obj, str):
            obj = obj.encode()
        return hashlib.md5(obj, usedforsecurity=usedforsecurity).hexdigest()


hash: Hash = Hash()

import hashlib
import json
import os
from pathlib import Path
from warnings import catch_warnings

import typing as t
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
    async def _normalize_input(obj: t.Any) -> bytes:
        if obj is None:
            msg = "Cannot hash None value"
            raise TypeError(msg)
        if isinstance(obj, Path | AsyncPath) or (
            isinstance(obj, str) and (os.path.sep in obj or obj.startswith("."))
        ):
            path = AsyncPath(str(obj))
            if not await path.exists():
                msg = f"File not found: {obj}"
                raise FileNotFoundError(msg)
            return await path.read_bytes()
        if isinstance(obj, dict):
            return json.dumps(obj, sort_keys=True).encode()
        if isinstance(obj, list):
            return "".join([str(a) for a in obj]).encode()
        if isinstance(obj, str):
            return obj.encode()
        if isinstance(obj, bytes):
            return obj
        msg = f"Unsupported type for hashing: {type(obj)}"
        raise TypeError(msg)

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
        data = await Hash._normalize_input(obj)
        return blake3(data).hexdigest()

    @staticmethod
    async def crc32c(obj: Path | AsyncPath | str | bytes | dict[str, t.Any]) -> str:
        data = await Hash._normalize_input(obj)
        return f"{crc32c_value(data):08x}"

    @staticmethod
    async def md5(
        obj: Path | AsyncPath | str | bytes | dict[str, t.Any],
        usedforsecurity: bool = False,
    ) -> str:
        data = await Hash._normalize_input(obj)
        return hashlib.md5(data, usedforsecurity=usedforsecurity).hexdigest()


hash: Hash = Hash()

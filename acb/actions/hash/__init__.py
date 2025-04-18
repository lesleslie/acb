import hashlib
from pathlib import Path
from warnings import catch_warnings

import arrow
from anyio import Path as AsyncPath
from blake3 import blake3  # type: ignore

__all__: list[str] = ["hash"]

with catch_warnings(action="ignore", category=RuntimeWarning):
    from google_crc32c import value as crc32c


class Hash:
    @staticmethod
    async def blake3(obj: Path | AsyncPath | list[str] | bytes | str) -> str:
        if not obj:
            timestamp = arrow.utcnow().float_timestamp
            obj = str(timestamp)
        elif isinstance(obj, Path | AsyncPath):
            obj = await AsyncPath(obj).read_bytes()
        elif isinstance(obj, list):
            obj = "".join([str(a) for a in obj])
        if not isinstance(obj, bytes):
            obj = obj.encode()  # type: ignore
        return blake3(obj).hexdigest()

    @staticmethod
    async def crc32c(obj: Path | AsyncPath | str) -> int:
        if isinstance(obj, Path | AsyncPath):
            obj = await AsyncPath(obj).read_text()
        return crc32c(obj.encode())  # type: ignore

    @staticmethod
    async def md5(
        obj: Path | AsyncPath | str, ascii: bool = False, usedforsecurity: bool = True
    ) -> str:
        if isinstance(obj, Path | AsyncPath):
            obj = await AsyncPath(obj).read_text()
        return hashlib.md5(
            obj.encode() if not ascii else obj.encode("ascii"),  # type: ignore
            usedforsecurity=usedforsecurity,
        ).hexdigest()


hash: Hash = Hash()

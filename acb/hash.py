from hashlib import blake2b
from pathlib import Path

import arrow
from aiopath import AsyncPath
from google_crc32c import value
from pydantic import BaseModel


class Hash(BaseModel):
    @staticmethod
    async def blake2b(obj: AsyncPath | Path | list | bytes | str) -> str:
        hash_obj = blake2b(digest_size=20)
        if not obj:
            timestamp = arrow.utcnow().float_timestamp
            obj = str(timestamp)
        elif isinstance(obj, AsyncPath | Path):
            obj = AsyncPath(obj) if isinstance(obj, Path) else obj
            obj = await obj.read_bytes()
        elif isinstance(obj, list):
            obj = "".join([str(a) for a in obj])
        if not isinstance(obj, bytes):
            obj = obj.encode()
        hash_obj.update(obj)
        return hash_obj.hexdigest()

    @staticmethod
    def crc32c(obj: Path | bytes | str) -> bytes:
        if isinstance(obj, Path):
            obj = obj.read_text()
        return value(obj.encode())

    @staticmethod
    async def acrc32c(obj: AsyncPath | Path | bytes | str) -> bytes:
        if isinstance(obj, AsyncPath | Path):
            obj = AsyncPath(obj) if isinstance(obj, Path) else obj
            obj = await obj.read_text()
        return value(obj.encode())


hash = Hash()

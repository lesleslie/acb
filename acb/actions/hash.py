from os import PathLike

import arrow
from aiopath import AsyncPath
from blake3 import blake3  # type: ignore
from google_crc32c import value as crc32c


class Hash:
    @staticmethod
    async def blake3(obj: PathLike | list | bytes | str) -> str:
        if not obj:
            timestamp = arrow.utcnow().float_timestamp
            obj = str(timestamp)
        elif isinstance(obj, PathLike):
            obj = await AsyncPath(obj).read_bytes()
        elif isinstance(obj, list):
            obj = "".join([str(a) for a in obj])
        if not isinstance(obj, bytes):
            obj = obj.encode()
        return blake3(obj).hexdigest()

    @staticmethod
    async def crc32c(obj: PathLike | bytes | str) -> bytes:
        if isinstance(obj, PathLike):
            obj = await AsyncPath(obj).read_text()
        return crc32c(obj.encode())


hash = Hash()

import typing as t
from gzip import GzipFile
from io import BytesIO
from pathlib import Path

import brotli
from pydantic import BaseModel


class Compress(BaseModel):
    @staticmethod
    def gzip(
        content: str | bytes,
        path: t.Optional[str | Path] = None,
        compresslevel: int = 6,
    ) -> bytes:
        gzip_buffer = BytesIO()
        gz = GzipFile(path, "wb", compresslevel, gzip_buffer)
        if path:
            if isinstance(content, bytes):
                gz.write(content)
            else:
                gz.write(content.encode())
        gz.close()
        return gzip_buffer.getvalue()

    @staticmethod
    def brotli(data: bytes | str, level: int = 3) -> bytes:
        if isinstance(data, str):
            data = data.encode()
        return brotli.compress(data, quality=level)


compress = Compress()


class Decompress(BaseModel):
    @staticmethod
    def brotli(data: bytes) -> str:
        return brotli.decompress(data).decode()

    @staticmethod
    def gzip(content: t.Any) -> str:
        gzip_buffer = BytesIO(content)
        return GzipFile(None, "rb", fileobj=gzip_buffer).read().decode()


decompress = Decompress()

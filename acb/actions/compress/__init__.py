from gzip import GzipFile
from io import BytesIO
from pathlib import Path

import brotli

__all__: list[str] = ["compress", "decompress"]


class Compress:
    @staticmethod
    def gzip(
        content: str | bytes,
        path: str | Path | None = None,
        compresslevel: int = 6,
    ) -> bytes:
        gzip_buffer = BytesIO()
        gz = GzipFile(
            filename=str(path) if path else None,
            mode="wb",
            compresslevel=compresslevel,
            fileobj=gzip_buffer,
        )

        data = content.encode() if isinstance(content, str) else content
        gz.write(data)
        gz.close()
        return gzip_buffer.getvalue()

    @staticmethod
    def brotli(data: bytes | str, level: int = 3) -> bytes:
        if isinstance(data, str):
            data = data.encode()
        return brotli.compress(data, quality=level)


compress = Compress()


class Decompress:
    @staticmethod
    def brotli(data: bytes) -> str:
        return brotli.decompress(data).decode()

    @staticmethod
    def gzip(content: bytes) -> str:
        gzip_buffer = BytesIO(content)
        with GzipFile(fileobj=gzip_buffer, mode="rb") as gz:
            decompressed = gz.read()
        return decompressed.decode()


decompress = Decompress()

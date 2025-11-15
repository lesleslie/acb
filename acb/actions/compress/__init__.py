import os
from gzip import BadGzipFile, GzipFile
from io import BytesIO
from pathlib import Path

import brotli

__all__: list[str] = ["compress", "decompress"]
ContentType = str | bytes | Path


def _normalize_input(content: ContentType) -> bytes:
    """Normalize input (Path, str, or bytes) to bytes for processing."""
    if isinstance(content, Path):
        if not content.exists():
            raise FileNotFoundError(f"File not found: {content}")
        return content.read_bytes()

    if isinstance(content, str) and (os.path.sep in content or content.startswith(".")):
        path = Path(content)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {content}")
        return path.read_bytes()

    return content.encode() if isinstance(content, str) else content


class Compress:
    @staticmethod
    def gzip(
        content: ContentType,
        output_path: str | Path | None = None,
        compresslevel: int = 6,
    ) -> bytes | None:
        data = _normalize_input(content)
        gzip_buffer = BytesIO()
        with GzipFile(
            mode="wb", compresslevel=compresslevel, fileobj=gzip_buffer
        ) as gz:
            gz.write(data)
        result = gzip_buffer.getvalue()
        if output_path is not None:
            Path(output_path).write_bytes(result)
            return None
        return result

    @staticmethod
    def brotli(content: ContentType, level: int = 3) -> bytes:
        data = _normalize_input(content)
        return brotli.compress(data, quality=level)


compress: Compress = Compress()


class Decompress:
    @staticmethod
    def gzip(content: ContentType) -> str:
        data = _normalize_input(content)
        try:
            with GzipFile(fileobj=BytesIO(data), mode="rb") as gz:
                return gz.read().decode()
        except BadGzipFile as e:
            raise BadGzipFile(f"Not a gzipped file: {e}") from e

    @staticmethod
    def brotli(content: ContentType) -> str:
        data = _normalize_input(content)
        return brotli.decompress(data).decode()


decompress: Decompress = Decompress()

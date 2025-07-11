import os
from gzip import BadGzipFile, GzipFile
from io import BytesIO
from pathlib import Path

import brotli

__all__: list[str] = ["compress", "decompress"]
ContentType = str | bytes | Path


class Compress:
    @staticmethod
    def gzip(
        content: ContentType,
        output_path: str | Path | None = None,
        compresslevel: int = 6,
    ) -> bytes | None:
        if isinstance(content, Path):
            if not content.exists():
                msg = f"File not found: {content}"
                raise FileNotFoundError(msg)
            data = content.read_bytes()
        elif isinstance(content, str) and (
            os.path.sep in content or content.startswith(".")
        ):
            path = Path(content)
            if not path.exists():
                msg = f"File not found: {content}"
                raise FileNotFoundError(msg)
            data = path.read_bytes()
        elif isinstance(content, str):
            data = content.encode()
        else:
            data = content
        gzip_buffer = BytesIO()
        gz = GzipFile(mode="wb", compresslevel=compresslevel, fileobj=gzip_buffer)
        gz.write(data)
        gz.close()
        result = gzip_buffer.getvalue()
        if output_path is not None:
            Path(output_path).write_bytes(result)
            return None
        return result

    @staticmethod
    def brotli(content: ContentType, level: int = 3) -> bytes:
        if isinstance(content, Path):
            if not content.exists():
                msg = f"File not found: {content}"
                raise FileNotFoundError(msg)
            data = content.read_bytes()
        elif isinstance(content, str) and (
            os.path.sep in content or content.startswith(".")
        ):
            path = Path(content)
            if not path.exists():
                msg = f"File not found: {content}"
                raise FileNotFoundError(msg)
            data = path.read_bytes()
        elif isinstance(content, str):
            data = content.encode()
        else:
            data = content
        return brotli.compress(data, quality=level)


compress: Compress = Compress()


class Decompress:
    @staticmethod
    def gzip(content: ContentType) -> str:
        if isinstance(content, Path):
            if not content.exists():
                msg = f"File not found: {content}"
                raise FileNotFoundError(msg)
            data = content.read_bytes()
        elif isinstance(content, str) and (
            os.path.sep in content or content.startswith(".")
        ):
            path = Path(content)
            if not path.exists():
                msg = f"File not found: {content}"
                raise FileNotFoundError(msg)
            data = path.read_bytes()
        elif isinstance(content, str):
            data = content.encode()
        else:
            data = content
        gzip_buffer = BytesIO(data)
        try:
            with GzipFile(fileobj=gzip_buffer, mode="rb") as gz:
                decompressed = gz.read()
            return decompressed.decode()
        except BadGzipFile as e:
            msg = f"Not a gzipped file: {e}"
            raise BadGzipFile(msg)

    @staticmethod
    def brotli(content: ContentType) -> str:
        if isinstance(content, Path):
            if not content.exists():
                msg = f"File not found: {content}"
                raise FileNotFoundError(msg)
            data = content.read_bytes()
        elif isinstance(content, str) and (
            os.path.sep in content or content.startswith(".")
        ):
            path = Path(content)
            if not path.exists():
                msg = f"File not found: {content}"
                raise FileNotFoundError(msg)
            data = path.read_bytes()
        elif isinstance(content, str):
            data = content.encode()
        else:
            data = content
        return brotli.decompress(data).decode()


decompress: Decompress = Decompress()

from gzip import GzipFile
from io import BytesIO
import typing as t

import brotli
from pydantic import BaseModel


class Compress(BaseModel):
    @staticmethod
    def gzip(content, fp=None, compresslevel=6):
        gzip_buffer = BytesIO()
        gz = GzipFile(fp, "wb", compresslevel, gzip_buffer)
        if fp:
            if isinstance(content, bytes):
                gz.write(content)
            else:
                gz.write(content.encode())
        gz.close()
        return gzip_buffer.getvalue()

    @staticmethod
    def brotli(data: bytes | str, level: int = 3):
        if isinstance(data, str):
            data = data.encode()
        return brotli.compress(data, quality=level)


compress = Compress()


class Decompress(BaseModel):
    @staticmethod
    def brotli(data: bytes):
        return brotli.decompress(data).decode()

    @staticmethod
    def gzip(content: t.Any):
        gzip_buffer = BytesIO(content)
        return GzipFile(None, "rb", fileobj=gzip_buffer).read().decode()


decompress = Decompress()

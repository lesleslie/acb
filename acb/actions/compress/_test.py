import gzip
from io import BytesIO
from pathlib import Path

from acb.actions.compress import compress, decompress

test_string = (
    "If the sun refused to shine...I would still be loving you...If "
    "mountains crumble to the sea...There will still be you and me"
    "...blah...blah...blah...blah...blah...blah...something"
)

bytes_test_string = (
    b"If the sun refused to shine...I would still be loving you...If "
    b"mountains crumble to the sea...There will still be you and me"
    b"...blah...blah...blah...blah...blah...blah...something"
)


class TestCompress:
    def test_gzip_compress_bytes(self) -> None:
        data = bytes_test_string
        compressed_data = compress.gzip(data)
        assert isinstance(compressed_data, bytes)
        assert len(compressed_data) < len(data)

        with gzip.GzipFile(fileobj=BytesIO(compressed_data), mode="rb") as f:
            decompressed_data = f.read()
        assert decompressed_data == data

    def test_gzip_compress_string(self) -> None:
        data = test_string
        compressed_data = compress.gzip(data)
        assert isinstance(compressed_data, bytes)
        assert len(compressed_data) < len(data.encode())

        with gzip.GzipFile(fileobj=BytesIO(compressed_data), mode="rb") as f:
            decompressed_data = f.read()
        assert decompressed_data == data.encode()

    def test_gzip_compress_with_path(self, tmp_path: Path) -> None:
        data = bytes_test_string
        file_path = tmp_path / "test.txt"
        compressed_data = compress.gzip(data, path=file_path)
        assert isinstance(compressed_data, bytes)
        assert len(compressed_data) < len(data)

        with gzip.GzipFile(fileobj=BytesIO(compressed_data), mode="rb") as f:
            decompressed_data = f.read()
        assert decompressed_data == data

    def test_gzip_compress_with_custom_level(self) -> None:
        data = bytes_test_string
        compressed_data_default = compress.gzip(data)
        compressed_data_best = compress.gzip(data, compresslevel=9)
        compressed_data_worst = compress.gzip(data, compresslevel=1)

        assert len(compressed_data_best) <= len(compressed_data_default)
        assert len(compressed_data_worst) >= len(compressed_data_default)
        assert len(compressed_data_best) <= len(compressed_data_worst)

    def test_brotli_compress_bytes(self) -> None:
        data = bytes_test_string
        compressed_data = compress.brotli(data)
        assert isinstance(compressed_data, bytes)
        assert len(compressed_data) < len(data)

        decompressed_data = decompress.brotli(compressed_data)
        assert decompressed_data == data.decode()

    def test_brotli_compress_string(self) -> None:
        data = test_string
        compressed_data = compress.brotli(data)
        assert isinstance(compressed_data, bytes)
        assert len(compressed_data) < len(data.encode())

        decompressed_data = decompress.brotli(compressed_data)
        assert decompressed_data == data

    def test_brotli_compress_with_custom_level(self) -> None:
        data = bytes_test_string
        compressed_data_default = compress.brotli(data)
        compressed_data_best = compress.brotli(data, level=11)
        compressed_data_worst = compress.brotli(data, level=0)

        assert len(compressed_data_best) < len(compressed_data_default)
        assert len(compressed_data_worst) > len(compressed_data_default)


class TestDecompress:
    def test_brotli_decompress(self) -> None:
        data = bytes_test_string
        compressed_data = compress.brotli(data)
        decompressed_data = decompress.brotli(compressed_data)
        assert decompressed_data == data.decode()

    def test_gzip_decompress(self) -> None:
        data = bytes_test_string
        compressed_data = compress.gzip(data)
        decompressed_data = decompress.gzip(compressed_data)
        assert decompressed_data == data.decode()

    def test_gzip_decompress_empty(self) -> None:
        data = b""
        compressed_data = compress.gzip(data)
        decompressed_data = decompress.gzip(compressed_data)
        assert decompressed_data == data.decode()

    def test_brotli_decompress_empty(self) -> None:
        data = b""
        compressed_data = compress.brotli(data)
        decompressed_data = decompress.brotli(compressed_data)
        assert decompressed_data == data.decode()

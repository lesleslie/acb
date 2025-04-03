import secrets
from pathlib import Path

from acb.actions.compress import compress, decompress


class TestCompress:
    def test_gzip_compress_bytes(self) -> None:
        data = b"This is a test string to be compressed."
        compressed_data = compress.gzip(data)
        assert isinstance(compressed_data, bytes)
        assert compressed_data != data

        decompressed_data = decompress.gzip(compressed_data)
        assert isinstance(decompressed_data, str)
        assert decompressed_data.encode() == data

    def test_gzip_compress_string(self) -> None:
        data = "This is a test string to be compressed."
        compressed_data = compress.gzip(data)
        assert isinstance(compressed_data, bytes)
        assert compressed_data != data.encode()

        decompressed_data = decompress.gzip(compressed_data)
        assert isinstance(decompressed_data, str)
        assert decompressed_data == data

    def test_gzip_compress_with_path(self, tmp_path: Path) -> None:
        data = b"This is a test string to be compressed with a path."
        file_path = tmp_path / "test.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        compressed_data = compress.gzip(data, path=file_path)
        assert isinstance(compressed_data, Path)
        assert compressed_data == file_path
        assert file_path.exists()

        with file_path.open("rb") as f:
            decompressed_data = decompress.gzip(f.read())
        assert isinstance(decompressed_data, str)
        assert decompressed_data.encode() == data

    def test_gzip_compress_with_custom_level(self) -> None:
        data = secrets.token_bytes(1024)
        compressed_data_level_1 = compress.gzip(data, compresslevel=1)
        compressed_data_level_9 = compress.gzip(data, compresslevel=9)
        assert isinstance(compressed_data_level_1, bytes)
        assert isinstance(compressed_data_level_9, bytes)
        assert compressed_data_level_1 != compressed_data_level_9
        assert len(compressed_data_level_1) > len(compressed_data_level_9)

        decompressed_data_level_1 = decompress.gzip(compressed_data_level_1)
        decompressed_data_level_9 = decompress.gzip(compressed_data_level_9)
        assert decompressed_data_level_1.encode() == data
        assert decompressed_data_level_9.encode() == data

    def test_brotli_compress_bytes(self) -> None:
        data = b"This is a test string to be compressed with brotli."
        compressed_data = compress.brotli(data)
        assert isinstance(compressed_data, bytes)
        assert compressed_data != data

        decompressed_data = decompress.brotli(compressed_data)
        assert isinstance(decompressed_data, str)
        assert decompressed_data.encode() == data

    def test_brotli_compress_string(self) -> None:
        data = "This is a test string to be compressed with brotli."
        compressed_data = compress.brotli(data)
        assert isinstance(compressed_data, bytes)
        assert compressed_data != data.encode()

        decompressed_data = decompress.brotli(compressed_data)
        assert isinstance(decompressed_data, str)
        assert decompressed_data == data

    def test_brotli_compress_with_custom_level(self) -> None:
        data = secrets.token_bytes(1024)
        compressed_data_level_1 = compress.brotli(data, level=1)
        compressed_data_level_9 = compress.brotli(data, level=9)
        assert isinstance(compressed_data_level_1, bytes)
        assert isinstance(compressed_data_level_9, bytes)
        assert compressed_data_level_1 != compressed_data_level_9
        assert len(compressed_data_level_1) > len(compressed_data_level_9)

        decompressed_data_level_1 = decompress.brotli(compressed_data_level_1)
        decompressed_data_level_9 = decompress.brotli(compressed_data_level_9)
        assert decompressed_data_level_1.encode() == data
        assert decompressed_data_level_9.encode() == data

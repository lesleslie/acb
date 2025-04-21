import gzip
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import brotli
from acb.actions.compress import compress, decompress


class TestCompress:
    def test_gzip_with_string(self) -> None:
        test_string = "test string to compress"

        compressed = compress.gzip(test_string)

        assert isinstance(compressed, bytes)

        gzip_buffer = BytesIO(compressed)
        with gzip.GzipFile(fileobj=gzip_buffer, mode="rb") as gz:
            pass

        gzip_buffer = BytesIO(compressed)
        with gzip.GzipFile(fileobj=gzip_buffer, mode="rb") as gz:
            decompressed = gz.read().decode()

        assert decompressed == test_string

    def test_gzip_with_bytes(self) -> None:
        test_bytes = b"test bytes to compress"

        compressed = compress.gzip(test_bytes)

        assert isinstance(compressed, bytes)

        gzip_buffer = BytesIO(compressed)
        with gzip.GzipFile(fileobj=gzip_buffer, mode="rb") as gz:
            pass

        gzip_buffer = BytesIO(compressed)
        with gzip.GzipFile(fileobj=gzip_buffer, mode="rb") as gz:
            decompressed = gz.read()

        assert decompressed == test_bytes

    def test_gzip_with_path(self) -> None:
        test_string = "test string with path"
        test_path = "test_file.txt"

        compressed = compress.gzip(test_string, path=test_path)

        gzip_buffer = BytesIO(compressed)
        with gzip.GzipFile(fileobj=gzip_buffer, mode="rb") as gz:
            decompressed = gz.read().decode()

        assert decompressed == test_string

    def test_gzip_with_path_object(self) -> None:
        test_string = "test string with path object"
        test_path = Path("test_file.txt")

        compressed = compress.gzip(test_string, path=test_path)

        gzip_buffer = BytesIO(compressed)
        with gzip.GzipFile(fileobj=gzip_buffer, mode="rb") as gz:
            decompressed = gz.read().decode()

        assert decompressed == test_string

    def test_gzip_with_compression_level(self) -> None:
        test_string = "test string " * 100

        compressed_min = compress.gzip(test_string, compresslevel=1)

        compressed_max = compress.gzip(test_string, compresslevel=9)

        assert len(compressed_min) >= len(compressed_max)

        gzip_buffer_min = BytesIO(compressed_min)
        with gzip.GzipFile(fileobj=gzip_buffer_min, mode="rb") as gz:
            decompressed_min = gz.read().decode()

        gzip_buffer_max = BytesIO(compressed_max)
        with gzip.GzipFile(fileobj=gzip_buffer_max, mode="rb") as gz:
            decompressed_max = gz.read().decode()

        assert decompressed_min == test_string
        assert decompressed_max == test_string

    def test_brotli_with_string(self) -> None:
        test_string = "test string to compress with brotli"

        compressed = compress.brotli(test_string)

        assert isinstance(compressed, bytes)

        decompressed = brotli.decompress(compressed).decode()
        assert decompressed == test_string

    def test_brotli_with_bytes(self) -> None:
        test_bytes = b"test bytes to compress with brotli"

        compressed = compress.brotli(test_bytes)

        assert isinstance(compressed, bytes)

        decompressed = brotli.decompress(compressed)
        assert decompressed == test_bytes

    def test_brotli_with_quality_levels(self) -> None:
        test_string = "test string " * 100

        compressed_min = compress.brotli(test_string, level=0)

        compressed_max = compress.brotli(test_string, level=11)

        assert len(compressed_min) >= len(compressed_max)

        decompressed_min = brotli.decompress(compressed_min).decode()
        decompressed_max = brotli.decompress(compressed_max).decode()

        assert decompressed_min == test_string
        assert decompressed_max == test_string

    def test_brotli_with_mock(self) -> None:
        test_string = "test string for mocked brotli"

        with patch("brotli.compress") as mock_compress:
            mock_compress.return_value = b"mocked compressed data"

            result = compress.brotli(test_string, level=5)

            assert result == b"mocked compressed data"
            mock_compress.assert_called_once_with(test_string.encode(), quality=5)


class TestDecompress:
    def test_gzip_decompress(self) -> None:
        original_string = "test string to compress and decompress"

        compressed = compress.gzip(original_string)

        decompressed = decompress.gzip(compressed)

        assert decompressed == original_string

    def test_gzip_decompress_with_mock(self) -> None:
        test_content = b"dummy compressed content"

        with patch("acb.actions.compress.GzipFile") as mock_gzip_file:
            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.read.return_value = b"mocked decompressed content"
            mock_gzip_file.return_value = mock_instance

            result = decompress.gzip(test_content)

            assert result == "mocked decompressed content"

            mock_gzip_file.assert_called_once()

    def test_brotli_decompress(self) -> None:
        original_string = "test string to compress and decompress with brotli"

        compressed = compress.brotli(original_string)

        decompressed = decompress.brotli(compressed)

        assert decompressed == original_string

    def test_brotli_decompress_with_mock(self) -> None:
        with patch("brotli.decompress") as mock_decompress:
            mock_decompress.return_value = b"decompressed content"

            result = decompress.brotli(b"compressed content")

            assert result == "decompressed content"
            mock_decompress.assert_called_once_with(b"compressed content")

    def test_gzip_decompress_large_content(self) -> None:
        original_string = "test string " * 1000

        compressed = compress.gzip(original_string)

        assert len(compressed) < len(original_string)

        decompressed = decompress.gzip(compressed)

        assert decompressed == original_string

    def test_brotli_decompress_large_content(self) -> None:
        original_string = "test string " * 1000

        compressed = compress.brotli(original_string)

        assert len(compressed) < len(original_string)

        decompressed = decompress.brotli(compressed)

        assert decompressed == original_string

    def test_gzip_decompress_binary_data(self) -> None:
        original_bytes = bytes([i % 256 for i in range(1000)])

        compressed = compress.gzip(original_bytes)

        gzip_buffer = BytesIO(compressed)
        with gzip.GzipFile(fileobj=gzip_buffer, mode="rb") as gz:
            decompressed = gz.read()

        assert decompressed == original_bytes

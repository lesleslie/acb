from gzip import GzipFile
from io import BytesIO
from pathlib import Path

import brotli
import pytest
from acb.actions.compress import Compress, Decompress, compress, decompress


class TestCompress:
    """Tests for the Compress class."""

    def test_compress_is_singleton_instance(self) -> None:
        """Test that compress is a singleton instance of Compress."""
        assert isinstance(compress, Compress)

    def test_gzip_with_string_input(self) -> None:
        """Test gzip compression with string input."""
        test_data = "Hello, world!"

        test_path = "test_file.txt"
        compressed = compress.gzip(test_data, path=test_path)

        assert isinstance(compressed, bytes)

        gzip_buffer = BytesIO(compressed)
        decompressed = GzipFile(None, "rb", fileobj=gzip_buffer).read().decode()
        assert decompressed == test_data

    def test_gzip_with_bytes_input(self) -> None:
        """Test gzip compression with bytes input."""
        test_data = b"Hello, world!"

        test_path = "test_file.txt"
        compressed = compress.gzip(test_data, path=test_path)

        assert isinstance(compressed, bytes)

        gzip_buffer = BytesIO(compressed)
        decompressed = GzipFile(None, "rb", fileobj=gzip_buffer).read()
        assert decompressed == test_data

    def test_gzip_with_path(self) -> None:
        """Test gzip compression with a path parameter."""
        test_data = "Hello, world!"
        test_path = "test_file.txt"

        compressed = compress.gzip(test_data, path=test_path)

        assert isinstance(compressed, bytes)

        gzip_buffer = BytesIO(compressed)
        decompressed = GzipFile(None, "rb", fileobj=gzip_buffer).read().decode()
        assert decompressed == test_data

    def test_gzip_with_path_object(self) -> None:
        """Test gzip compression with a Path object parameter."""
        test_data = "Hello, world!"
        test_path = Path("test_file.txt")

        compressed = compress.gzip(test_data, path=test_path)

        assert isinstance(compressed, bytes)

        gzip_buffer = BytesIO(compressed)
        decompressed = GzipFile(None, "rb", fileobj=gzip_buffer).read().decode()
        assert decompressed == test_data

    def test_gzip_with_custom_compression_level(self) -> None:
        """Test gzip compression with a custom compression level."""
        test_data = "Hello, world!"
        test_path = "test_file.txt"

        default_compressed = compress.gzip(test_data, path=test_path)

        max_compressed = compress.gzip(test_data, path=test_path, compresslevel=9)

        assert isinstance(default_compressed, bytes)
        assert isinstance(max_compressed, bytes)

        gzip_buffer1 = BytesIO(default_compressed)
        decompressed1 = GzipFile(None, "rb", fileobj=gzip_buffer1).read().decode()
        assert decompressed1 == test_data

        gzip_buffer2 = BytesIO(max_compressed)
        decompressed2 = GzipFile(None, "rb", fileobj=gzip_buffer2).read().decode()
        assert decompressed2 == test_data

    def test_brotli_with_string_input(self) -> None:
        """Test brotli compression with string input."""
        test_data = "Hello, world!"

        compressed = compress.brotli(test_data)

        assert isinstance(compressed, bytes)

        decompressed = brotli.decompress(compressed).decode()
        assert decompressed == test_data

    def test_brotli_with_bytes_input(self) -> None:
        """Test brotli compression with bytes input."""
        test_data = b"Hello, world!"

        compressed = compress.brotli(test_data)

        assert isinstance(compressed, bytes)

        decompressed = brotli.decompress(compressed)
        assert decompressed == test_data

    def test_brotli_with_custom_quality_level(self) -> None:
        """Test brotli compression with a custom quality level."""
        test_data = "Hello, world! " * 100

        default_compressed = compress.brotli(test_data)

        max_compressed = compress.brotli(test_data, level=11)

        min_compressed = compress.brotli(test_data, level=0)

        assert isinstance(default_compressed, bytes)
        assert isinstance(max_compressed, bytes)
        assert isinstance(min_compressed, bytes)

        assert brotli.decompress(default_compressed).decode() == test_data
        assert brotli.decompress(max_compressed).decode() == test_data
        assert brotli.decompress(min_compressed).decode() == test_data

    def test_large_data_compression(self) -> None:
        """Test compression of large data."""
        test_data = "The quick brown fox jumps over the lazy dog. " * 1000

        gzip_compressed = compress.gzip(test_data, path="large_file.txt")
        assert isinstance(gzip_compressed, bytes)

        brotli_compressed = compress.brotli(test_data)
        assert isinstance(brotli_compressed, bytes)

        gzip_buffer = BytesIO(gzip_compressed)
        gzip_decompressed = GzipFile(None, "rb", fileobj=gzip_buffer).read().decode()
        assert gzip_decompressed == test_data

        brotli_decompressed = brotli.decompress(brotli_compressed).decode()
        assert brotli_decompressed == test_data


class TestDecompress:
    """Tests for the Decompress class."""

    def test_decompress_is_singleton_instance(self) -> None:
        """Test that decompress is a singleton instance of Decompress."""
        assert isinstance(decompress, Decompress)

    def test_gzip_decompression(self) -> None:
        """Test gzip decompression."""
        test_data = "Hello, world!"

        gzip_buffer = BytesIO()
        with GzipFile(None, "wb", fileobj=gzip_buffer) as gz:
            gz.write(test_data.encode())
        compressed = gzip_buffer.getvalue()

        decompressed = decompress.gzip(compressed)

        assert decompressed == test_data

    def test_gzip_decompression_with_compress_output(self) -> None:
        """Test decompressing data that was compressed with the Compress class."""
        test_data = "Hello, world!"

        compressed = compress.gzip(test_data, path="test_file.txt")

        decompressed = decompress.gzip(compressed)

        assert decompressed == test_data

    def test_brotli_decompression(self) -> None:
        """Test brotli decompression."""
        test_data = "Hello, world!"

        compressed = brotli.compress(test_data.encode())

        decompressed = decompress.brotli(compressed)

        assert decompressed == test_data.encode()

    def test_brotli_decompression_with_compress_output(self) -> None:
        """Test decompressing data that was compressed with the Compress class."""
        test_data = "Hello, world!"

        compressed = compress.brotli(test_data)

        decompressed = decompress.brotli(compressed)

        assert decompressed == test_data.encode()

    def test_roundtrip_gzip(self) -> None:
        """Test a complete compress/decompress cycle with gzip."""
        test_data = "Hello, world! 123 !@"

        compressed = compress.gzip(test_data, path="test_file.txt")

        decompressed = decompress.gzip(compressed)

        assert decompressed == test_data

    def test_roundtrip_brotli(self) -> None:
        """Test a complete compress/decompress cycle with brotli."""
        test_data = "Hello, world! 123 !@"

        compressed = compress.brotli(test_data)

        decompressed = decompress.brotli(compressed)

        assert decompressed == test_data.encode()


class TestErrorCases:
    """Tests for error cases in compression/decompression."""

    def test_invalid_gzip_data(self) -> None:
        """Test decompressing invalid gzip data."""
        invalid_data = b"This is not valid gzip data"

        with pytest.raises(Exception):
            decompress.gzip(invalid_data)

    def test_invalid_brotli_data(self) -> None:
        """Test decompressing invalid brotli data."""
        invalid_data = b"This is not valid brotli data"

        with pytest.raises(Exception):
            decompress.brotli(invalid_data)

    def test_invalid_brotli_quality(self) -> None:
        """Test compressing with invalid brotli quality level."""
        test_data = "Hello, world!"

        with pytest.raises(Exception):
            compress.brotli(test_data, level=12)

    def test_invalid_gzip_level(self) -> None:
        """Test compressing with invalid gzip compression level."""
        test_data = "Hello, world!"

        with pytest.raises(Exception):
            compress.gzip(test_data, compresslevel=10)

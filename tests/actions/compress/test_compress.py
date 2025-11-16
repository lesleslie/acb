"""Tests for compression functionality."""

import gzip
import tempfile
from pathlib import Path
from unittest.mock import patch

import brotli
import pytest

from acb.actions.compress import compress

TEST_STRING: str = "This is a test string to compress."
TEST_BYTES: bytes = b"This is a test string to compress."
LARGE_TEST_STRING: str = "A" * 10000


@pytest.mark.unit
@pytest.mark.parametrize("data", [TEST_STRING, TEST_BYTES])
def test_gzip_compress_string_bytes(data: str | bytes) -> None:
    """Test gzip compression with string and bytes inputs."""
    result = compress.gzip(data)
    assert result is not None, "Compression should return a result"
    assert isinstance(result, bytes), "Compressed result must be bytes"
    decompressed: bytes = gzip.decompress(result)
    if isinstance(data, str):
        data = data.encode()
    assert decompressed == data, "Round-trip decompression should match original data"


@pytest.mark.unit
def test_gzip_compress_file(tmp_path: Path) -> None:
    """Test gzip compression from file path."""
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result = compress.gzip(str(file_path))
    assert result is not None, "File compression should return a result"
    assert isinstance(result, bytes), "Compressed result must be bytes"
    decompressed: bytes = gzip.decompress(result)
    assert decompressed == TEST_STRING.encode(), (
        "Decompressed content should match file content"
    )


@pytest.mark.unit
def test_gzip_compression_levels() -> None:
    """Test gzip compression with different compression levels."""
    test_data = "A" * 1000
    result = compress.gzip(test_data, compresslevel=9)
    assert result is not None, "Compression with level 9 should return a result"
    assert isinstance(result, bytes), "Compressed result must be bytes"
    decompressed: bytes = gzip.decompress(result)
    assert decompressed == test_data.encode(), "Decompressed data should match original"


@pytest.mark.unit
def test_gzip_with_path_output(tmp_path: Path) -> None:
    """Test gzip compression with output path."""
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    output_path: Path = tmp_path / "output.gz"
    result = compress.gzip(str(file_path), str(output_path))
    assert result is None, "Should return None when writing to output file"
    assert output_path.exists(), "Output file should be created"
    decompressed: bytes = gzip.decompress(output_path.read_bytes())
    assert decompressed == TEST_STRING.encode(), (
        "Output file content should decompress correctly"
    )


@pytest.mark.unit
def test_gzip_invalid_input() -> None:
    """Test gzip compression with nonexistent file path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        nonexistent_file = Path(temp_dir) / "nonexistent_file.txt"
        with pytest.raises(FileNotFoundError):
            compress.gzip(str(nonexistent_file))


@pytest.mark.unit
def test_gzip_pathlib_path(tmp_path: Path) -> None:
    """Test gzip compression with pathlib.Path object."""
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result = compress.gzip(file_path)
    assert result is not None, "Compression should return a result"
    assert isinstance(result, bytes), "Compressed result must be bytes"
    decompressed: bytes = gzip.decompress(result)
    assert decompressed == TEST_STRING.encode(), (
        "Path-based compression should decompress correctly"
    )


@pytest.mark.unit
def test_gzip_with_mock(tmp_path: Path) -> None:
    """Test gzip compression with mocked implementation."""
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    with patch("acb.actions.compress.compress.gzip", return_value=b"mocked"):
        result = compress.gzip(file_path.read_text())
        assert result == b"mocked", "Mock should override real compression"


@pytest.mark.unit
def test_gzip_compression_level_comparison() -> None:
    """Test gzip compression level comparison (level 1 vs 9)."""
    test_data = "A" * 1000

    result1 = compress.gzip(test_data, compresslevel=1)
    result9 = compress.gzip(test_data, compresslevel=9)

    assert result1 is not None, "Level 1 compression should return a result"
    assert result9 is not None, "Level 9 compression should return a result"
    assert len(result9) <= len(result1), (
        "Higher compression level should produce smaller or equal size"
    )

    assert gzip.decompress(result1).decode() == test_data, (
        "Level 1 decompression should match original"
    )
    assert gzip.decompress(result9).decode() == test_data, (
        "Level 9 decompression should match original"
    )


@pytest.mark.unit
@pytest.mark.parametrize("data", [TEST_STRING, TEST_BYTES])
def test_brotli_compress_string_bytes(data: str | bytes) -> None:
    """Test brotli compression with string and bytes inputs."""
    result: bytes = compress.brotli(data)
    assert isinstance(result, bytes), "Compressed result must be bytes"
    decompressed: bytes = brotli.decompress(result)
    if isinstance(data, str):
        data = data.encode()
    assert decompressed == data, (
        "Round-trip brotli decompression should match original data"
    )


@pytest.mark.unit
def test_brotli_compress_file(tmp_path: Path) -> None:
    """Test brotli compression from file path."""
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result: bytes = compress.brotli(str(file_path))
    assert isinstance(result, bytes), "Compressed result must be bytes"
    decompressed: bytes = brotli.decompress(result)
    assert decompressed == TEST_STRING.encode(), (
        "Decompressed content should match file content"
    )


@pytest.mark.unit
def test_brotli_compression_levels() -> None:
    """Test brotli compression with maximum compression level."""
    test_data = "A" * 1000
    result: bytes = compress.brotli(test_data, 11)
    assert isinstance(result, bytes), "Compressed result must be bytes"
    decompressed: bytes = brotli.decompress(result)
    assert decompressed == test_data.encode(), "Decompressed data should match original"


@pytest.mark.unit
def test_brotli_with_path_output(tmp_path: Path) -> None:
    """Test brotli compression with output to file."""
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    output_path: Path = tmp_path / "output.br"
    compressed: bytes = compress.brotli(str(file_path), 5)
    output_path.write_bytes(compressed)
    assert output_path.exists(), "Output file should be created"
    decompressed: bytes = brotli.decompress(output_path.read_bytes())
    assert decompressed == TEST_STRING.encode(), (
        "Output file content should decompress correctly"
    )


@pytest.mark.unit
def test_brotli_invalid_input() -> None:
    """Test brotli compression with nonexistent file path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        nonexistent_file = Path(temp_dir) / "nonexistent_file.txt"
        with pytest.raises(FileNotFoundError):
            compress.brotli(str(nonexistent_file))


@pytest.mark.unit
def test_brotli_pathlib_path(tmp_path: Path) -> None:
    """Test brotli compression with pathlib.Path object."""
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result: bytes = compress.brotli(file_path)
    assert isinstance(result, bytes), "Compressed result must be bytes"
    decompressed: bytes = brotli.decompress(result)
    assert decompressed == TEST_STRING.encode(), (
        "Path-based compression should decompress correctly"
    )


@pytest.mark.unit
def test_brotli_with_mock(tmp_path: Path) -> None:
    """Test brotli compression with mocked implementation."""
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    with patch("acb.actions.compress.compress.brotli", return_value=b"mocked"):
        result: bytes = compress.brotli(file_path.read_text())
        assert result == b"mocked", "Mock should override real compression"


@pytest.mark.unit
def test_brotli_compression_level_comparison() -> None:
    """Test brotli compression level comparison (level 1 vs 11)."""
    test_data = "A" * 1000

    result1: bytes = compress.brotli(test_data, 1)
    result11: bytes = compress.brotli(test_data, 11)

    assert len(result11) <= len(result1), (
        "Higher compression level should produce smaller or equal size"
    )
    assert brotli.decompress(result1).decode() == test_data, (
        "Level 1 decompression should match original"
    )
    assert brotli.decompress(result11).decode() == test_data, (
        "Level 11 decompression should match original"
    )


@pytest.mark.unit
def test_normalize_input_with_path_object(tmp_path: Path) -> None:
    """Test that _normalize_input correctly handles Path objects."""
    file_path: Path = tmp_path / "test.txt"
    file_path.write_text("test content")

    # Test with Path object for gzip
    result = compress.gzip(file_path)
    assert isinstance(result, bytes), "Should handle Path objects"
    assert gzip.decompress(result).decode() == "test content"

    # Test with Path object for brotli
    result_br: bytes = compress.brotli(file_path)
    assert isinstance(result_br, bytes), "Should handle Path objects"
    assert brotli.decompress(result_br).decode() == "test content"


@pytest.mark.unit
def test_compress_with_special_characters_in_path(tmp_path: Path) -> None:
    """Test compression with special characters in file path."""
    file_path: Path = tmp_path / "test file with spaces.txt"
    file_path.write_text("content with spaces")

    result = compress.gzip(file_path)
    assert isinstance(result, bytes)
    assert gzip.decompress(result).decode() == "content with spaces"

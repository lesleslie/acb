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


@pytest.mark.parametrize("data", [TEST_STRING, TEST_BYTES])
def test_gzip_compress_string_bytes(data: str | bytes) -> None:
    result = compress.gzip(data)
    assert result is not None
    assert isinstance(result, bytes)
    decompressed: bytes = gzip.decompress(result)
    if isinstance(data, str):
        data = data.encode()
    assert decompressed == data


def test_gzip_compress_file(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result = compress.gzip(str(file_path))
    assert result is not None
    assert isinstance(result, bytes)
    decompressed: bytes = gzip.decompress(result)
    assert decompressed == TEST_STRING.encode()


def test_gzip_compression_levels() -> None:
    test_data = "A" * 1000
    result = compress.gzip(test_data, compresslevel=9)
    assert result is not None
    assert isinstance(result, bytes)
    decompressed: bytes = gzip.decompress(result)
    assert decompressed == test_data.encode()


def test_gzip_with_path_output(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    output_path: Path = tmp_path / "output.gz"
    result = compress.gzip(str(file_path), str(output_path))
    assert result is None
    assert output_path.exists()
    decompressed: bytes = gzip.decompress(output_path.read_bytes())
    assert decompressed == TEST_STRING.encode()


def test_gzip_invalid_input() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        nonexistent_file = Path(temp_dir) / "nonexistent_file.txt"
        with pytest.raises(FileNotFoundError):
            compress.gzip(str(nonexistent_file))


def test_gzip_pathlib_path(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result = compress.gzip(file_path)
    assert result is not None
    assert isinstance(result, bytes)
    decompressed: bytes = gzip.decompress(result)
    assert decompressed == TEST_STRING.encode()


def test_gzip_with_mock(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    with patch("acb.actions.compress.compress.gzip", return_value=b"mocked"):
        result = compress.gzip(file_path.read_text())
        assert result == b"mocked"


def test_gzip_compression_level_comparison() -> None:
    test_data = "A" * 1000

    result1 = compress.gzip(test_data, compresslevel=1)
    result9 = compress.gzip(test_data, compresslevel=9)

    assert result1 is not None
    assert result9 is not None

    assert gzip.decompress(result1).decode() == test_data
    assert gzip.decompress(result9).decode() == test_data


@pytest.mark.parametrize("data", [TEST_STRING, TEST_BYTES])
def test_brotli_compress_string_bytes(data: str | bytes) -> None:
    result: bytes = compress.brotli(data)
    assert isinstance(result, bytes)
    decompressed: bytes = brotli.decompress(result)
    if isinstance(data, str):
        data = data.encode()
    assert decompressed == data


def test_brotli_compress_file(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result: bytes = compress.brotli(str(file_path))
    assert isinstance(result, bytes)
    decompressed: bytes = brotli.decompress(result)
    assert decompressed == TEST_STRING.encode()


def test_brotli_compression_levels() -> None:
    test_data = "A" * 1000
    result: bytes = compress.brotli(test_data, 11)
    assert isinstance(result, bytes)
    decompressed: bytes = brotli.decompress(result)
    assert decompressed == test_data.encode()


def test_brotli_with_path_output(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    output_path: Path = tmp_path / "output.br"
    compressed: bytes = compress.brotli(str(file_path), 5)
    output_path.write_bytes(compressed)
    assert output_path.exists()
    decompressed: bytes = brotli.decompress(output_path.read_bytes())
    assert decompressed == TEST_STRING.encode()


def test_brotli_invalid_input() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        nonexistent_file = Path(temp_dir) / "nonexistent_file.txt"
        with pytest.raises(FileNotFoundError):
            compress.brotli(str(nonexistent_file))


def test_brotli_pathlib_path(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result: bytes = compress.brotli(file_path)
    assert isinstance(result, bytes)
    decompressed: bytes = brotli.decompress(result)
    assert decompressed == TEST_STRING.encode()


def test_brotli_with_mock(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    with patch("acb.actions.compress.compress.brotli", return_value=b"mocked"):
        result: bytes = compress.brotli(file_path.read_text())
        assert result == b"mocked"


def test_brotli_compression_level_comparison() -> None:
    test_data = "A" * 1000

    result1: bytes = compress.brotli(test_data, 1)
    result11: bytes = compress.brotli(test_data, 11)

    assert brotli.decompress(result1).decode() == test_data
    assert brotli.decompress(result11).decode() == test_data

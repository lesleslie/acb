"""Tests for compression functionality."""

import gzip
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
    result: bytes = compress.gzip(data)
    assert isinstance(result, bytes)
    decompressed: bytes = gzip.decompress(result)
    if isinstance(data, str):
        data = data.encode()
    assert decompressed == data


def test_gzip_compress_file(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result: bytes = compress.gzip(file_path.read_text())
    assert isinstance(result, bytes)
    decompressed: bytes = gzip.decompress(result)
    assert decompressed == TEST_STRING.encode()


def test_gzip_compression_levels(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "large_test_file.txt"
    file_path.write_text(LARGE_TEST_STRING)
    result: bytes = compress.gzip(file_path.read_text(), compresslevel=9)
    assert isinstance(result, bytes)
    decompressed: bytes = gzip.decompress(result)
    assert decompressed == LARGE_TEST_STRING.encode()


def test_gzip_with_path_output(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    output_path: Path = tmp_path / "output.gz"
    compress.gzip(file_path.read_text(), output_path)
    assert output_path.exists()
    decompressed: bytes = gzip.decompress(output_path.read_bytes())
    assert decompressed == TEST_STRING.encode()


def test_gzip_invalid_input() -> None:
    with pytest.raises(FileNotFoundError):
        compress.gzip("/nonexistent/file.txt")


def test_gzip_pathlib_path(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result: bytes = compress.gzip(file_path.read_text())
    assert isinstance(result, bytes)
    decompressed: bytes = gzip.decompress(result)
    assert decompressed == TEST_STRING.encode()


def test_gzip_with_mock(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    with patch("acb.actions.compress.gzip", return_value=b"mocked"):
        result: bytes = compress.gzip(file_path.read_text())
        assert result == b"mocked"


def test_gzip_compression_level_comparison(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "large_test_file.txt"
    file_path.write_text(LARGE_TEST_STRING)
    result1: bytes = compress.gzip(file_path.read_text(), compresslevel=1)
    result9: bytes = compress.gzip(file_path.read_text(), compresslevel=9)
    assert len(result9) < len(result1)


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
    result: bytes = compress.brotli(file_path.read_text())
    assert isinstance(result, bytes)
    decompressed: bytes = brotli.decompress(result)
    assert decompressed == TEST_STRING.encode()


def test_brotli_compression_levels(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "large_test_file.txt"
    file_path.write_text(LARGE_TEST_STRING)
    result: bytes = compress.brotli(file_path.read_text(), 11)
    assert isinstance(result, bytes)
    decompressed: bytes = brotli.decompress(result)
    assert decompressed == LARGE_TEST_STRING.encode()


def test_brotli_with_path_output(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    output_path: Path = tmp_path / "output.br"
    compressed = compress.brotli(TEST_STRING, 5)
    output_path.write_bytes(compressed)
    assert output_path.exists()
    decompressed: bytes = brotli.decompress(output_path.read_bytes())
    assert decompressed == TEST_STRING.encode()


def test_brotli_invalid_input() -> None:
    with pytest.raises(FileNotFoundError):
        compress.brotli("/nonexistent/file.txt")


def test_brotli_pathlib_path(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    result: bytes = compress.brotli(file_path.read_text())
    assert isinstance(result, bytes)
    decompressed: bytes = brotli.decompress(result)
    assert decompressed == TEST_STRING.encode()


def test_brotli_with_mock(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "test_file.txt"
    file_path.write_text(TEST_STRING)
    with patch("acb.actions.compress.brotli", return_value=b"mocked"):
        result: bytes = compress.brotli(file_path.read_text())
        assert result == b"mocked"


def test_brotli_compression_level_comparison(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "large_test_file.txt"
    file_path.write_text(LARGE_TEST_STRING)
    result1: bytes = compress.brotli(file_path.read_text(), 1)
    result11: bytes = compress.brotli(file_path.read_text(), 11)
    assert len(result11) < len(result1)

import gzip
from pathlib import Path
from unittest.mock import patch

import brotli
import pytest
from acb.actions.compress import decompress

TEST_STRING: str = "This is a test string to decompress."
TEST_BYTES: bytes = b"This is a test string to decompress."
LARGE_TEST_STRING: str = "A" * 10000


@pytest.fixture
def compressed_bytes() -> bytes:
    return gzip.compress(TEST_BYTES)


@pytest.fixture
def tmp_gzip_file(tmp_path: Path) -> Path:
    file_path: Path = tmp_path / "test_file.gz"
    file_path.write_bytes(gzip.compress(TEST_BYTES))
    return file_path


@pytest.fixture
def tmp_brotli_file(tmp_path: Path) -> Path:
    file_path: Path = tmp_path / "test_file.br"
    file_path.write_bytes(brotli.compress(TEST_BYTES))
    return file_path


def test_gzip_decompress_bytes(compressed_bytes: bytes) -> None:
    result: str = decompress.gzip(compressed_bytes)
    assert isinstance(result, str)
    assert result == TEST_BYTES.decode()


def test_gzip_decompress_file(tmp_gzip_file: Path) -> None:
    result: str = decompress.gzip(tmp_gzip_file.read_bytes())
    assert isinstance(result, str)
    assert result == TEST_BYTES.decode()


def test_gzip_decompress_with_path_output(tmp_path: Path, tmp_gzip_file: Path) -> None:
    output_path: Path = tmp_path / "decompressed.txt"
    result: str = decompress.gzip(tmp_gzip_file.read_bytes())
    output_path.write_text(result)
    assert output_path.exists()
    assert output_path.read_text() == TEST_BYTES.decode()


def test_gzip_decompress_nonexistent_file(tmp_path: Path) -> None:
    nonexistent_file = tmp_path / "nonexistent_file.gz"
    with pytest.raises(FileNotFoundError):
        decompress.gzip(nonexistent_file)


def test_gzip_decompress_pathlib_path(tmp_gzip_file: Path) -> None:
    result: str = decompress.gzip(tmp_gzip_file.read_bytes())
    assert isinstance(result, str)
    assert result == TEST_BYTES.decode()


def test_gzip_decompress_async_path(tmp_gzip_file: Path) -> None:
    from anyio import Path as AsyncPath

    AsyncPath(str(tmp_gzip_file))
    result: str = decompress.gzip(tmp_gzip_file.read_bytes())
    assert isinstance(result, str)
    assert result == TEST_BYTES.decode()


def test_gzip_decompress_with_mock(tmp_gzip_file: Path) -> None:
    with patch(
        "acb.actions.compress.Decompress.gzip",
        return_value=TEST_BYTES.decode(),
    ):
        result: str = decompress.gzip(tmp_gzip_file.read_bytes())
        assert result == TEST_BYTES.decode()


def test_gzip_decompress_bad_file(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "not_a_gzip.gz"
    file_path.write_bytes(b"not really gzip")
    with pytest.raises(OSError):
        decompress.gzip(file_path.read_bytes())


def test_brotli_decompress_bytes(tmp_brotli_file: Path) -> None:
    result: str = decompress.brotli(tmp_brotli_file.read_bytes())
    assert isinstance(result, str)
    assert result == TEST_BYTES.decode()

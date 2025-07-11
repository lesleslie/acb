"""Tests for hashing functionality."""

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final
from unittest.mock import MagicMock, patch
from warnings import catch_warnings

import blake3
import pytest
from anyio import Path as AsyncPath
from pytest_benchmark.fixture import BenchmarkFixture
from acb.actions.hash import hash

with catch_warnings(action="ignore", category=RuntimeWarning):
    from google_crc32c import value as crc32c

TEST_STRING: Final[str] = "This is a test string to hash."
TEST_BYTES: Final[bytes] = b"This is a test string to hash."
TEST_NON_ASCII: Final[str] = "Test string with non-ASCII: éñçödîñg"


class TestHash:
    @pytest.fixture
    def async_tmp_path(self, tmp_path: Path) -> AsyncPath:
        return AsyncPath(tmp_path)

    @pytest.fixture
    async def test_file(self, async_tmp_path: AsyncPath) -> AsyncPath:
        file_path = async_tmp_path / "test_file.txt"
        await file_path.write_text(TEST_STRING)
        return file_path

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("hash_func", "expected_func"),
        [
            (hash.blake3, lambda data: blake3.blake3(data).hexdigest()),
            (
                hash.md5,
                lambda data: hashlib.md5(data, usedforsecurity=False).hexdigest(),
            ),
            (hash.crc32c, lambda data: f"{crc32c(data):08x}"),
        ],
    )
    async def test_hash_string(
        self,
        hash_func: Callable[[Any], Any],
        expected_func: Callable[[bytes], str],
    ) -> None:
        result = await hash_func(TEST_STRING)

        assert isinstance(result, str)

        expected = expected_func(TEST_STRING.encode())
        assert result == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("hash_func", "expected_func"),
        [
            (hash.blake3, lambda data: blake3.blake3(data).hexdigest()),
            (
                hash.md5,
                lambda data: hashlib.md5(data, usedforsecurity=False).hexdigest(),
            ),
            (hash.crc32c, lambda data: f"{crc32c(data):08x}"),
        ],
    )
    async def test_hash_bytes(
        self,
        hash_func: Callable[[Any], Any],
        expected_func: Callable[[bytes], str],
    ) -> None:
        result = await hash_func(TEST_BYTES)

        assert isinstance(result, str)

        expected = expected_func(TEST_BYTES)
        assert result == expected

    @pytest.mark.asyncio
    async def test_blake3_string(self) -> None:
        result = await hash.blake3(TEST_STRING)

        assert isinstance(result, str)

        expected = blake3.blake3(TEST_STRING.encode()).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    async def test_blake3_bytes(self) -> None:
        result = await hash.blake3(TEST_BYTES)

        assert isinstance(result, str)

        expected = blake3.blake3(TEST_BYTES).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("hash_func", "expected_func"),
        [
            (hash.blake3, lambda data: blake3.blake3(data).hexdigest()),
            (
                hash.md5,
                lambda data: hashlib.md5(data, usedforsecurity=False).hexdigest(),
            ),
            (hash.crc32c, lambda data: f"{crc32c(data):08x}"),
        ],
    )
    async def test_hash_file(
        self,
        hash_func: Callable[[Any], Any],
        expected_func: Callable[[bytes], str],
        test_file: AsyncPath,
    ) -> None:
        result = await hash_func(str(test_file))

        assert isinstance(result, str)

        expected = expected_func(TEST_STRING.encode())
        assert result == expected

    @pytest.mark.asyncio
    async def test_blake3_file(self, test_file: AsyncPath) -> None:
        result = await hash.blake3(str(test_file))

        assert isinstance(result, str)

        expected = blake3.blake3(TEST_STRING.encode()).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    async def test_crc32c_string(self) -> None:
        result = await hash.crc32c(TEST_STRING)

        assert isinstance(result, str)

        expected = f"{crc32c(TEST_STRING.encode()):08x}"
        assert result == expected

    @pytest.mark.asyncio
    async def test_crc32c_bytes(self) -> None:
        result = await hash.crc32c(TEST_BYTES)

        assert isinstance(result, str)

        expected = f"{crc32c(TEST_BYTES):08x}"
        assert result == expected

    @pytest.mark.asyncio
    async def test_crc32c_file(self, test_file: AsyncPath) -> None:
        result = await hash.crc32c(str(test_file))

        assert isinstance(result, str)

        expected = f"{crc32c(TEST_STRING.encode()):08x}"
        assert result == expected

    @pytest.mark.asyncio
    async def test_md5_string(self) -> None:
        result = await hash.md5(TEST_STRING)

        assert isinstance(result, str)

        expected = hashlib.md5(TEST_STRING.encode(), usedforsecurity=False).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    async def test_md5_bytes(self) -> None:
        result = await hash.md5(TEST_BYTES)

        assert isinstance(result, str)

        expected = hashlib.md5(TEST_BYTES, usedforsecurity=False).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    async def test_md5_file(self, test_file: AsyncPath) -> None:
        result = await hash.md5(str(test_file))

        assert isinstance(result, str)

        expected = hashlib.md5(TEST_STRING.encode(), usedforsecurity=False).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("hash_func", "exception_type"),
        [
            (hash.blake3, TypeError),
            (hash.md5, TypeError),
            (hash.crc32c, TypeError),
        ],
    )
    async def test_hash_invalid_input(
        self,
        hash_func: Callable[[Any], Any],
        exception_type: "type[Exception]",
    ) -> None:
        with pytest.raises(exception_type):
            await hash_func(None)  # type: ignore

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "hash_func",
        [
            hash.blake3,
            hash.md5,
            hash.crc32c,
        ],
    )
    async def test_hash_nonexistent_file(self, hash_func: Callable[[Any], Any]) -> None:
        with pytest.raises(FileNotFoundError):
            await hash_func("/nonexistent/file/path.txt")

    @pytest.mark.asyncio
    async def test_hash_with_mock(self) -> None:
        with patch("acb.actions.hash.blake3") as mock_blake3:
            mock_hasher = MagicMock()
            mock_hasher.hexdigest.return_value = "mocked_blake3_hash"
            mock_blake3.return_value = mock_hasher

            result = await hash.blake3(TEST_STRING)

            assert result == "mocked_blake3_hash"
            mock_blake3.assert_called_once_with(TEST_STRING.encode())

    @pytest.mark.asyncio
    async def test_blake3_pathlib_path(self, async_tmp_path: AsyncPath) -> None:
        test_file = async_tmp_path / "test_file.txt"
        await test_file.write_text(TEST_STRING)
        path_obj = Path(test_file)

        result = await hash.blake3(path_obj)

        assert isinstance(result, str)

        expected = blake3.blake3(TEST_STRING.encode()).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    async def test_crc32c_pathlib_path(self, async_tmp_path: AsyncPath) -> None:
        test_file = async_tmp_path / "test_file.txt"
        await test_file.write_text(TEST_STRING)
        path_obj = Path(test_file)

        result = await hash.crc32c(path_obj)

        assert isinstance(result, str)

        expected = f"{crc32c(TEST_STRING.encode()):08x}"
        assert result == expected

    @pytest.mark.asyncio
    async def test_md5_pathlib_path(self, async_tmp_path: AsyncPath) -> None:
        test_file = async_tmp_path / "test_file.txt"
        await test_file.write_text(TEST_STRING)
        path_obj = Path(test_file)

        result = await hash.md5(path_obj)

        assert isinstance(result, str)

        expected = hashlib.md5(TEST_STRING.encode(), usedforsecurity=False).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    async def test_blake3_async_path(self, test_file: AsyncPath) -> None:
        result = await hash.blake3(test_file)

        assert isinstance(result, str)

        expected = blake3.blake3(TEST_STRING.encode()).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    async def test_blake3_list(self) -> None:
        test_list = ["item1", "item2", "item3"]
        result = await hash.blake3(test_list)

        assert isinstance(result, str)

        expected = blake3.blake3("".join(test_list.copy()).encode()).hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    async def test_crc32c_async_path(self, test_file: AsyncPath) -> None:
        result = await hash.crc32c(test_file)

        assert isinstance(result, str)

        expected = f"{crc32c(TEST_STRING.encode()):08x}"
        assert result == expected

    @pytest.mark.asyncio
    async def test_md5_with_ascii_parameter(self) -> None:
        result1 = await hash.md5(TEST_NON_ASCII)
        expected1 = hashlib.md5(
            TEST_NON_ASCII.encode(),
            usedforsecurity=False,
        ).hexdigest()
        assert result1 == expected1

        result2 = await hash.md5(TEST_NON_ASCII.encode("ascii", errors="replace"))
        expected2 = hashlib.md5(
            TEST_NON_ASCII.encode("ascii", errors="replace"),
            usedforsecurity=False,
        ).hexdigest()
        assert result2 == expected2

        assert result1 != result2

    @pytest.mark.asyncio
    async def test_md5_with_usedforsecurity_parameter(self) -> None:
        result1 = await hash.md5(TEST_STRING)
        expected1 = hashlib.md5(TEST_STRING.encode(), usedforsecurity=False).hexdigest()
        assert result1 == expected1

        result2 = await hash.md5(TEST_STRING)
        expected2 = hashlib.md5(TEST_STRING.encode(), usedforsecurity=False).hexdigest()
        assert result2 == expected2

        assert result1 == result2


class TestHashBenchmarks:
    @pytest.fixture
    def async_tmp_path(self, tmp_path: Path) -> AsyncPath:
        return AsyncPath(tmp_path)

    @pytest.fixture
    def large_text_data(self) -> str:
        return "large text data for performance testing" * 1000

    @pytest.fixture
    def large_binary_data(self) -> bytes:
        return b"large binary data for performance testing" * 1000

    @pytest.fixture
    async def large_test_file(self, async_tmp_path: AsyncPath) -> AsyncPath:
        file_path = async_tmp_path / "large_test_file.txt"
        large_content = "large file content for performance testing\n" * 1000
        await file_path.write_text(large_content)
        return file_path

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_blake3_large_text_performance(
        self,
        benchmark: BenchmarkFixture,
        large_text_data: str,
    ) -> None:
        result = await benchmark(hash.blake3, large_text_data)
        assert isinstance(result, str)
        assert len(result) == 64

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_blake3_large_binary_performance(
        self,
        benchmark: BenchmarkFixture,
        large_binary_data: bytes,
    ) -> None:
        result = await benchmark(hash.blake3, large_binary_data)
        assert isinstance(result, str)
        assert len(result) == 64

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_blake3_large_file_performance(
        self,
        benchmark: BenchmarkFixture,
        large_test_file: AsyncPath,
    ) -> None:
        result = await benchmark(hash.blake3, str(large_test_file))
        assert isinstance(result, str)
        assert len(result) == 64

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_crc32c_large_text_performance(
        self,
        benchmark: BenchmarkFixture,
        large_text_data: str,
    ) -> None:
        result = await benchmark(hash.crc32c, large_text_data)
        assert isinstance(result, str)
        assert len(result) == 8

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_crc32c_large_binary_performance(
        self,
        benchmark: BenchmarkFixture,
        large_binary_data: bytes,
    ) -> None:
        result = await benchmark(hash.crc32c, large_binary_data)
        assert isinstance(result, str)
        assert len(result) == 8

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_crc32c_large_file_performance(
        self,
        benchmark: BenchmarkFixture,
        large_test_file: AsyncPath,
    ) -> None:
        result = await benchmark(hash.crc32c, str(large_test_file))
        assert isinstance(result, str)
        assert len(result) == 8

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_md5_large_text_performance(
        self,
        benchmark: BenchmarkFixture,
        large_text_data: str,
    ) -> None:
        result = await benchmark(hash.md5, large_text_data)
        assert isinstance(result, str)
        assert len(result) == 32

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_md5_large_binary_performance(
        self,
        benchmark: BenchmarkFixture,
        large_binary_data: bytes,
    ) -> None:
        result = await benchmark(hash.md5, large_binary_data)
        assert isinstance(result, str)
        assert len(result) == 32

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_md5_large_file_performance(
        self,
        benchmark: BenchmarkFixture,
        large_test_file: AsyncPath,
    ) -> None:
        result = await benchmark(hash.md5, str(large_test_file))
        assert isinstance(result, str)
        assert len(result) == 32

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_hash_algorithms_comparison_performance(
        self,
        benchmark: BenchmarkFixture,
        large_text_data: str,
    ) -> None:
        async def hash_with_all_algorithms():
            blake3_result = await hash.blake3(large_text_data)
            crc32c_result = await hash.crc32c(large_text_data)
            md5_result = await hash.md5(large_text_data)
            return blake3_result, crc32c_result, md5_result

        results = await benchmark(hash_with_all_algorithms)
        assert len(results) == 3
        assert len(results[0]) == 64  # blake3
        assert len(results[1]) == 8  # crc32c
        assert len(results[2]) == 32  # md5

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_bulk_hash_operations_performance(
        self,
        benchmark: BenchmarkFixture,
    ) -> None:
        test_data = [f"test_data_{i}" for i in range(10)]

        async def bulk_hash_operations() -> list[str]:
            results: list[str] = []
            for data in test_data:
                blake3_result = await hash.blake3(data)
                results.append(blake3_result)
            return results

        results = await benchmark(bulk_hash_operations)
        assert len(results) == 10
        assert all(len(result) == 64 for result in results)

import tempfile
from pathlib import Path

import arrow
import pytest
from aiopath import AsyncPath
from acb.actions.hash import hash


class TestHash:
    @pytest.mark.asyncio
    async def test_blake3_with_string(self) -> None:
        """Test blake3 with a string input."""
        test_string = "test string"
        result = await hash.blake3(test_string)
        assert isinstance(result, str)
        assert len(result) == 64

    @pytest.mark.asyncio
    async def test_blake3_with_bytes(self) -> None:
        """Test blake3 with bytes input."""
        test_bytes = b"test bytes"
        result = await hash.blake3(test_bytes)
        assert isinstance(result, str)
        assert len(result) == 64

    @pytest.mark.asyncio
    async def test_blake3_with_list(self) -> None:
        """Test blake3 with list of strings input."""
        test_list = ["test", "list", "of", "strings"]
        result = await hash.blake3(test_list)
        assert isinstance(result, str)
        assert len(result) == 64

    @pytest.mark.asyncio
    async def test_blake3_with_path(self) -> None:
        """Test blake3 with Path object."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test file content")
            tmp_path = tmp.name

        try:
            path_obj = Path(tmp_path)
            result = await hash.blake3(path_obj)
            assert isinstance(result, str)
            assert len(result) == 64
        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_blake3_with_async_path(self) -> None:
        """Test blake3 with AsyncPath object."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test file content")
            tmp_path = tmp.name

        try:
            async_path_obj = AsyncPath(tmp_path)
            result = await hash.blake3(async_path_obj)
            assert isinstance(result, str)
            assert len(result) == 64
        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_blake3_with_empty_input(self) -> None:
        """Test blake3 with empty input (should use timestamp)."""
        arrow.utcnow().float_timestamp
        result = await hash.blake3("")
        arrow.utcnow().float_timestamp

        assert isinstance(result, str)
        assert len(result) == 64

        result2 = await hash.blake3("")
        assert result != result2

    @pytest.mark.asyncio
    async def test_crc32c_with_string(self) -> None:
        """Test crc32c with string input."""
        test_string = "test string"
        result = await hash.crc32c(test_string)
        assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_crc32c_with_path(self) -> None:
        """Test crc32c with Path object."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test file content")
            tmp_path = tmp.name

        try:
            path_obj = Path(tmp_path)
            result = await hash.crc32c(path_obj)
            assert isinstance(result, int)
        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_crc32c_with_async_path(self) -> None:
        """Test crc32c with AsyncPath object."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test file content")
            tmp_path = tmp.name

        try:
            async_path_obj = AsyncPath(tmp_path)
            result = await hash.crc32c(async_path_obj)
            assert isinstance(result, int)
        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_md5_with_string(self) -> None:
        """Test md5 with string input."""
        test_string = "test string"
        result = await hash.md5(test_string)
        assert isinstance(result, str)
        assert len(result) == 32

    @pytest.mark.asyncio
    async def test_md5_with_path(self) -> None:
        """Test md5 with Path object."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test file content")
            tmp_path = tmp.name

        try:
            path_obj = Path(tmp_path)
            result = await hash.md5(path_obj)
            assert isinstance(result, str)
            assert len(result) == 32
        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_md5_with_async_path(self) -> None:
        """Test md5 with AsyncPath object."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test file content")
            tmp_path = tmp.name

        try:
            async_path_obj = AsyncPath(tmp_path)
            result = await hash.md5(async_path_obj)
            assert isinstance(result, str)
            assert len(result) == 32
        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_consistency(self) -> None:
        """Test that hash functions return consistent results for the same input."""
        test_string = "consistent test string"

        blake3_result1 = await hash.blake3(test_string)
        blake3_result2 = await hash.blake3(test_string)
        assert blake3_result1 == blake3_result2

        crc32c_result1 = await hash.crc32c(test_string)
        crc32c_result2 = await hash.crc32c(test_string)
        assert crc32c_result1 == crc32c_result2

        md5_result1 = await hash.md5(test_string)
        md5_result2 = await hash.md5(test_string)
        assert md5_result1 == md5_result2

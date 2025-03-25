import hashlib
from pathlib import Path

import arrow
import pytest
from aiopath import AsyncPath
from blake3 import blake3
from google_crc32c import value as crc32c
from acb.actions.hash import Hash


@pytest.fixture
def test_hash() -> Hash:
    return Hash()


@pytest.fixture
async def temp_file(tmp_path: Path) -> AsyncPath:
    file_path = AsyncPath(tmp_path) / "test.txt"
    await file_path.write_text("test content")
    return file_path


class TestHash:
    @pytest.mark.asyncio
    async def test_blake3_with_empty_input(self, test_hash: Hash) -> None:
        timestamp = arrow.utcnow().float_timestamp
        blake3(str(timestamp).encode()).hexdigest()
        result = await test_hash.blake3("")

        assert isinstance(result, str)
        assert len(result) == 64

    @pytest.mark.asyncio
    async def test_blake3_with_string(self, test_hash: Hash) -> None:
        test_string = "test string"
        expected = blake3(test_string.encode()).hexdigest()
        result = await test_hash.blake3(test_string)

        assert result == expected

    @pytest.mark.asyncio
    async def test_blake3_with_bytes(self, test_hash: Hash) -> None:
        test_bytes = b"test bytes"
        expected = blake3(test_bytes).hexdigest()
        result = await test_hash.blake3(test_bytes)

        assert result == expected

    @pytest.mark.asyncio
    async def test_blake3_with_list(self, test_hash: Hash) -> None:
        test_list = ["test", "list", "items"]
        expected = blake3("".join(test_list).encode()).hexdigest()
        result = await test_hash.blake3(test_list)

        assert result == expected

    @pytest.mark.asyncio
    async def test_blake3_with_file(
        self, test_hash: Hash, temp_file: AsyncPath
    ) -> None:
        content = await temp_file.read_bytes()
        expected = blake3(content).hexdigest()
        result = await test_hash.blake3(temp_file)

        assert result == expected

    @pytest.mark.asyncio
    async def test_blake3_with_pathlib_path(
        self, test_hash: Hash, temp_file: AsyncPath
    ) -> None:
        content = await temp_file.read_bytes()
        expected = blake3(content).hexdigest()
        result = await test_hash.blake3(Path(temp_file))

        assert result == expected

    @pytest.mark.asyncio
    async def test_crc32c_with_string(self, test_hash: Hash) -> None:
        test_string = "test string"
        expected = crc32c(test_string.encode())
        result = await test_hash.crc32c(test_string)

        assert result == expected

    @pytest.mark.asyncio
    async def test_crc32c_with_file(
        self, test_hash: Hash, temp_file: AsyncPath
    ) -> None:
        content = await temp_file.read_text()
        expected = crc32c(content.encode())
        result = await test_hash.crc32c(temp_file)

        assert result == expected

    @pytest.mark.asyncio
    async def test_crc32c_with_pathlib_path(
        self, test_hash: Hash, temp_file: AsyncPath
    ) -> None:
        content = await temp_file.read_text()
        expected = crc32c(content.encode())
        result = await test_hash.crc32c(Path(temp_file))

        assert result == expected

    @pytest.mark.asyncio
    async def test_md5_with_string(self, test_hash: Hash) -> None:
        test_string = "test string"
        expected = hashlib.md5(test_string.encode(), usedforsecurity=False).hexdigest()
        result = await test_hash.md5(test_string)

        assert result == expected

    @pytest.mark.asyncio
    async def test_md5_with_file(self, test_hash: Hash, temp_file: AsyncPath) -> None:
        content = await temp_file.read_text()
        expected = hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()
        result = await test_hash.md5(temp_file)

        assert result == expected

    @pytest.mark.asyncio
    async def test_md5_with_pathlib_path(
        self, test_hash: Hash, temp_file: AsyncPath
    ) -> None:
        content = await temp_file.read_text()
        expected = hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()
        result = await test_hash.md5(Path(temp_file))

        assert result == expected

from pathlib import Path

import pytest
from anyio import Path as AsyncPath
from acb.actions.hash import hash


class TestHash:
    @pytest.mark.anyio
    async def test_blake3_hash_bytes(self) -> None:
        data = b"This is a test string to be hashed with blake3."
        hashed_data = await hash.blake3(data)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 64

        hashed_data_again = await hash.blake3(data)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_blake3_hash_string(self) -> None:
        data = "This is a test string to be hashed with blake3."
        hashed_data = await hash.blake3(data)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 64

        hashed_data_again = await hash.blake3(data)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_blake3_hash_path(self, tmp_path: Path) -> None:
        data = b"This is a test string to be hashed with blake3 from a path."
        file_path = tmp_path / "test.txt"
        file_path.write_bytes(data)

        hashed_data = await hash.blake3(file_path)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 64

        hashed_data_again = await hash.blake3(file_path)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_blake3_hash_async_path(self, tmp_path: Path) -> None:
        data = b"This is a test string to be hashed with blake3 from an async path."
        file_path = tmp_path / "test.txt"
        file_path.write_bytes(data)
        async_file_path = AsyncPath(file_path)

        hashed_data = await hash.blake3(async_file_path)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 64

        hashed_data_again = await hash.blake3(async_file_path)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_blake3_hash_list(self) -> None:
        data = ["This", "is", "a", "test", "list"]
        hashed_data = await hash.blake3(data)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 64

        hashed_data_again = await hash.blake3(data)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_blake3_hash_empty(self) -> None:
        hashed_data = await hash.blake3("")
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 64

    @pytest.mark.anyio
    async def test_crc32c_hash_string(self) -> None:
        data = "This is a test string to be hashed with crc32c."
        hashed_data = await hash.crc32c(data)
        assert isinstance(hashed_data, int)
        assert hashed_data > 0

        hashed_data_again = await hash.crc32c(data)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_crc32c_hash_path(self, tmp_path: Path) -> None:
        data = "This is a test string to be hashed with crc32c from a path."
        file_path = tmp_path / "test.txt"
        file_path.write_text(data)

        hashed_data = await hash.crc32c(file_path)
        assert isinstance(hashed_data, int)
        assert hashed_data > 0

        hashed_data_again = await hash.crc32c(file_path)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_crc32c_hash_async_path(self, tmp_path: Path) -> None:
        data = "This is a test string to be hashed with crc32c from an async path."
        file_path = tmp_path / "test.txt"
        file_path.write_text(data)
        async_file_path = AsyncPath(file_path)

        hashed_data = await hash.crc32c(async_file_path)
        assert isinstance(hashed_data, int)
        assert hashed_data > 0

        hashed_data_again = await hash.crc32c(async_file_path)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_md5_hash_string(self) -> None:
        data = "This is a test string to be hashed with md5."
        hashed_data = await hash.md5(data)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 32

        hashed_data_again = await hash.md5(data)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_md5_hash_path(self, tmp_path: Path) -> None:
        data = "This is a test string to be hashed with md5 from a path."
        file_path = tmp_path / "test.txt"
        file_path.write_text(data)

        hashed_data = await hash.md5(file_path)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 32

        hashed_data_again = await hash.md5(file_path)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_md5_hash_async_path(self, tmp_path: Path) -> None:
        data = "This is a test string to be hashed with md5 from an async path."
        file_path = tmp_path / "test.txt"
        file_path.write_text(data)
        async_file_path = AsyncPath(file_path)

        hashed_data = await hash.md5(async_file_path)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 32

        hashed_data_again = await hash.md5(async_file_path)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_md5_hash_ascii(self) -> None:
        data = "This is a test string to be hashed with md5 in ascii."
        hashed_data = await hash.md5(data, ascii=True)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 32

        hashed_data_again = await hash.md5(data, ascii=True)
        assert hashed_data == hashed_data_again

    @pytest.mark.anyio
    async def test_md5_hash_not_usedforsecurity(self) -> None:
        data = "This is a test string to be hashed with md5 not used for security."
        hashed_data = await hash.md5(data, usedforsecurity=False)
        assert isinstance(hashed_data, str)
        assert len(hashed_data) == 32

        hashed_data_again = await hash.md5(data, usedforsecurity=False)
        assert hashed_data == hashed_data_again

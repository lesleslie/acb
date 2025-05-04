import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from blake3 import blake3
from acb.actions.hash import hash


class TestHash:
    @pytest.mark.asyncio
    async def test_blake3_with_string(self) -> None:
        test_string = "test string"
        expected_hash = blake3(test_string.encode()).hexdigest()
        result = await hash.blake3(test_string)
        assert result == expected_hash

    @pytest.mark.asyncio
    async def test_blake3_with_bytes(self) -> None:
        test_bytes = b"test bytes"
        expected_hash = blake3(test_bytes).hexdigest()
        result = await hash.blake3(test_bytes)
        assert result == expected_hash

    @pytest.mark.asyncio
    async def test_blake3_with_file(self, tmp_path: Path) -> None:
        file_content = "test file content"
        file_path = AsyncPath(tmp_path) / "test_file.txt"

        with (
            patch.object(AsyncPath, "write_text", AsyncMock(return_value=None)),
            patch.object(
                AsyncPath, "read_bytes", AsyncMock(return_value=file_content.encode())
            ),
            patch.object(AsyncPath, "exists", AsyncMock(return_value=True)),
            patch.object(Path, "exists", MagicMock(return_value=True)),
        ):
            expected_hash = blake3(file_content.encode()).hexdigest()

            result_async = await hash.blake3(file_path)
            assert result_async == expected_hash

            result_path = await hash.blake3(file_path._path)
            assert result_path == expected_hash

    @pytest.mark.asyncio
    async def test_crc32c_with_string(self) -> None:
        test_string = "test string for crc32c"

        with patch("acb.actions.hash.crc32c") as mock_crc32c:
            mock_crc32c.return_value = 123456789

            result = await hash.crc32c(test_string)
            assert result == 123456789
            mock_crc32c.assert_called_with(test_string.encode())

    @pytest.mark.asyncio
    async def test_crc32c_with_bytes(self) -> None:
        test_bytes = b"test bytes for crc32c"

        with patch("acb.actions.hash.crc32c") as mock_crc32c:
            mock_crc32c.return_value = 987654321

            result = await hash.crc32c(test_bytes)
            assert result == 987654321
            mock_crc32c.assert_called_with(test_bytes)

    @pytest.mark.asyncio
    async def test_crc32c_with_file(self, tmp_path: Path) -> None:
        file_content = "test file content for crc32c"
        file_path = AsyncPath(tmp_path) / "test_crc32c.txt"

        with (
            patch.object(AsyncPath, "write_text", AsyncMock(return_value=None)),
            patch.object(AsyncPath, "read_text", AsyncMock(return_value=file_content)),
            patch.object(AsyncPath, "exists", AsyncMock(return_value=True)),
            patch.object(Path, "exists", MagicMock(return_value=True)),
            patch("acb.actions.hash.crc32c") as mock_crc32c,
        ):
            mock_crc32c.return_value = 987654321

            result_async = await hash.crc32c(file_path)
            assert result_async == 987654321
            mock_crc32c.assert_called_with(file_content.encode())

            result_path = await hash.crc32c(file_path._path)
            assert result_path == 987654321

    @pytest.mark.asyncio
    async def test_md5_with_string(self) -> None:
        test_string = "test string for md5"
        expected_hash = hashlib.md5(
            test_string.encode(), usedforsecurity=False
        ).hexdigest()
        result = await hash.md5(test_string)
        assert result == expected_hash

    @pytest.mark.asyncio
    async def test_md5_with_bytes(self) -> None:
        test_bytes = b"test bytes for md5"
        expected_hash = hashlib.md5(test_bytes, usedforsecurity=False).hexdigest()
        result = await hash.md5(test_bytes)
        assert result == expected_hash

    @pytest.mark.asyncio
    async def test_md5_with_file(self, tmp_path: Path) -> None:
        file_content = "test file content for md5"
        file_path = AsyncPath(tmp_path) / "test_md5.txt"

        with (
            patch.object(AsyncPath, "write_text", AsyncMock(return_value=None)),
            patch.object(AsyncPath, "read_text", AsyncMock(return_value=file_content)),
            patch.object(AsyncPath, "exists", AsyncMock(return_value=True)),
            patch.object(Path, "exists", MagicMock(return_value=True)),
        ):
            expected_hash = hashlib.md5(
                file_content.encode(), usedforsecurity=False
            ).hexdigest()

            result_async = await hash.md5(file_path)
            assert result_async == expected_hash

            result_path = await hash.md5(file_path._path)
            assert result_path == expected_hash

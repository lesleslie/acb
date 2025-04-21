import hashlib
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from blake3 import blake3
from acb.actions.hash import hash


class TestHash:
    @pytest.mark.asyncio
    async def test_blake3_with_string(self) -> None:
        test_string = "test string to hash"
        expected_hash = blake3(test_string.encode()).hexdigest()

        result = await hash.blake3(test_string)

        assert result == expected_hash
        assert isinstance(result, str)
        assert re.match(r"^[0-9a-f]{64}$", result)

    @pytest.mark.asyncio
    async def test_blake3_with_bytes(self) -> None:
        test_bytes = b"test bytes to hash"
        expected_hash = blake3(test_bytes).hexdigest()

        result = await hash.blake3(test_bytes)

        assert result == expected_hash
        assert isinstance(result, str)
        assert re.match(r"^[0-9a-f]{64}$", result)

    @pytest.mark.asyncio
    async def test_blake3_with_list(self) -> None:
        test_list = ["item1", "item2", "item3"]
        combined = "item1item2item3"
        expected_hash = blake3(combined.encode()).hexdigest()

        result = await hash.blake3(test_list)

        assert result == expected_hash
        assert isinstance(result, str)
        assert re.match(r"^[0-9a-f]{64}$", result)

    @pytest.mark.asyncio
    async def test_blake3_with_empty_input(self) -> None:
        fixed_timestamp = 1234567890.123456
        with patch("arrow.utcnow") as mock_utcnow:
            mock_utcnow.return_value = MagicMock(float_timestamp=fixed_timestamp)

            result = await hash.blake3("")

            expected_hash = blake3(str(fixed_timestamp).encode()).hexdigest()
            assert result == expected_hash
            assert isinstance(result, str)
            assert re.match(r"^[0-9a-f]{64}$", result)

    @pytest.mark.asyncio
    async def test_blake3_with_file(self, tmp_path: Path) -> None:
        file_content = "test file content"
        file_path = AsyncPath(tmp_path) / "test_file.txt"
        await file_path.write_text(file_content)

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
            assert isinstance(result, int)
            mock_crc32c.assert_called_once_with(test_string.encode())

    @pytest.mark.asyncio
    async def test_crc32c_with_file(self, tmp_path: Path) -> None:
        file_content = "test file content for crc32c"
        file_path = AsyncPath(tmp_path) / "test_crc32c.txt"
        await file_path.write_text(file_content)

        with patch("acb.actions.hash.crc32c") as mock_crc32c:
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
        assert isinstance(result, str)
        assert re.match(r"^[0-9a-f]{32}$", result)

    @pytest.mark.asyncio
    async def test_md5_with_ascii_option(self) -> None:
        test_string = "test string for md5 with ascii"
        expected_hash = hashlib.md5(
            test_string.encode("ascii"), usedforsecurity=False
        ).hexdigest()

        result = await hash.md5(test_string, ascii=True)

        assert result == expected_hash
        assert isinstance(result, str)
        assert re.match(r"^[0-9a-f]{32}$", result)

    @pytest.mark.asyncio
    async def test_md5_with_security_option(self) -> None:
        test_string = "test string for md5 with security option"

        with patch("hashlib.md5") as mock_md5:
            mock_md5_instance = MagicMock()
            mock_md5_instance.hexdigest.return_value = "mocked_md5_hash"
            mock_md5.return_value = mock_md5_instance

            result = await hash.md5(test_string, usedforsecurity=True)

            assert result == "mocked_md5_hash"
            mock_md5.assert_called_with(test_string.encode(), usedforsecurity=True)

    @pytest.mark.asyncio
    async def test_md5_with_file(self, tmp_path: Path) -> None:
        file_content = "test file content for md5"
        file_path = AsyncPath(tmp_path) / "test_md5.txt"
        await file_path.write_text(file_content)

        expected_hash = hashlib.md5(
            file_content.encode(), usedforsecurity=False
        ).hexdigest()

        result_async = await hash.md5(file_path)
        assert result_async == expected_hash

        result_path = await hash.md5(file_path._path)
        assert result_path == expected_hash

    @pytest.mark.asyncio
    async def test_md5_with_non_ascii_characters(self) -> None:
        test_string = "こんにちは世界"
        expected_hash = hashlib.md5(
            test_string.encode(), usedforsecurity=False
        ).hexdigest()

        result = await hash.md5(test_string)

        assert result == expected_hash

        with pytest.raises(UnicodeEncodeError):
            await hash.md5(test_string, ascii=True)

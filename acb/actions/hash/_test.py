import hashlib
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from blake3 import blake3
from acb.actions.hash import Blake3Hasher, hash


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

    def test_create_blake3(self) -> None:
        hasher = hash.create_blake3()

        assert isinstance(hasher, Blake3Hasher)

    def test_blake3_hasher_with_string(self) -> None:
        test_string = "test string for streaming"
        expected_hash = blake3(test_string.encode()).hexdigest()

        hasher = hash.create_blake3()
        hasher.update(test_string)
        result = hasher.hexdigest()

        assert result == expected_hash
        assert isinstance(result, str)
        assert re.match(r"^[0-9a-f]{64}$", result)

    def test_blake3_hasher_with_bytes(self) -> None:
        test_bytes = b"test bytes for streaming"
        expected_hash = blake3(test_bytes).hexdigest()

        hasher = hash.create_blake3()
        hasher.update(test_bytes)
        result = hasher.hexdigest()

        assert result == expected_hash
        assert isinstance(result, str)
        assert re.match(r"^[0-9a-f]{64}$", result)

    def test_blake3_hasher_with_multiple_updates(self) -> None:
        chunk1 = "chunk1"
        chunk2 = "chunk2"
        chunk3 = "chunk3"
        combined = chunk1 + chunk2 + chunk3
        expected_hash = blake3(combined.encode()).hexdigest()

        hasher = hash.create_blake3()
        hasher.update(chunk1)
        hasher.update(chunk2)
        hasher.update(chunk3)
        result = hasher.hexdigest()

        assert result == expected_hash

    def test_blake3_hasher_finalize(self) -> None:
        test_data = "test finalize method"
        expected_digest = blake3(test_data.encode()).digest()

        hasher = hash.create_blake3()
        hasher.update(test_data)
        result = hasher.finalize()

        assert result == expected_digest
        assert result.hex() == expected_digest.hex()

    @pytest.mark.asyncio
    async def test_streaming_vs_direct_hash(self) -> None:
        chunk_size = 1024
        large_data = b"x" * (chunk_size * 10)

        full_hash = await hash.blake3(large_data)

        hasher = hash.create_blake3()
        for i in range(0, len(large_data), chunk_size):
            chunk = large_data[i : i + chunk_size]
            hasher.update(chunk)
        chunk_hash = hasher.hexdigest()

        assert chunk_hash == full_hash

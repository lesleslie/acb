from typing import TYPE_CHECKING, Any

import pytest
from acb.actions.compress import compress, decompress
from acb.actions.encode import decode, encode
from acb.actions.hash import hash

if TYPE_CHECKING:
    from collections.abc import Sequence


@pytest.mark.unit
class TestCompressionActions:
    def test_compression_with_different_levels(self) -> None:
        test_data: str = "test" * 1000
        compression_levels: Sequence[int] = [1, 6, 9]

        for level in compression_levels:
            compressed = compress.gzip(test_data, compresslevel=level)
            assert compressed is not None
            decompressed_raw = decompress.gzip(compressed)
            decompressed: str = (
                decompressed_raw.decode()
                if isinstance(decompressed_raw, bytes)
                else decompressed_raw
            )
            assert decompressed == test_data

    def test_compression_with_large_data(self) -> None:
        large_data: str = "x" * (1024 * 1024)
        compressed = compress.gzip(large_data)
        assert compressed is not None
        decompressed_raw = decompress.gzip(compressed)
        decompressed: str = (
            decompressed_raw.decode()
            if isinstance(decompressed_raw, bytes)
            else decompressed_raw
        )
        assert decompressed == large_data


@pytest.mark.unit
class TestEncodingActions:
    @pytest.mark.asyncio
    async def test_encoding_with_different_formats(self) -> None:
        test_data: dict[str, Any] = {"test": "data", "nested": {"key": "value"}}

        json_encoded_raw = await encode.json(test_data)
        json_encoded: str = (
            json_encoded_raw.decode()
            if isinstance(json_encoded_raw, bytes)
            else json_encoded_raw
        )
        json_decoded: dict[str, Any] = await decode.json(json_encoded)
        assert json_decoded == test_data

        yaml_encoded_raw = await encode.yaml(test_data)
        yaml_encoded: str = (
            yaml_encoded_raw.decode()
            if isinstance(yaml_encoded_raw, bytes)
            else yaml_encoded_raw
        )
        yaml_decoded: dict[str, Any] = await decode.yaml(yaml_encoded)
        assert yaml_decoded == test_data

    @pytest.mark.asyncio
    async def test_encoding_with_custom_options(self) -> None:
        test_data: dict[str, int] = {"z": 1, "a": 2, "m": 3}

        json_encoded_raw = await encode.json(test_data, sort_keys=True)
        json_encoded: str = (
            json_encoded_raw.decode()
            if isinstance(json_encoded_raw, bytes)
            else json_encoded_raw
        )
        json_decoded: dict[str, int] = await decode.json(json_encoded)
        assert set(json_decoded.keys()) == {"a", "m", "z"}

        yaml_encoded_raw = await encode.yaml(test_data)
        yaml_encoded: str = (
            yaml_encoded_raw.decode()
            if isinstance(yaml_encoded_raw, bytes)
            else yaml_encoded_raw
        )
        yaml_decoded: dict[str, int] = await decode.yaml(yaml_encoded)
        assert yaml_decoded == test_data


@pytest.mark.unit
class TestHashActions:
    @pytest.mark.asyncio
    async def test_hash_with_different_inputs(self) -> None:
        test_cases: Sequence[str | bytes | list[int]] = [
            "test string",
            b"test bytes",
            str({"test": "dict"}),
            [1, 2, 3],
        ]

        for data in test_cases:
            if isinstance(data, str | bytes):
                result: str = await hash.blake3(data)
                assert isinstance(result, str)
                assert len(result) == 64

    @pytest.mark.asyncio
    async def test_hash_streaming(self) -> None:
        chunk_size: int = 1024
        large_data: bytes = b"x" * (chunk_size * 10)

        full_hash: str = await hash.blake3(large_data)

        hasher: Any = hash.create_blake3()
        for i in range(0, len(large_data), chunk_size):
            chunk: bytes = large_data[i : i + chunk_size]
            hasher.update(chunk)
        chunk_hash: str = hasher.finalize().hex()

        assert chunk_hash == full_hash

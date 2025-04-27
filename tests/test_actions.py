from typing import Any, Dict, List, Union

import pytest
from acb.actions.compress import compress, decompress
from acb.actions.encode import decode, encode
from acb.actions.hash import hash


@pytest.mark.unit
class TestCompressionActions:
    def test_compression_with_different_levels(self) -> None:
        test_data: str = "test" * 1000
        compression_levels: List[int] = [1, 6, 9]

        for level in compression_levels:
            compressed: bytes = compress.gzip(test_data, compresslevel=level)
            decompressed: str = decompress.gzip(compressed)
            assert decompressed == test_data

    def test_compression_with_large_data(self) -> None:
        large_data: str = "x" * (1024 * 1024)
        compressed: bytes = compress.gzip(large_data)
        decompressed: str = decompress.gzip(compressed)
        assert decompressed == large_data


@pytest.mark.unit
class TestEncodingActions:
    @pytest.mark.asyncio
    async def test_encoding_with_different_formats(self) -> None:
        test_data: Dict[str, Any] = {"test": "data", "nested": {"key": "value"}}

        json_encoded: str = await encode.json(test_data)
        json_decoded: Dict[str, Any] = await decode.json(json_encoded)
        assert json_decoded == test_data

        yaml_encoded: str = await encode.yaml(test_data)
        yaml_decoded: Dict[str, Any] = await decode.yaml(yaml_encoded)
        assert yaml_decoded == test_data

    @pytest.mark.asyncio
    async def test_encoding_with_custom_options(self) -> None:
        test_data: Dict[str, int] = {"z": 1, "a": 2, "m": 3}

        json_encoded: str = await encode.json(test_data, sort_keys=True)
        json_decoded: Dict[str, int] = await decode.json(json_encoded)
        assert list(json_decoded.keys()) == ["a", "m", "z"]

        yaml_encoded: str = await encode.yaml(test_data)
        yaml_decoded: Dict[str, int] = await decode.yaml(yaml_encoded)
        assert yaml_decoded == test_data


@pytest.mark.unit
class TestHashActions:
    @pytest.mark.asyncio
    async def test_hash_with_different_inputs(self) -> None:
        test_cases: List[Union[str, bytes, List[int]]] = [
            "test string",
            b"test bytes",
            str({"test": "dict"}),
            [1, 2, 3],
        ]

        for data in test_cases:
            result: str = await hash.blake3(data)  # type: ignore
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

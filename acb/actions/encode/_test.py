from pathlib import Path
from typing import Any, Final
from unittest.mock import AsyncMock, patch

import pytest
from anyio import Path as AsyncPath
from acb.actions.encode import decode, encode

TEST_DATA: Final[dict[str, Any]] = {"name": "Test", "value": 123, "active": True}


class TestEncode:
    @pytest.mark.asyncio
    async def test_json_encode(self) -> None:
        result = await encode.json(TEST_DATA)
        assert isinstance(result, bytes)
        assert b"Test" in result
        assert b"123" in result
        assert b"true" in result

    @pytest.mark.asyncio
    async def test_yaml_encode(self) -> None:
        result = await encode.yaml(TEST_DATA)
        assert isinstance(result, bytes)
        assert b"name: Test" in result
        assert b"value: 123" in result
        assert b"active: true" in result

    @pytest.mark.asyncio
    async def test_toml_encode(self) -> None:
        result = await encode.toml(TEST_DATA)
        assert isinstance(result, bytes)
        assert b'name = "Test"' in result
        assert b"value = 123" in result
        assert b"active = true" in result

    @pytest.mark.asyncio
    async def test_msgpack_encode(self) -> None:
        result = await encode.msgpack(TEST_DATA)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_pickle_encode(self) -> None:
        result = await encode.pickle(TEST_DATA)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_file_operations(self, tmp_path: Path) -> None:
        test_data = {"name": "Test", "value": 123, "active": True}
        file_path = AsyncPath(tmp_path) / "test_config.json"

        with (
            patch.object(AsyncPath, "write_text", AsyncMock(return_value=None)),
            patch.object(AsyncPath, "exists", AsyncMock(return_value=True)),
            patch.object(
                AsyncPath,
                "read_text",
                AsyncMock(
                    return_value='{"name": "Test", "value": 123, "active": true}'
                ),
            ),
        ):
            await encode.json(test_data, path=file_path)
            assert await file_path.exists()

            decoded = await decode.json(file_path)
            assert decoded == test_data


class TestDecode:
    @pytest.mark.asyncio
    async def test_json_decode(self) -> None:
        json_str = '{"name": "Test", "value": 123, "active": true}'
        result = await decode.json(json_str)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_yaml_decode(self) -> None:
        yaml_str = "name: Test\nvalue: 123\nactive: true"
        result = await decode.yaml(yaml_str)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_toml_decode(self) -> None:
        toml_str = 'name = "Test"\nvalue = 123\nactive = true'
        result = await decode.toml(toml_str)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_msgpack_decode(self) -> None:
        msgpack_data = await encode.msgpack(TEST_DATA)
        result = await decode.msgpack(msgpack_data)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_pickle_decode(self) -> None:
        pickle_data = await encode.pickle(TEST_DATA)
        result = await decode.pickle(pickle_data)
        assert result == TEST_DATA

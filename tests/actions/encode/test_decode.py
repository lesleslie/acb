"""Tests for decoding functionality."""

import json
import pickle
import tempfile
import typing as t
from typing import Final
from unittest.mock import AsyncMock, patch

import msgspec
import msgspec.msgpack
import pytest
import toml
import yaml
from anyio import Path as AsyncPath
from acb.actions.encode import decode, encode

TEST_DATA: Final[dict[str, t.Any]] = {"name": "Test", "value": 123, "active": True}
NESTED_TEST_DATA: Final[dict[str, t.Any]] = {
    "name": "Test",
    "value": 123,
    "active": True,
    "nested": {"key1": "value1", "key2": 234, "key3": False},
    "list": [1, 2, 3, "four", {"five": 5}],
}


class TestDecode:
    @pytest.fixture
    async def async_tmp_path(self, tmp_path: str) -> AsyncPath:
        return AsyncPath(tmp_path)

    @pytest.fixture
    def json_string(self) -> str:
        return '{"name": "Test", "value": 123, "active": true}'

    @pytest.fixture
    def json_bytes(self) -> bytes:
        return b'{"name": "Test", "value": 123, "active": true}'

    @pytest.fixture
    def yaml_string(self) -> str:
        return "name: Test\nvalue: 123\nactive: true"

    @pytest.fixture
    def yaml_bytes(self) -> bytes:
        return b"name: Test\nvalue: 123\nactive: true"

    @pytest.fixture
    def toml_string(self) -> str:
        return 'name = "Test"\nvalue = 123\nactive = true'

    @pytest.fixture
    def toml_bytes(self) -> bytes:
        return b'name = "Test"\nvalue = 123\nactive = true'

    @pytest.fixture
    def msgpack_bytes(self) -> bytes | None:
        return msgspec.msgpack.encode(TEST_DATA)

    @pytest.fixture
    def pickle_bytes(self) -> bytes:
        return pickle.dumps(TEST_DATA)

    @pytest.mark.asyncio
    async def test_json_decode_string(self, json_string: str) -> None:
        result = await decode.json(json_string)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_json_decode_bytes(self, json_bytes: bytes) -> None:
        result = await decode.json(json_bytes)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_yaml_decode_string(self, yaml_string: str) -> None:
        result = await decode.yaml(yaml_string)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_yaml_decode_bytes(self, yaml_bytes: bytes) -> None:
        result = await decode.yaml(yaml_bytes)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_toml_decode_string(self, toml_string: str) -> None:
        result = await decode.toml(toml_string)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_toml_decode_bytes(self, toml_bytes: bytes) -> None:
        result = await decode.toml(toml_bytes)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_msgpack_decode(self, msgpack_bytes: bytes) -> None:
        result = await decode.msgpack(msgpack_bytes)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_pickle_decode(self, pickle_bytes: bytes) -> None:
        result = await decode.pickle(pickle_bytes)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_json_decode_from_file(self, async_tmp_path: AsyncPath) -> None:
        file_path: AsyncPath = async_tmp_path / "test_data.json"
        await file_path.write_text(json.dumps(TEST_DATA))
        result = await decode.json(file_path)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_yaml_decode_from_file(self, async_tmp_path: AsyncPath) -> None:
        file_path: AsyncPath = async_tmp_path / "test_data.yaml"
        yaml_content = yaml.dump(TEST_DATA)
        if not isinstance(yaml_content, str):
            yaml_content = str(yaml_content)
        await file_path.write_text(yaml_content)
        result = await decode.yaml(file_path)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_toml_decode_from_file(self, async_tmp_path: AsyncPath) -> None:
        file_path: AsyncPath = async_tmp_path / "test_data.toml"
        await file_path.write_text(toml.dumps(TEST_DATA))
        result = await decode.toml(file_path)
        assert result == TEST_DATA

    @pytest.mark.asyncio
    async def test_complex_data_roundtrip(self) -> None:
        json_bytes: bytes = await encode.json(NESTED_TEST_DATA)
        json_result = await decode.json(json_bytes)
        assert json_result == NESTED_TEST_DATA

        yaml_bytes: bytes = await encode.yaml(NESTED_TEST_DATA)
        yaml_result = await decode.yaml(yaml_bytes)
        assert yaml_result == NESTED_TEST_DATA

        toml_bytes: bytes = await encode.toml(NESTED_TEST_DATA)
        toml_result = await decode.toml(toml_bytes)
        assert toml_result == NESTED_TEST_DATA

        msgpack_bytes: bytes = await encode.msgpack(NESTED_TEST_DATA)
        msgpack_result = await decode.msgpack(msgpack_bytes)
        assert msgpack_result == NESTED_TEST_DATA

        pickle_bytes: bytes = await encode.pickle(NESTED_TEST_DATA)
        pickle_result = await decode.pickle(pickle_bytes)
        assert pickle_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_file_operations_with_mocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_path: AsyncPath = AsyncPath(tmp_dir) / "test_config.json"
            mock_json: str = '{"name": "Test", "value": 123, "active": true}'

            await mock_path.parent.mkdir(exist_ok=True)
            await mock_path.write_text(mock_json)

            with (
                patch.object(AsyncPath, "read_text", AsyncMock(return_value=mock_json)),
                patch.object(AsyncPath, "exists", AsyncMock(return_value=True)),
            ):
                result = await decode.json(mock_path)
                assert result == TEST_DATA

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("invalid_input", "format_name"),
        [
            ("{not valid json}", "json"),
            ("not: valid: yaml: structure", "yaml"),
            ("not valid = toml", "toml"),
            (b"not valid msgpack", "msgpack"),
            (b"not valid pickle", "pickle"),
        ],
    )
    async def test_decode_error_handling(
        self,
        invalid_input: str | bytes,
        format_name: str,
    ) -> None:
        with pytest.raises(Exception):
            await getattr(decode, format_name)(invalid_input)

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            nonexistent_path: AsyncPath = AsyncPath(tmp_dir) / "nonexistent_file.json"
            with pytest.raises(FileNotFoundError):
                await decode.json(nonexistent_path)

    @pytest.mark.asyncio
    async def test_empty_input_handling(self) -> None:
        with pytest.raises(Exception):
            await decode.json("")
        with pytest.raises(Exception):
            await decode.yaml("")
        with pytest.raises(Exception):
            await decode.toml("")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("input_value", "expected_type"),
        [
            (b"bytes", bytes),
            ("string", str),
            (None, type(None)),
        ],
    )
    async def test_decode_return_type(
        self,
        input_value: t.Any,
        expected_type: type,
    ) -> None:
        if input_value is None:
            with pytest.raises(Exception):
                await decode.json(input_value)
        else:
            with patch.object(msgspec.json, "decode") as mock_decode:
                if isinstance(input_value, bytes):
                    mock_decode.return_value = {
                        "value": input_value.decode("utf-8", errors="replace"),
                    }
                else:
                    mock_decode.return_value = {"value": input_value}

                result = await decode.json(input_value)
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_write_text_type(self, async_tmp_path: AsyncPath) -> None:
        file_path: AsyncPath = async_tmp_path / "test.txt"
        content = "test content"
        await file_path.write_text(content)
        result = await file_path.read_text()
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_write_bytes_type(self, async_tmp_path: AsyncPath) -> None:
        file_path: AsyncPath = async_tmp_path / "test.bin"
        content = b"test content"
        await file_path.write_bytes(content)
        result = await file_path.read_bytes()
        assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_write_text_str_only(self, async_tmp_path: AsyncPath) -> None:
        file_path: AsyncPath = async_tmp_path / "test_str.txt"
        content: str = "test content"
        await file_path.write_text(content)
        result = await file_path.read_text()
        assert isinstance(result, str)

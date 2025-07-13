"""Tests for encoding functionality."""

import json
import pickle
import typing as t
from pathlib import Path
from unittest.mock import patch

import msgspec
import msgspec.msgpack
import pytest
import toml
import yaml
from acb.actions.encode import encode

TEST_DATA: t.Final[dict[str, t.Any]] = {"name": "Test", "value": 123, "active": True}
NESTED_TEST_DATA: t.Final[dict[str, t.Any]] = {
    "name": "Test",
    "value": 123,
    "active": True,
    "nested": {"key1": "value1", "key2": 234, "key3": False},
    "list": [1, 2, 3, "four", {"five": 5}],
}


class TestEncode:
    @pytest.fixture
    def async_tmp_path(self, tmp_path: Path) -> Path:
        return tmp_path

    @pytest.mark.asyncio
    async def test_json_encode(self) -> None:
        result_bytes: bytes = await encode.json(TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = json.loads(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_json_encode_with_indent(self) -> None:
        result_bytes: bytes = await encode.json(TEST_DATA, indent=4)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = json.loads(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_json_encode_to_file(self, async_tmp_path: Path) -> None:
        output_file: Path = async_tmp_path / "test.json"
        await encode.json(TEST_DATA, path=output_file)
        assert output_file.exists()
        content: str = output_file.read_text()
        decoded: t.Any = json.loads(content)
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_yaml_encode(self) -> None:
        result_bytes: bytes = await encode.yaml(TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = yaml.safe_load(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_yaml_encode_to_file(self, async_tmp_path: Path) -> None:
        output_file: Path = async_tmp_path / "test.yaml"
        await encode.yaml(TEST_DATA, path=output_file)
        assert output_file.exists()
        content: str = output_file.read_text()
        decoded: t.Any = yaml.safe_load(content)
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_toml_encode(self) -> None:
        result_bytes: bytes = await encode.toml(TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = toml.loads(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_toml_encode_to_file(self, async_tmp_path: Path) -> None:
        output_file: Path = async_tmp_path / "test.toml"
        await encode.toml(TEST_DATA, path=output_file)
        assert output_file.exists()
        content: str = output_file.read_text()
        decoded: t.Any = toml.loads(content)
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_msgpack_encode(self) -> None:
        result_bytes: bytes = await encode.msgpack(TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = msgspec.msgpack.decode(result_bytes)
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_msgpack_encode_to_file(self, async_tmp_path: Path) -> None:
        output_file: Path = async_tmp_path / "test.msgpack"
        await encode.msgpack(TEST_DATA, path=output_file)
        assert output_file.exists()
        content: bytes = output_file.read_bytes()
        decoded: t.Any = msgspec.msgpack.decode(content)
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_pickle_encode(self) -> None:
        result_bytes: bytes = await encode.pickle(TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = pickle.loads(result_bytes)  # nosec B301
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_pickle_encode_to_file(self, async_tmp_path: Path) -> None:
        output_file: Path = async_tmp_path / "test.pickle"
        await encode.pickle(TEST_DATA, path=output_file)
        assert output_file.exists()
        content: bytes = output_file.read_bytes()
        decoded: t.Any = pickle.loads(content)  # nosec B301
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_json_encode(self) -> None:
        result_bytes: bytes = await encode.json(NESTED_TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = json.loads(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_yaml_encode(self) -> None:
        result_bytes: bytes = await encode.yaml(NESTED_TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = yaml.safe_load(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_toml_encode(self) -> None:
        result_bytes: bytes = await encode.toml(NESTED_TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = toml.loads(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_msgpack_encode(self) -> None:
        result_bytes: bytes = await encode.msgpack(NESTED_TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = msgspec.msgpack.decode(result_bytes)
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_pickle_encode(self) -> None:
        result_bytes: bytes = await encode.pickle(NESTED_TEST_DATA)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = pickle.loads(result_bytes)  # nosec B301
        if isinstance(decoded, dict):
            dict_result: dict[str, t.Any] = decoded
        else:
            dict_result: dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_json_encode_with_mock(self) -> None:
        with patch("json.dumps") as mock_dumps:
            mock_dumps.return_value = '{"mocked": true}'

            with patch.object(msgspec.json, "encode") as mock_encode:
                mock_encode.return_value = b'{"mocked": true}'

                result_bytes: bytes = await encode.json(TEST_DATA)

                assert result_bytes == b'{"mocked": true}'
                mock_encode.assert_called_once()

    @pytest.mark.asyncio
    async def test_yaml_encode_with_mock(self) -> None:
        with patch("msgspec.yaml.encode") as mock_encode:
            mock_encode.return_value = b"mocked: true"

            result_bytes: bytes = await encode.yaml(TEST_DATA)

            assert result_bytes == b"mocked: true"
            mock_encode.assert_called_once()

    @pytest.mark.asyncio
    async def test_toml_encode_with_mock(self) -> None:
        with patch("msgspec.toml.encode") as mock_encode:
            mock_encode.return_value = b'mocked = "true"'

            result_bytes: bytes = await encode.toml(TEST_DATA)

            assert result_bytes == b'mocked = "true"'
            mock_encode.assert_called_once()

    @pytest.mark.asyncio
    async def test_msgpack_encode_with_mock(self) -> None:
        with patch("msgspec.msgpack.encode") as mock_encode:
            mock_encode.return_value = b"mocked data"

            result_bytes: bytes = await encode.msgpack(TEST_DATA)

            assert result_bytes == b"mocked data"
            mock_encode.assert_called_once()

    @pytest.mark.asyncio
    async def test_pickle_encode_with_mock(self) -> None:
        with patch("acb.actions.encode.serializers.pickle.encode") as mock_dumps:
            mock_dumps.return_value = b"mocked pickle data"

            result_bytes: bytes = await encode.pickle(TEST_DATA)

            assert result_bytes == b"mocked pickle data"
            mock_dumps.assert_called_once()

    @pytest.mark.asyncio
    async def test_pickle_encode_invalid(self) -> None:
        class InvalidClass:
            def __reduce__(self) -> tuple[str, tuple[()]]:
                msg = "Invalid class"
                raise ValueError(msg)

        with pytest.raises(ValueError):
            await encode.pickle(InvalidClass())

    @pytest.mark.asyncio
    async def test_json_encode_invalid(self) -> None:
        with pytest.raises(TypeError):
            await encode.json(object())

    @pytest.mark.asyncio
    async def test_yaml_encode_invalid(self) -> None:
        with pytest.raises(TypeError):
            await encode.yaml(object())

    @pytest.mark.asyncio
    async def test_toml_encode_invalid(self) -> None:
        with pytest.raises(TypeError):
            await encode.toml(object())

    @pytest.mark.asyncio
    async def test_msgpack_encode_invalid(self) -> None:
        with pytest.raises(TypeError):
            await encode.msgpack(object())

    @pytest.mark.parametrize(
        ("data", "expected_type"),
        [
            (True, bool),
            (1, int),
            (1.0, float),
            ("string", str),
            ([], list),
            ({}, dict),
            (None, type(None)),
        ],
    )
    @pytest.mark.asyncio
    async def test_json_encode_type_errors(
        self,
        data: t.Any,
        expected_type: type,
    ) -> None:
        with patch.object(msgspec.json, "encode") as mock_encode:
            mock_encode.side_effect = TypeError("Failed to encode")

            with pytest.raises(TypeError) as excinfo:
                await encode.json(data)

            assert "Failed to encode" in str(excinfo.value)

    @pytest.mark.parametrize(
        ("data", "expected_type"),
        [
            (True, bool),
            (1, int),
            (1.0, float),
            ("string", str),
            ([], list),
            ({}, dict),
            (None, type(None)),
        ],
    )
    @pytest.mark.asyncio
    async def test_yaml_encode_type_errors(
        self,
        data: t.Any,
        expected_type: type,
    ) -> None:
        with patch("msgspec.yaml.encode") as mock_encode:
            mock_encode.side_effect = TypeError("Failed to encode")

            with pytest.raises(TypeError) as excinfo:
                await encode.yaml(data)

            assert "Failed to encode" in str(excinfo.value)

    @pytest.mark.parametrize(
        ("data", "expected_type"),
        [
            (True, bool),
            (1, int),
            (1.0, float),
            ("string", str),
            ([], list),
            ({}, dict),
            (None, type(None)),
        ],
    )
    @pytest.mark.asyncio
    async def test_toml_encode_type_errors(
        self,
        data: t.Any,
        expected_type: type,
    ) -> None:
        with patch("msgspec.toml.encode") as mock_encode:
            mock_encode.side_effect = TypeError("Failed to encode")

            with pytest.raises(TypeError) as excinfo:
                await encode.toml(data)

            assert "Failed to encode" in str(excinfo.value)

    @pytest.mark.parametrize(
        ("data", "expected_type"),
        [
            (True, bool),
            (1, int),
            (1.0, float),
            ("string", str),
            ([], list),
            ({}, dict),
            (None, type(None)),
        ],
    )
    @pytest.mark.asyncio
    async def test_msgpack_encode_type_errors(
        self,
        data: t.Any,
        expected_type: type,
    ) -> None:
        with patch("msgspec.msgpack.encode") as mock_encode:
            mock_encode.side_effect = TypeError("Failed to encode")

            with pytest.raises(TypeError) as excinfo:
                await encode.msgpack(data)

            assert "Failed to encode" in str(excinfo.value)

    @pytest.mark.parametrize(
        ("data", "expected_type"),
        [
            (True, bool),
            (1, int),
            (1.0, float),
            ("string", str),
            ([], list),
            ({}, dict),
            (None, type(None)),
        ],
    )
    @pytest.mark.asyncio
    async def test_pickle_encode_type_errors(
        self,
        data: t.Any,
        expected_type: type,
    ) -> None:
        with patch("acb.actions.encode.serializers.pickle.encode") as mock_dumps:
            mock_dumps.side_effect = TypeError("Failed to encode")

            with pytest.raises(TypeError) as excinfo:
                await encode.pickle(data)

            assert "Failed to encode" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_error_handling_file_operations(self, async_tmp_path: Path) -> None:
        output_file: Path = async_tmp_path / "nonexistent_dir" / "test.json"

        with pytest.raises(FileNotFoundError):
            await encode.json(TEST_DATA, path=output_file)

        with patch("pathlib.Path.write_bytes") as mock_write_bytes:
            mock_write_bytes.side_effect = PermissionError("Access denied")

            output_file = async_tmp_path / "test.json"
            with pytest.raises(PermissionError):
                await encode.json(TEST_DATA, path=output_file)

        with patch("pathlib.Path.write_bytes") as mock_write_bytes:
            mock_write_bytes.side_effect = OSError("IO error")

            output_file = async_tmp_path / "test.json"
            with pytest.raises(IOError):
                await encode.json(TEST_DATA, path=output_file)

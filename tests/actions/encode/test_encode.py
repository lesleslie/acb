"""Tests for encoding functionality."""

import json
import pickle
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, patch

import msgpack
import msgspec
import pytest
import toml
import yaml
from acb.actions.encode import encode

TEST_DATA: t.Final[t.Dict[str, t.Any]] = {"name": "Test", "value": 123, "active": True}
NESTED_TEST_DATA: t.Final[t.Dict[str, t.Any]] = {
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
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_json_encode_with_indent(self) -> None:
        result_bytes: bytes = await encode.json(TEST_DATA, indent=4)
        assert isinstance(result_bytes, bytes)
        decoded: t.Any = json.loads(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == TEST_DATA
        lines: t.List[str] = result_bytes.decode().split("\n")
        assert len(lines) > 1

    @pytest.mark.asyncio
    async def test_json_encode_to_file(self, async_tmp_path: Path) -> None:
        file_path: Path = async_tmp_path / "test_data.json"

        with patch.object(Path, "write_bytes", AsyncMock()) as mock_write:
            await encode.json(TEST_DATA, path=file_path)

            assert mock_write.called
            call_args: bytes = mock_write.call_args[0][0]
            assert isinstance(call_args, bytes)
            decoded: t.Any = json.loads(call_args.decode())
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_yaml_encode(self) -> None:
        result_bytes: bytes = await encode.yaml(TEST_DATA)

        assert isinstance(result_bytes, bytes)
        decoded: t.Any = yaml.safe_load(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_yaml_encode_to_file(self, async_tmp_path: Path) -> None:
        file_path: Path = async_tmp_path / "test_data.yaml"

        with patch.object(Path, "write_bytes", AsyncMock()) as mock_write:
            await encode.yaml(TEST_DATA, path=file_path)

            assert mock_write.called
            call_args: bytes = mock_write.call_args[0][0]
            assert isinstance(call_args, bytes)
            decoded: t.Any = yaml.safe_load(call_args.decode())
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_toml_encode(self) -> None:
        result_bytes: bytes = await encode.toml(TEST_DATA)

        assert isinstance(result_bytes, bytes)
        decoded: t.Any = toml.loads(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_toml_encode_to_file(self, async_tmp_path: Path) -> None:
        file_path: Path = async_tmp_path / "test_data.toml"

        with patch.object(Path, "write_bytes", AsyncMock()) as mock_write:
            await encode.toml(TEST_DATA, path=file_path)

            assert mock_write.called
            call_args: bytes = mock_write.call_args[0][0]
            assert isinstance(call_args, bytes)
            decoded: t.Any = toml.loads(call_args.decode())
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_msgpack_encode(self) -> None:
        result_bytes: bytes = await encode.msgpack(TEST_DATA)

        assert isinstance(result_bytes, bytes)
        decoded: t.Any = msgpack.unpackb(result_bytes, raw=False)
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_msgpack_encode_to_file(self, async_tmp_path: Path) -> None:
        file_path: Path = async_tmp_path / "test_data.msgpack"

        with patch.object(Path, "write_bytes", AsyncMock()) as mock_write:
            await encode.msgpack(TEST_DATA, path=file_path)

            assert mock_write.called
            call_args: bytes = mock_write.call_args[0][0]
            assert isinstance(call_args, bytes)
            decoded: t.Any = msgpack.unpackb(call_args, raw=False)
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_pickle_encode(self) -> None:
        result_bytes: bytes = await encode.pickle(TEST_DATA)

        assert isinstance(result_bytes, bytes)
        decoded: t.Any = pickle.loads(result_bytes)
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_pickle_encode_to_file(self, async_tmp_path: Path) -> None:
        file_path: Path = async_tmp_path / "test_data.pickle"

        with patch.object(Path, "write_bytes", AsyncMock()) as mock_write:
            await encode.pickle(TEST_DATA, path=file_path)

            assert mock_write.called
            call_args: bytes = mock_write.call_args[0][0]
            assert isinstance(call_args, bytes)
            decoded: t.Any = pickle.loads(call_args)
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert dict_result == TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_json_encode(self) -> None:
        result_bytes: bytes = await encode.json(NESTED_TEST_DATA)

        assert isinstance(result_bytes, bytes)
        decoded: t.Any = json.loads(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_yaml_encode(self) -> None:
        result_bytes: bytes = await encode.yaml(NESTED_TEST_DATA)

        assert isinstance(result_bytes, bytes)
        decoded: t.Any = yaml.safe_load(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_toml_encode(self) -> None:
        result_bytes: bytes = await encode.toml(NESTED_TEST_DATA)

        assert isinstance(result_bytes, bytes)
        decoded: t.Any = toml.loads(result_bytes.decode())
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_msgpack_encode(self) -> None:
        result_bytes: bytes = await encode.msgpack(NESTED_TEST_DATA)

        assert isinstance(result_bytes, bytes)
        decoded: t.Any = msgpack.unpackb(result_bytes, raw=False)
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_nested_data_pickle_encode(self) -> None:
        result_bytes: bytes = await encode.pickle(NESTED_TEST_DATA)

        assert isinstance(result_bytes, bytes)
        decoded: t.Any = pickle.loads(result_bytes)
        if isinstance(decoded, dict):
            dict_result: t.Dict[str, t.Any] = decoded
        else:
            dict_result: t.Dict[str, t.Any] = {}
        assert dict_result == NESTED_TEST_DATA

    @pytest.mark.asyncio
    async def test_json_encode_with_mock(self) -> None:
        with patch("json.dumps") as mock_dumps:
            mock_dumps.return_value = '{"mocked": true}'

            with patch.object(msgspec.json, "encode") as mock_encode:
                mock_encode.side_effect = lambda obj, **kwargs: mock_dumps(
                    obj, indent=kwargs.get("indent")
                ).encode()

                result_bytes: bytes = await encode.json(TEST_DATA)

                assert result_bytes == b'{"mocked": true}'
                mock_dumps.assert_called_once_with(TEST_DATA, indent=None)

    @pytest.mark.asyncio
    async def test_yaml_encode_with_mock(self) -> None:
        with patch("yaml.dump") as mock_dump:
            mock_dump.return_value = "mocked: true"

            with patch.object(msgspec.yaml, "encode") as mock_encode:
                mock_encode.side_effect = lambda obj, **kwargs: mock_dump(obj).encode()

                result_bytes: bytes = await encode.yaml(TEST_DATA)

                assert result_bytes == b"mocked: true"
                mock_dump.assert_called_once_with(TEST_DATA)

    @pytest.mark.asyncio
    async def test_toml_encode_with_mock(self) -> None:
        with patch("toml.dumps") as mock_dumps:
            mock_dumps.return_value = "mocked = true"

            with patch.object(msgspec.toml, "encode") as mock_encode:
                mock_encode.side_effect = lambda obj, **kwargs: mock_dumps(obj).encode()

                result_bytes: bytes = await encode.toml(TEST_DATA)

                assert result_bytes == b"mocked = true"
                mock_dumps.assert_called_once_with(TEST_DATA)

    @pytest.mark.asyncio
    async def test_msgpack_encode_with_mock(self) -> None:
        with patch("acb.actions.encode.Encode.process") as mock_process:
            mock_process.return_value = b"mocked"

            result_bytes: bytes = await encode.msgpack(TEST_DATA)

            assert result_bytes == b"mocked"

    @pytest.mark.asyncio
    async def test_pickle_encode_with_mock(self) -> None:
        with patch("acb.actions.encode.Encode.process") as mock_process:
            mock_process.return_value = b"mocked"

            result_bytes: bytes = await encode.pickle(TEST_DATA)

            assert result_bytes == b"mocked"

    @pytest.mark.asyncio
    async def test_pickle_encode_invalid(self) -> None:
        class UnpickleableObject:
            def __reduce__(self):
                raise TypeError("Cannot pickle this object")

        with pytest.raises(TypeError):
            await encode.pickle(UnpickleableObject())

    @pytest.mark.asyncio
    async def test_json_encode_invalid(self) -> None:
        with patch("json.dumps", side_effect=TypeError):
            with pytest.raises(TypeError):
                await encode.json(object())

    @pytest.mark.asyncio
    async def test_yaml_encode_invalid(self) -> None:
        with patch("yaml.dump", side_effect=TypeError):
            with pytest.raises(TypeError):
                await encode.yaml(object())

    @pytest.mark.asyncio
    async def test_toml_encode_invalid(self) -> None:
        with patch("toml.dumps", side_effect=TypeError):
            with pytest.raises(TypeError):
                await encode.toml(object())

    @pytest.mark.asyncio
    async def test_msgpack_encode_invalid(self) -> None:
        with patch("msgpack.packb", side_effect=TypeError):
            with pytest.raises(TypeError):
                await encode.msgpack(object())

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data,expected_type",
        [
            (TEST_DATA, dict),
            (NESTED_TEST_DATA, dict),
        ],
    )
    async def test_json_encode_type_errors(
        self, data: t.Any, expected_type: type
    ) -> None:
        if not isinstance(data, dict):
            with pytest.raises(Exception):
                await encode.json(data)
        else:
            result_bytes: bytes = await encode.json(data)
            assert isinstance(result_bytes, bytes)
            decoded: t.Any = json.loads(result_bytes.decode())
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert isinstance(dict_result, dict)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data,expected_type",
        [
            (TEST_DATA, dict),
            (NESTED_TEST_DATA, dict),
        ],
    )
    async def test_yaml_encode_type_errors(
        self, data: t.Any, expected_type: type
    ) -> None:
        if not isinstance(data, dict):
            with pytest.raises(Exception):
                await encode.yaml(data)
        else:
            result_bytes: bytes = await encode.yaml(data)
            assert isinstance(result_bytes, bytes)
            decoded: t.Any = yaml.safe_load(result_bytes.decode())
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert isinstance(dict_result, dict)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data,expected_type",
        [
            (TEST_DATA, dict),
            (NESTED_TEST_DATA, dict),
        ],
    )
    async def test_toml_encode_type_errors(
        self, data: t.Any, expected_type: type
    ) -> None:
        if not isinstance(data, dict):
            with pytest.raises(Exception):
                await encode.toml(data)
        else:
            result_bytes: bytes = await encode.toml(data)
            assert isinstance(result_bytes, bytes)
            decoded: t.Any = toml.loads(result_bytes.decode())
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert isinstance(dict_result, dict)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data,expected_type",
        [
            (TEST_DATA, dict),
            (NESTED_TEST_DATA, dict),
        ],
    )
    async def test_msgpack_encode_type_errors(
        self, data: t.Any, expected_type: type
    ) -> None:
        if not isinstance(data, dict):
            with pytest.raises(Exception):
                await encode.msgpack(data)
        else:
            result_bytes: bytes = await encode.msgpack(data)
            assert isinstance(result_bytes, bytes)
            decoded: t.Any = msgpack.unpackb(result_bytes, raw=False)
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert isinstance(dict_result, dict)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data,expected_type",
        [
            (TEST_DATA, dict),
            (NESTED_TEST_DATA, dict),
        ],
    )
    async def test_pickle_encode_type_errors(
        self, data: t.Any, expected_type: type
    ) -> None:
        if not isinstance(data, dict):
            with pytest.raises(Exception):
                await encode.pickle(data)
        else:
            result_bytes: bytes = await encode.pickle(data)
            assert isinstance(result_bytes, bytes)
            decoded: t.Any = pickle.loads(result_bytes)
            if isinstance(decoded, dict):
                dict_result: t.Dict[str, t.Any] = decoded
            else:
                dict_result: t.Dict[str, t.Any] = {}
            assert isinstance(dict_result, dict)

    @pytest.mark.asyncio
    async def test_error_handling_file_operations(self, async_tmp_path: Path) -> None:
        test_file: Path = async_tmp_path / "test_data.json"

        with patch.object(Path, "write_bytes") as mock_write:
            mock_write.side_effect = PermissionError("Access denied")

            with pytest.raises(PermissionError):
                await encode.json(TEST_DATA, path=test_file)

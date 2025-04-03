import json as _json
from pathlib import Path

import pytest
from anyio import Path as AsyncPath
from acb.actions.encode import dump, load, serializers


class TestEncodeAction:
    @pytest.mark.anyio
    async def test_json_encode_decode(self) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        encoded_data = await dump(data, serializer=serializers.json)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.json)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_json_encode_decode_list(self) -> None:
        data = ["value1", 123, True]
        encoded_data = await dump(data, serializer=serializers.json)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.json)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_json_encode_decode_string(self) -> None:
        data = "This is a test string to be json encoded."
        encoded_data = await dump(data, serializer=serializers.json)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.json)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_json_encode_decode_int(self) -> None:
        data = 123
        encoded_data = await dump(data, serializer=serializers.json)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.json)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_json_encode_decode_float(self) -> None:
        data = 123.45
        encoded_data = await dump(data, serializer=serializers.json)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.json)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_json_encode_decode_bool(self) -> None:
        data = True
        encoded_data = await dump(data, serializer=serializers.json)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.json)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_json_encode_to_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.json")
        await dump(data, path=file_path, serializer=serializers.json)
        assert await file_path.exists()
        file_content = await file_path.read_bytes()
        decoded_data = _json.loads(file_content.decode())
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_json_decode_from_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.json")
        await file_path.write_text(_json.dumps(data))
        decoded_data = await load(file_path, serializer=serializers.json)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_yaml_encode_decode(self) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        encoded_data = await dump(data, serializer=serializers.yaml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.yaml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_yaml_encode_decode_list(self) -> None:
        data = ["value1", 123, True]
        encoded_data = await dump(data, serializer=serializers.yaml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.yaml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_yaml_encode_decode_string(self) -> None:
        data = "This is a test string to be yaml encoded."
        encoded_data = await dump(data, serializer=serializers.yaml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.yaml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_yaml_encode_decode_int(self) -> None:
        data = 123
        encoded_data = await dump(data, serializer=serializers.yaml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.yaml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_yaml_encode_decode_float(self) -> None:
        data = 123.45
        encoded_data = await dump(data, serializer=serializers.yaml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.yaml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_yaml_encode_decode_bool(self) -> None:
        data = True
        encoded_data = await dump(data, serializer=serializers.yaml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.yaml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_yaml_encode_to_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.yaml")
        await dump(data, path=file_path, serializer=serializers.yaml)
        assert await file_path.exists()
        file_content = await file_path.read_bytes()
        decoded_data = serializers.yaml.decode(file_content)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_yaml_decode_from_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.yaml")
        await file_path.write_bytes(serializers.yaml.encode(data))
        decoded_data = await load(file_path, serializer=serializers.yaml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_msgpack_encode_decode(self) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        encoded_data = await dump(data, serializer=serializers.msgpack)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.msgpack)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_msgpack_encode_decode_list(self) -> None:
        data = ["value1", 123, True]
        encoded_data = await dump(data, serializer=serializers.msgpack)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.msgpack)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_msgpack_encode_decode_string(self) -> None:
        data = "This is a test string to be msgpack encoded."
        encoded_data = await dump(data, serializer=serializers.msgpack)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.msgpack)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_msgpack_encode_decode_int(self) -> None:
        data = 123
        encoded_data = await dump(data, serializer=serializers.msgpack)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.msgpack)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_msgpack_encode_decode_float(self) -> None:
        data = 123.45
        encoded_data = await dump(data, serializer=serializers.msgpack)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.msgpack)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_msgpack_encode_decode_bool(self) -> None:
        data = True
        encoded_data = await dump(data, serializer=serializers.msgpack)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.msgpack)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_msgpack_encode_to_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.msgpack")
        await dump(data, path=file_path, serializer=serializers.msgpack)
        assert await file_path.exists()
        file_content = await file_path.read_bytes()
        decoded_data = serializers.msgpack.decode(file_content)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_msgpack_decode_from_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.msgpack")
        await file_path.write_bytes(serializers.msgpack.encode(data))
        decoded_data = await load(file_path, serializer=serializers.msgpack)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_pickle_encode_decode(self) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        encoded_data = await dump(data, serializer=serializers.pickle)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.pickle)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_pickle_encode_decode_list(self) -> None:
        data = ["value1", 123, True]
        encoded_data = await dump(data, serializer=serializers.pickle)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.pickle)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_pickle_encode_decode_string(self) -> None:
        data = "This is a test string to be pickle encoded."
        encoded_data = await dump(data, serializer=serializers.pickle)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.pickle)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_pickle_encode_decode_int(self) -> None:
        data = 123
        encoded_data = await dump(data, serializer=serializers.pickle)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.pickle)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_pickle_encode_decode_float(self) -> None:
        data = 123.45
        encoded_data = await dump(data, serializer=serializers.pickle)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.pickle)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_pickle_encode_decode_bool(self) -> None:
        data = True
        encoded_data = await dump(data, serializer=serializers.pickle)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.pickle)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_pickle_encode_to_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.pickle")
        await dump(data, path=file_path, serializer=serializers.pickle)
        assert await file_path.exists()
        file_content = await file_path.read_bytes()
        decoded_data = serializers.pickle.decode(file_content)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_pickle_decode_from_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.pickle")
        await file_path.write_bytes(serializers.pickle.encode(data))
        decoded_data = await load(file_path, serializer=serializers.pickle)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_toml_encode_decode(self) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        encoded_data = await dump(data, serializer=serializers.toml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.toml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_toml_encode_decode_list(self) -> None:
        data = ["value1", 123, True]
        encoded_data = await dump(data, serializer=serializers.toml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.toml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_toml_encode_decode_string(self) -> None:
        data = "This is a test string to be toml encoded."
        encoded_data = await dump(data, serializer=serializers.toml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.toml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_toml_encode_decode_int(self) -> None:
        data = 123
        encoded_data = await dump(data, serializer=serializers.toml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.toml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_toml_encode_decode_float(self) -> None:
        data = 123.45
        encoded_data = await dump(data, serializer=serializers.toml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.toml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_toml_encode_decode_bool(self) -> None:
        data = True
        encoded_data = await dump(data, serializer=serializers.toml)
        assert isinstance(encoded_data, bytes)
        decoded_data = await load(encoded_data, serializer=serializers.toml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_toml_encode_to_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.toml")
        await dump(data, path=file_path, serializer=serializers.toml)
        assert await file_path.exists()
        file_content = await file_path.read_bytes()
        decoded_data = serializers.toml.decode(file_content)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_toml_decode_from_path(self, tmp_path: Path) -> None:
        data = {"key1": "value1", "key2": 123, "key3": True}
        file_path = AsyncPath(tmp_path / "test.toml")
        await file_path.write_bytes(serializers.toml.encode(data))
        decoded_data = await load(file_path, serializer=serializers.toml)
        assert decoded_data == data

    @pytest.mark.anyio
    async def test_sort_keys(self) -> None:
        data = {"c": 3, "a": 1, "b": 2}
        encoded_data = await dump(data, serializer=serializers.json, sort_keys=True)
        decoded_data = await load(encoded_data, serializer=serializers.json)
        assert decoded_data == data
        assert encoded_data == b'{"a":1,"b":2,"c":3}'

    @pytest.mark.anyio
    async def test_use_list(self) -> None:
        data = ["a", "b", "c"]
        encoded_data = await dump(data, serializer=serializers.msgpack, use_list=True)
        decoded_data = await load(
            encoded_data, serializer=serializers.msgpack, use_list=True
        )
        assert decoded_data == data

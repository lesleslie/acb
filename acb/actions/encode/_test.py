from pathlib import Path
from unittest.mock import Mock, patch

import dill
import msgspec
import pytest
from aiopath import AsyncPath
from acb.actions.encode import Encode, Serializers, serializers, yaml_encode


@pytest.fixture
def encode() -> Encode:
    return Encode()


@pytest.fixture
def mock_frame() -> Mock:
    frame = Mock()
    frame.f_code.co_filename = "test_file.py"
    frame.f_lineno = 1
    return frame


class TestSerializers:
    def test_serializers_initialization(self) -> None:
        serializer = Serializers()

        assert serializer.json == msgspec.json
        assert serializer.yaml == msgspec.yaml
        assert serializer.msgpack == msgspec.msgpack
        assert serializer.pickle is not None
        assert serializer.toml == msgspec.toml

        assert serializer.pickle.encode == dill.dumps
        assert serializer.pickle.decode == dill.loads


class TestYamlEncode:
    def test_yaml_encode_basic_types(self) -> None:
        data = {"test": "value", "number": 42}
        result = yaml_encode(data)

        assert isinstance(result, bytes)
        decoded = msgspec.yaml.decode(result)
        assert decoded == data

    def test_yaml_encode_with_none(self) -> None:
        data = {"test": None}
        result = yaml_encode(data)

        assert isinstance(result, bytes)
        decoded = msgspec.yaml.decode(result)
        assert decoded == data

    def test_yaml_encode_with_sort_keys(self) -> None:
        data = {"b": 2, "a": 1}
        result = yaml_encode(data, sort_keys=True)

        decoded = msgspec.yaml.decode(result)
        assert list(decoded.keys()) == ["a", "b"]


class TestEncode:
    def test_initialization(self, encode: Encode) -> None:
        assert encode.serializers == serializers.__dict__
        assert hasattr(encode, "json")
        assert hasattr(encode, "yaml")
        assert hasattr(encode, "msgpack")
        assert hasattr(encode, "toml")
        assert hasattr(encode, "pickle")

    @pytest.mark.asyncio
    async def test_encode_json(self, encode: Encode, mock_frame: Mock) -> None:
        with patch("sys._getframe", return_value=mock_frame):
            with patch("linecache.getline", return_value="await encode.json(data)"):
                data = {"test": "value"}
                result = await encode.json(data)

                assert isinstance(result, bytes)
                decoded = msgspec.json.decode(result)
                assert decoded == data

    @pytest.mark.asyncio
    async def test_encode_yaml(self, encode: Encode, mock_frame: Mock) -> None:
        with patch("sys._getframe", return_value=mock_frame):
            with patch("linecache.getline", return_value="await encode.yaml(data)"):
                data = {"test": "value"}
                result = await encode.yaml(data)

                assert isinstance(result, bytes)
                decoded = msgspec.yaml.decode(result)
                assert decoded == data

    @pytest.mark.asyncio
    async def test_decode_json(self, encode: Encode, mock_frame: Mock) -> None:
        with patch("sys._getframe", return_value=mock_frame):
            with patch("linecache.getline", return_value="await decode.json(data)"):
                data = msgspec.json.encode({"test": "value"})
                result = await encode.json(data)

                assert isinstance(result, dict)
                assert result == {"test": "value"}

    @pytest.mark.asyncio
    async def test_dump_to_file(
        self, encode: Encode, mock_frame: Mock, tmp_path: Path
    ) -> None:
        test_file = AsyncPath(tmp_path) / "test.json"

        with patch("sys._getframe", return_value=mock_frame):
            with patch("linecache.getline", return_value="await dump.json(data)"):
                data = {"test": "value"}
                await encode.json(data, path=test_file)

                content = await test_file.read_bytes()
                decoded = msgspec.json.decode(content)
                assert decoded == data

    @pytest.mark.asyncio
    async def test_load_from_file(
        self, encode: Encode, mock_frame: Mock, tmp_path: Path
    ) -> None:
        test_file = AsyncPath(tmp_path) / "test.json"
        data = {"test": "value"}
        await test_file.write_bytes(msgspec.json.encode(data))

        with patch("sys._getframe", return_value=mock_frame):
            with patch("linecache.getline", return_value="await load.json(data)"):
                result = await encode.json(test_file)
                assert result == data

    @pytest.mark.asyncio
    async def test_msgpack_with_use_list(
        self, encode: Encode, mock_frame: Mock
    ) -> None:
        with patch("sys._getframe", return_value=mock_frame):
            with patch("linecache.getline", return_value="await encode.msgpack(data)"):
                data = {"test": (1, 2, 3)}
                result = await encode.msgpack(data, use_list=True)

                decoded = msgspec.msgpack.decode(result)
                assert decoded["test"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_yaml_with_sort_keys(self, encode: Encode, mock_frame: Mock) -> None:
        with patch("sys._getframe", return_value=mock_frame):
            with patch("linecache.getline", return_value="await encode.yaml(data)"):
                data = {"b": 2, "a": 1}
                result = await encode.yaml(data, sort_keys=True)

                decoded = msgspec.yaml.decode(result)
                assert list(decoded.keys()) == ["a", "b"]

    def test_get_vars(self, encode: Encode, mock_frame: Mock) -> None:
        with patch("linecache.getline", return_value="await encode.json(data)"):
            action, serializer = encode.get_vars(mock_frame)

            assert action == "encode"
            assert serializer == msgspec.json

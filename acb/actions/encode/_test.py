import datetime as _datetime
import tempfile
import typing as t
from pathlib import Path
from types import FrameType
from unittest.mock import AsyncMock, Mock, patch

import msgspec
import pytest
import yaml
from aiopath import AsyncPath
from acb.actions.encode import (
    Encode,
    decode,
    dump,
    encode,
    load,
    serializers,
    yaml_encode,
)


class TestSerializers:
    """Tests for the Serializers class."""

    def test_serializers_initialization(self) -> None:
        """Test that the Serializers dataclass initializes correctly."""
        assert hasattr(serializers, "json")
        assert hasattr(serializers, "yaml")
        assert hasattr(serializers, "msgpack")
        assert hasattr(serializers, "pickle")
        assert hasattr(serializers, "toml")

        assert serializers.pickle.encode.__name__ == "dumps"
        assert serializers.pickle.decode.__name__ == "loads"


class TestYamlEncode:
    """Tests for the yaml_encode function."""

    def test_yaml_encode_basic(self) -> None:
        """Test basic yaml encoding."""
        data = {"test": "value"}
        encoded = yaml_encode(data)
        assert isinstance(encoded, bytes)

        decoded = yaml.safe_load(encoded)
        assert decoded == data

    def test_yaml_encode_with_none(self) -> None:
        """Test yaml encoding with None values."""
        data = {"test": None}
        encoded = yaml_encode(data)
        assert isinstance(encoded, bytes)

        decoded = yaml.safe_load(encoded)
        assert decoded == {"test": None}

    def test_yaml_encode_with_datetime(self) -> None:
        """Test yaml encoding with datetime objects."""
        now = _datetime.datetime(2020, 5, 10, 12, 30, 45)
        data = {"date": now}

        with patch("msgspec.yaml._to_builtins") as mock_to_builtins:
            datetime_str = "2020-05-10 12:30:45"
            mock_to_builtins.return_value = {"date": datetime_str}

            encoded = yaml_encode(data)
            assert isinstance(encoded, bytes)

            mock_to_builtins.assert_called_once()
            assert mock_to_builtins.call_args[0][0] == data

            decoded = yaml.safe_load(encoded)
            assert isinstance(decoded, dict)
            assert "date" in decoded
            assert isinstance(decoded["date"], str)
            assert decoded["date"] == datetime_str

    def test_yaml_encode_with_custom_hook(self) -> None:
        """Test yaml encoding with a custom encoding hook."""

        def custom_hook(obj: t.Any) -> t.Any:
            if isinstance(obj, _datetime.datetime):
                return obj.isoformat()
            return obj

        now = _datetime.datetime(2020, 1, 15, 14, 30, 45)
        data = {"date": now}

        with patch("msgspec.yaml._to_builtins") as mock_to_builtins:
            mock_to_builtins.return_value = {"date": "2020-01-15T14:30:45"}

            encoded = yaml_encode(data, enc_hook=custom_hook)
            assert isinstance(encoded, bytes)

            mock_to_builtins.assert_called_once()

            assert mock_to_builtins.call_args[0][0] == data

            assert mock_to_builtins.call_args[1]["enc_hook"] == custom_hook

            decoded = yaml.safe_load(encoded)
            assert isinstance(decoded, dict)
            assert "date" in decoded
            expected_format = "2020-01-15T14:30:45"
            assert decoded["date"] == expected_format

    def test_yaml_encode_with_sort_keys(self) -> None:
        """Test yaml encoding with sort_keys=True."""
        data = {"z": 1, "a": 2}
        encoded = yaml_encode(data, sort_keys=True)
        assert isinstance(encoded, bytes)

        encoded_str = encoded.decode()
        a_pos = encoded_str.find("a:")
        z_pos = encoded_str.find("z:")
        assert a_pos < z_pos


class TestEncode:
    """Tests for the Encode class."""

    @pytest.mark.asyncio
    async def test_encode_initialization(self) -> None:
        """Test that the Encode instance initializes correctly."""
        encoder = Encode()
        assert hasattr(encoder, "json")
        assert hasattr(encoder, "yaml")
        assert hasattr(encoder, "msgpack")
        assert hasattr(encoder, "toml")
        assert hasattr(encoder, "pickle")
        assert encoder.serializers == serializers.__dict__

    @pytest.mark.asyncio
    async def test_encode_get_vars(self) -> None:
        """Test the get_vars method that extracts context info."""
        encoder = Encode()

        mock_frame = Mock(spec=FrameType)
        mock_frame.f_code.co_filename = "test.py"
        mock_frame.f_lineno = 10

        with patch("linecache.getline", return_value="await encode.json(data)"):
            action, serializer = encoder.get_vars(mock_frame)
            assert action == "encode"
            assert serializer == serializers.json

        with patch("linecache.getline", return_value="await dump.yaml(data)"):
            action, serializer = encoder.get_vars(mock_frame)
            assert action == "dump"
            assert serializer == serializers.yaml

    @pytest.mark.asyncio
    async def test_process_encode(self) -> None:
        """Test the process method for encoding."""
        encoder = Encode()
        encoder.action = "encode"
        encoder.serializer = serializers.json

        data = {"test": "value"}
        result = await encoder.process(data)

        assert isinstance(result, bytes)
        decoded = msgspec.json.decode(result)
        assert decoded == data

    @pytest.mark.asyncio
    async def test_process_encode_to_file(self) -> None:
        """Test encoding to a file."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp_path = temp.name

        try:
            encoder = Encode()
            encoder.action = "dump"
            encoder.serializer = serializers.json
            encoder.path = AsyncPath(temp_path)

            data = {"test": "file_value"}
            await encoder.process(data)

            file_content = await AsyncPath(temp_path).read_bytes()
            decoded = msgspec.json.decode(file_content)
            assert decoded == data

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_process_decode(self) -> None:
        """Test the process method for decoding."""
        encoder = Encode()
        encoder.action = "decode"
        encoder.serializer = serializers.json

        data = {"test": "value"}
        encoded = msgspec.json.encode(data)

        result = await encoder.process(encoded)
        assert result == data

    @pytest.mark.asyncio
    async def test_process_decode_from_file(self) -> None:
        """Test decoding from a file path."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            data = {"test": "file_content"}
            encoded = msgspec.json.encode(data)
            temp.write(encoded)
            temp_path = temp.name

        try:
            mock_path = AsyncMock(spec=AsyncPath)
            mock_path.read_text.return_value = encoded

            encoder = Encode()
            encoder.action = "load"
            encoder.serializer = serializers.json

            result = await encoder.process(mock_path)
            assert result == data

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_call_encode_json(self) -> None:
        """Test the __call__ method for JSON encoding."""
        mock_frame = Mock(spec=FrameType)

        with (
            patch.object(Encode, "get_vars", return_value=("encode", serializers.json)),
            patch("sys._getframe", return_value=mock_frame),
        ):
            data = {"test": "call_value"}
            result = await encode.json(data)

            assert isinstance(result, bytes)
            decoded = msgspec.json.decode(result)
            assert decoded == data

    @pytest.mark.asyncio
    async def test_call_decode_yaml(self) -> None:
        """Test the __call__ method for YAML decoding."""
        data = {"test": "yaml_value"}
        encoded = msgspec.yaml.encode(data)

        mock_frame = Mock(spec=FrameType)

        with (
            patch.object(Encode, "get_vars", return_value=("decode", serializers.yaml)),
            patch("sys._getframe", return_value=mock_frame),
        ):
            result = await decode.yaml(encoded)
            assert result == data

    @pytest.mark.asyncio
    async def test_call_dump_to_file(self) -> None:
        """Test dumping to a file."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp_path = temp.name

        try:
            path = AsyncPath(temp_path)

            mock_frame = Mock(spec=FrameType)

            with (
                patch.object(
                    Encode, "get_vars", return_value=("dump", serializers.json)
                ),
                patch("sys._getframe", return_value=mock_frame),
            ):
                data = {"test": "dump_file"}
                await dump.json(data, path=path)

                file_content = await path.read_bytes()
                decoded = msgspec.json.decode(file_content)
                assert decoded == data

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_call_load_from_file(self) -> None:
        """Test loading from a file."""
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            data = {"test": "load_file"}
            encoded = msgspec.toml.encode(data)
            temp.write(encoded)
            temp_path = temp.name

        try:
            path = AsyncPath(temp_path)

            mock_frame = Mock(spec=FrameType)

            with (
                patch.object(
                    Encode, "get_vars", return_value=("load", serializers.toml)
                ),
                patch("sys._getframe", return_value=mock_frame),
            ):
                result = await load.toml(path)
                assert result == data

        finally:
            Path(temp_path).unlink()


class TestFormatSpecific:
    """Tests for specific serialization formats."""

    @pytest.mark.asyncio
    async def test_msgpack_use_list(self) -> None:
        """Test msgpack with use_list parameter."""
        data = [1, 2, 3]

        mock_frame = Mock(spec=FrameType)

        mock_msgpack = Mock()
        mock_msgpack.encode = Mock(return_value=b"test_encoded_data")
        mock_msgpack.decode = Mock(return_value=data)

        with (
            patch.object(Encode, "get_vars", return_value=("encode", mock_msgpack)),
            patch("sys._getframe", return_value=mock_frame),
            patch.object(Encode, "process", new_callable=AsyncMock) as mock_process,
        ):
            mock_process.return_value = b"test_encoded_data"

            await encode.msgpack(data, use_list=True)

            mock_process.assert_called_once()

            with (
                patch.object(Encode, "get_vars", return_value=("decode", mock_msgpack)),
                patch.object(
                    Encode, "process", new_callable=AsyncMock
                ) as mock_decode_process,
            ):
                mock_decode_process.return_value = data

                result = await decode.msgpack(b"test_encoded_data", use_list=True)

                assert result == data

    @pytest.mark.asyncio
    async def test_yaml_sort_keys(self) -> None:
        """Test YAML with sort_keys parameter."""
        data = {"z": 1, "a": 2}

        mock_frame = Mock(spec=FrameType)

        with (
            patch.object(Encode, "get_vars", return_value=("encode", serializers.yaml)),
            patch("sys._getframe", return_value=mock_frame),
        ):
            encoded = await encode.yaml(data, sort_keys=True)
            encoded_str = encoded.decode("utf-8")

            a_pos = encoded_str.find("a:")
            z_pos = encoded_str.find("z:")
            assert a_pos < z_pos

    @pytest.mark.asyncio
    async def test_pickle_complex_objects(self) -> None:
        """Test pickle with complex Python objects."""

        class TestClass:
            def __init__(self, value: str) -> None:
                self.value = value

            def __eq__(self, other: object) -> bool:
                if not isinstance(other, TestClass):
                    return False
                return self.value == other.value

        obj = TestClass("pickle_test")

        mock_frame = Mock(spec=FrameType)

        mock_pickle = Mock()
        mock_pickle.encode = Mock(return_value=b"mock_pickled_data")

        with (
            patch.object(
                Encode, "get_vars", return_value=("encode", serializers.pickle)
            ),
            patch("sys._getframe", return_value=mock_frame),
            patch.object(Encode, "process", new_callable=AsyncMock) as mock_process,
        ):
            mock_process.return_value = b"mock_pickled_data"

            encoded = await encode.pickle(obj)

            mock_process.assert_called_once()

            decoded_obj = TestClass("pickle_test")

            with (
                patch.object(
                    Encode, "get_vars", return_value=("decode", serializers.pickle)
                ),
                patch.object(
                    Encode, "process", new_callable=AsyncMock
                ) as mock_decode_process,
            ):
                mock_decode_process.return_value = decoded_obj

                result = await decode.pickle(encoded)

                assert isinstance(result, TestClass)
                assert result.value == "pickle_test"
                assert result == obj

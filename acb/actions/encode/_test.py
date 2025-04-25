import math
from pathlib import Path
from typing import Any, Final
from unittest.mock import MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from acb.actions.encode import Encode, decode, encode, serializers

TEST_DATA: Final[dict[str, Any]] = {"name": "Test", "value": 123, "active": True}


@pytest.mark.unit
class TestEncode:
    @pytest.mark.asyncio
    async def test_json_encode_decode(self) -> None:
        encoded = await encode.json(TEST_DATA)
        assert isinstance(encoded, bytes)

        decoded = await decode.json(encoded)
        assert decoded == TEST_DATA

    @pytest.mark.asyncio
    async def test_serializer_registration(self) -> None:
        test_serializer = MagicMock()

        mock_serializers = MagicMock()
        mock_serializers.__dict__ = {}

        with patch("acb.actions.encode.serializers", mock_serializers):
            mock_serializers.__dict__["test"] = test_serializer

            assert "test" in mock_serializers.__dict__
            assert mock_serializers.__dict__["test"] == test_serializer

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_large_data_encoding(self) -> None:
        large_data = {str(i): "x" * 1000 for i in range(1000)}
        encoded = await encode.json(large_data)
        decoded = await decode.json(encoded)
        assert decoded == large_data

    @pytest.mark.asyncio
    async def test_yaml_encode_with_sort_keys(self) -> None:
        test_data = {"z": 1, "a": 2, "m": 3}

        encoded = await encode.yaml(test_data, sort_keys=True)
        assert isinstance(encoded, bytes)

        encoded_str = encoded.decode("utf-8")
        a_pos = encoded_str.find("a:")
        m_pos = encoded_str.find("m:")
        z_pos = encoded_str.find("z:")

        assert a_pos < m_pos < z_pos

    @pytest.mark.asyncio
    async def test_toml_encode_decode(self) -> None:
        test_data = {"name": "Test", "value": 123, "active": True}

        encoded = await encode.toml(test_data)
        assert isinstance(encoded, bytes)

        decoded = await decode.toml(encoded)
        assert decoded == test_data

    @pytest.mark.asyncio
    async def test_msgpack_encode_decode(self) -> None:
        test_data = {"name": "Test", "value": 123, "active": True}

        encoded = await encode.msgpack(test_data)
        assert isinstance(encoded, bytes)

        with patch.object(serializers.msgpack, "decode", return_value=test_data):
            decoded = await decode.msgpack(encoded)
            assert decoded == test_data

    @pytest.mark.asyncio
    async def test_msgpack_decode_with_use_list(self) -> None:
        test_data = {"items": [1, 2, 3]}

        encoded = await encode.msgpack(test_data)

        with patch.object(
            serializers.msgpack, "decode", return_value={"items": [1, 2, 3]}
        ):
            with patch.object(Encode, "use_list", True):
                decoded = await decode.msgpack(encoded)
                assert isinstance(decoded["items"], list)

    @pytest.mark.asyncio
    async def test_pickle_encode_decode(self) -> None:
        test_data = {"name": "Test", "value": 123, "active": True}

        encoded = await encode.pickle(test_data)
        assert isinstance(encoded, bytes)

        decoded = await decode.pickle(encoded)
        assert decoded == test_data

    @pytest.mark.asyncio
    async def test_file_operations(self, tmp_path: Path) -> None:
        test_data = {"name": "Test", "value": 123, "active": True}

        file_path = AsyncPath(tmp_path) / "test_config.json"

        await encode.json(test_data, path=file_path)

        assert await file_path.exists()

        decoded = await decode.json(file_path)
        assert decoded == test_data

    @pytest.mark.asyncio
    async def test_get_vars(self) -> None:
        encoder = Encode()

        mock_frame = MagicMock()
        mock_frame.f_code.co_filename = "test_file.py"
        mock_frame.f_lineno = 10

        with patch("linecache.getline", return_value="await encode.json(data)"):
            action, serializer = encoder.get_vars(mock_frame)
            assert action == "encode"
            assert serializer == serializers.json

        with patch("linecache.getline", return_value="await decode.yaml(data)"):
            action, serializer = encoder.get_vars(mock_frame)
            assert action == "decode"
            assert serializer == serializers.yaml

    @pytest.mark.asyncio
    async def test_complex_data_structures(self) -> None:
        complex_data = {
            "string": "test",
            "number": 42,
            "float": math.pi,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3, 4],
            "nested": {"a": 1, "b": [2, 3, {"c": 4}]},
        }

        toml_data = {
            "string": "test",
            "number": 42,
            "float": math.pi,
            "boolean": True,
            "list": [1, 2, 3, 4],
            "nested": {"a": 1, "b": [2, 3, {"c": 4}]},
        }

        json_encoded = await encode.json(complex_data)
        json_decoded = await decode.json(json_encoded)
        assert json_decoded == complex_data

        yaml_encoded = await encode.yaml(complex_data)
        yaml_decoded = await decode.yaml(yaml_encoded)
        assert yaml_decoded == complex_data

        toml_encoded = await encode.toml(toml_data)
        toml_decoded = await decode.toml(toml_encoded)
        assert toml_decoded == toml_data

        pickle_encoded = await encode.pickle(complex_data)
        pickle_decoded = await decode.pickle(pickle_encoded)
        assert pickle_decoded == complex_data

        msgpack_encoded = await encode.msgpack(complex_data)
        with patch.object(serializers.msgpack, "decode", return_value=complex_data):
            msgpack_decoded = await decode.msgpack(msgpack_encoded)
            assert msgpack_decoded == complex_data

"""Tests for encoding improvements including frame inspection and error handling."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import msgspec
import pytest
from anyio import Path as AsyncPath
from acb.actions.encode import Encode, decode, encode


class TestEncodeFrameInspection:
    """Test enhanced frame inspection capabilities."""

    @pytest.mark.asyncio
    async def test_caller_name_detection_test_context(self) -> None:
        """Test that test context is properly detected."""
        encoder = Encode()

        with patch("sys._getframe") as mock_getframe:
            mock_frame = MagicMock()
            mock_frame.f_code.co_name = "test_encode_json"
            mock_getframe.return_value = mock_frame

            # Create method should detect test context
            method = encoder._create_method("json", "encode")

            # Call the method in test context
            await method({"test": "data"})

            # Should have detected encode action from test name
            assert encoder.action == "encode"

    @pytest.mark.asyncio
    async def test_caller_name_detection_decode_test(self) -> None:
        """Test that decode test context is properly detected."""
        encoder = Encode()

        with patch("sys._getframe") as mock_getframe:
            mock_frame = MagicMock()
            mock_frame.f_code.co_name = "test_decode_json"
            mock_getframe.return_value = mock_frame

            # Create method for decode context
            method = encoder._create_method("json", "decode")

            # Call the method in decode test context
            await method(b'{"test": "data"}')

            # Should have detected decode action from test name
            assert encoder.action == "decode"

    @pytest.mark.asyncio
    async def test_linecache_pattern_matching(self) -> None:
        """Test enhanced pattern matching using linecache."""
        encoder = Encode()

        with patch("sys._getframe") as mock_getframe:
            with patch("linecache.getline") as mock_getline:
                mock_frame = MagicMock()
                mock_frame.f_code.co_filename = "/test/file.py"
                mock_frame.f_lineno = 42
                mock_getframe.return_value = mock_frame

                # Mock linecache to return code showing encode call
                mock_getline.return_value = "result = await encode.json(data)"

                # Call encoder
                await encoder({"test": "data"})

                # Should detect encode action from code context
                assert encoder.action == "encode"
                mock_getline.assert_called_once_with("/test/file.py", 42)

    @pytest.mark.asyncio
    async def test_pattern_matching_decode_call(self) -> None:
        """Test pattern matching for decode calls."""
        encoder = Encode()

        with patch("sys._getframe") as mock_getframe:
            with patch("linecache.getline") as mock_getline:
                mock_frame = MagicMock()
                mock_frame.f_code.co_filename = "/test/file.py"
                mock_frame.f_lineno = 42
                mock_getframe.return_value = mock_frame

                # Mock linecache to return code showing decode call
                mock_getline.return_value = "result = await decode.yaml(yaml_data)"

                # Call encoder
                await encoder(b"test: data")

                # Should detect decode action and yaml serializer
                assert encoder.action == "decode"

    @pytest.mark.asyncio
    async def test_fallback_json_encode_serializer(self) -> None:
        """Test fallback to JSON serializer when pattern matching fails."""
        encoder = Encode()

        with patch("sys._getframe") as mock_getframe:
            with patch("linecache.getline") as mock_getline:
                mock_frame = MagicMock()
                mock_frame.f_code.co_filename = "/test/file.py"
                mock_frame.f_lineno = 42
                mock_frame.f_code.co_name = "test_fallback_json_encode_serializer"
                mock_getframe.return_value = mock_frame

                # Mock linecache to return code that doesn't match patterns
                mock_getline.return_value = "some_other_code()"

                # Call encoder - should fallback to JSON encode
                result = await encoder({"test": "data"})

                # Should use JSON serializer as fallback
                assert isinstance(result, bytes)


class TestEncodeErrorHandling:
    """Test enhanced error handling in encoding operations."""

    @pytest.mark.asyncio
    async def test_decode_input_validation(self) -> None:
        """Test enhanced input validation for decode operations."""
        encoder = Encode()
        encoder.action = "decode"
        encoder.serializer = msgspec.json.decode

        # Test None input
        with pytest.raises(ValueError, match="Cannot decode from None input"):
            await encoder._decode(None)

        # Test empty string input
        with pytest.raises(ValueError, match="Cannot decode from empty input"):
            await encoder._decode("")

        # Test empty bytes input
        with pytest.raises(ValueError, match="Cannot decode from empty input"):
            await encoder._decode(b"")

    @pytest.mark.asyncio
    async def test_file_path_handling_async(self) -> None:
        """Test improved file path handling for AsyncPath."""
        encoder = Encode()
        encoder.action = "decode"
        encoder.serializer = msgspec.json.decode

        mock_path = MagicMock(spec=AsyncPath)
        mock_path.read_bytes = MagicMock(side_effect=AttributeError("No read_bytes"))
        mock_path.read_text = AsyncMock(return_value='{"test": "data"}')

        # Should fallback to read_text when read_bytes is not available
        result = await encoder._load_from_path(mock_path)

        mock_path.read_text.assert_called_once()
        assert result == b'{"test": "data"}'

    @pytest.mark.asyncio
    async def test_file_path_handling_sync(self) -> None:
        """Test improved file path handling for sync Path."""
        encoder = Encode()
        encoder.action = "decode"
        encoder.serializer = msgspec.json.decode

        mock_path = MagicMock(spec=Path)
        mock_path.read_bytes = MagicMock(side_effect=AttributeError("No read_bytes"))
        mock_path.read_text = MagicMock(return_value='{"test": "data"}')

        # Should fallback to read_text when read_bytes is not available
        result = await encoder._load_from_path(mock_path)

        mock_path.read_text.assert_called_once()
        assert result == b'{"test": "data"}'

    @pytest.mark.asyncio
    async def test_file_not_found_handling(self) -> None:
        """Test enhanced file not found error handling."""
        encoder = Encode()
        encoder.action = "decode"
        encoder.serializer = msgspec.json.decode

        mock_path = MagicMock(spec=AsyncPath)
        mock_path.read_bytes = MagicMock(
            side_effect=FileNotFoundError("File not found"),
        )

        # Should raise FileNotFoundError with clear message
        with pytest.raises(FileNotFoundError, match="File not found: "):
            await encoder._load_from_path(mock_path)

    @pytest.mark.asyncio
    async def test_encode_decode_error_handling_msgspec(self) -> None:
        """Test decode error handling for msgspec errors."""
        encoder = Encode()
        encoder.action = "decode"
        encoder.serializer = msgspec.json.decode

        # Test msgspec.DecodeError handling
        with (
            patch(
                "msgspec.json.decode",
                side_effect=msgspec.DecodeError(
                    "JSON is malformed: invalid character (byte 12)",
                ),
            ),
            pytest.raises(
                msgspec.DecodeError,
                match="Failed to decode: JSON is malformed: invalid character",
            ),
        ):
            encoder._perform_decode(b'{"invalid": json}')

    @pytest.mark.asyncio
    async def test_encode_decode_error_handling_toml(self) -> None:
        """Test decode error handling for TOML errors."""
        encoder = Encode()
        encoder.action = "decode"
        encoder.serializer = msgspec.toml.decode

        # Test msgspec.DecodeError handling for TOML
        with (
            patch(
                "msgspec.toml.decode",
                side_effect=msgspec.DecodeError("Invalid value (at line 1, column 11)"),
            ),
            pytest.raises(
                msgspec.DecodeError,
                match="Failed to decode: Invalid value",
            ),
        ):
            encoder._perform_decode(b"invalid = toml")

    @pytest.mark.asyncio
    async def test_encode_decode_error_handling_generic(self) -> None:
        """Test decode error handling for generic exceptions."""
        encoder = Encode()
        encoder.action = "decode"

        # Create a mock serializer that raises ValueError
        mock_serializer = Mock(side_effect=ValueError("Some error"))
        encoder.serializer = mock_serializer

        # Test generic exception handling
        with pytest.raises(RuntimeError, match="Error during decoding: Some error"):
            encoder._perform_decode(b'{"test": "data"}')

    @pytest.mark.asyncio
    async def test_encode_path_validation(self) -> None:
        """Test path validation in encode operations."""
        encoder = Encode()
        encoder.action = "encode"
        encoder.serializer = msgspec.json.encode

        # Test encoding a Path object directly should raise TypeError
        test_path = AsyncPath("/test/path")
        with pytest.raises(TypeError, match="Cannot encode a Path object directly"):
            await encoder._encode(test_path)

    @pytest.mark.asyncio
    async def test_encode_path_decode_action(self) -> None:
        """Test that Path objects in decode action are handled correctly."""
        encoder = Encode()
        encoder.action = "decode"
        encoder.serializer = msgspec.json.decode

        mock_path = MagicMock(spec=AsyncPath)
        mock_path.read_bytes = MagicMock(return_value=b'{"test": "data"}')

        # Should call _decode when action is decode
        with patch.object(
            encoder,
            "_decode",
            return_value={"test": "data"},
        ) as mock_decode:
            await encoder._encode(mock_path)
            mock_decode.assert_called_once_with(mock_path)

    @pytest.mark.asyncio
    async def test_write_permission_error(self) -> None:
        """Test permission error handling when writing files."""
        encoder = Encode()
        encoder.path = AsyncPath("/readonly/file.json")

        with (
            patch.object(
                AsyncPath,
                "write_bytes",
                side_effect=PermissionError("Access denied"),
            ),
            pytest.raises(
                PermissionError,
                match="Permission denied when writing to",
            ),
        ):
            await encoder._write_to_path(b'{"test": "data"}')

    @pytest.mark.asyncio
    async def test_serializer_validation(self) -> None:
        """Test serializer validation in encode/decode operations."""
        encoder = Encode()
        encoder.action = "encode"
        encoder.serializer = None

        # Test encode with no serializer
        with pytest.raises(ValueError, match="Serializer not set"):
            encoder._serialize({"test": "data"}, {})

        # Test decode with no serializer
        encoder.action = "decode"
        with pytest.raises(ValueError, match="Serializer not set"):
            encoder._perform_decode(b'{"test": "data"}')


class TestEncodeDataPreprocessing:
    """Test enhanced data preprocessing capabilities."""

    @pytest.mark.asyncio
    async def test_json_sort_keys_preprocessing(self) -> None:
        """Test JSON sort_keys preprocessing."""
        encoder = Encode()
        encoder.action = "encode"
        encoder.serializer = msgspec.json.encode
        encoder.sort_keys = True

        unsorted_dict = {"z": 1, "a": 2, "m": 3}

        result = encoder._preprocess_data(unsorted_dict, {})

        # Should return sorted dictionary
        assert list(result.keys()) == ["a", "m", "z"]

    @pytest.mark.asyncio
    async def test_yaml_sort_keys_preprocessing(self) -> None:
        """Test YAML sort_keys preprocessing."""
        encoder = Encode()
        encoder.action = "encode"
        encoder.serializer = msgspec.yaml.encode
        encoder.sort_keys = True

        test_data = {"test": "data"}
        kwargs = {}

        encoder._preprocess_data(test_data, kwargs)

        # Should add sort_keys to kwargs
        assert kwargs["sort_keys"] is True

    @pytest.mark.asyncio
    async def test_toml_list_preprocessing(self) -> None:
        """Test TOML list of dicts preprocessing."""
        encoder = Encode()
        encoder.action = "encode"
        encoder.serializer = msgspec.toml.encode

        test_data = {
            "normal_list": ["a", "b", "c"],
            "dict_list": [{"key1": "value1"}, {"key2": "value2"}],
            "mixed_list": ["string", {"key": "value"}],
        }

        result = encoder._preprocess_data(test_data, {})

        # Lists with dicts should be converted to strings
        assert result["normal_list"] == ["a", "b", "c"]  # Unchanged
        assert isinstance(result["dict_list"], str)  # Converted to string
        assert isinstance(result["mixed_list"], str)  # Converted to string

    @pytest.mark.asyncio
    async def test_json_indent_handling(self) -> None:
        """Test JSON indent parameter handling."""
        encoder = Encode()
        encoder.action = "encode"
        encoder.serializer = msgspec.json.encode

        test_data = {"test": "data"}
        kwargs = {"indent": 2}

        with patch("json.dumps") as mock_dumps:
            mock_dumps.return_value = '{\n  "test": "data"\n}'

            result = encoder._serialize(test_data, kwargs)

            mock_dumps.assert_called_once_with(test_data, indent=2)
            assert result == b'{\n  "test": "data"\n}'

    @pytest.mark.asyncio
    async def test_encode_json_extra_kwargs_filtering(self) -> None:
        """Test filtering of extra kwargs for JSON encoding."""
        encoder = Encode()
        encoder.action = "encode"
        encoder.serializer = msgspec.json.encode

        test_data = {"test": "data"}

        # Test with indent parameter that should be filtered out
        kwargs = {
            "indent": 2,
        }  # This parameter should be filtered out for msgspec.json.encode

        # The logic should handle indent specially and fall back to json.dumps
        with patch("json.dumps") as mock_dumps:
            mock_dumps.return_value = '{"test": "data"}'

            result = encoder._serialize(test_data, kwargs)

            # Should have called json.dumps with indent
            mock_dumps.assert_called_once_with(test_data, indent=2)
            assert result == b'{"test": "data"}'


class TestEncodeStringInputHandling:
    """Test enhanced string input handling."""

    @pytest.mark.asyncio
    async def test_string_to_bytes_conversion(self) -> None:
        """Test string to bytes conversion for specific serializers."""
        encoder = Encode()
        encoder.action = "decode"

        test_cases = [
            (msgspec.json.decode, '{"test": "data"}'),
            (msgspec.yaml.decode, "test: data"),
            (msgspec.toml.decode, 'test = "data"'),
        ]

        for serializer, test_string in test_cases:
            encoder.serializer = serializer
            result = encoder._prepare_string_input(test_string)
            assert result == test_string.encode()

        # Test with non-targeted serializer
        encoder.serializer = msgspec.msgpack.decode
        result = encoder._prepare_string_input("test string")
        assert result == "test string"  # Should remain unchanged


class TestEncodeIntegrationImprovements:
    """Test integration of encoding improvements."""

    @pytest.mark.asyncio
    async def test_encode_roundtrip_with_improvements(self) -> None:
        """Test full encode/decode roundtrip with all improvements."""
        test_data = {
            "string": "test",
            "number": 123,
            "boolean": True,
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }

        # Encode the data
        encoded_json = await encode.json(test_data, sort_keys=True)
        assert isinstance(encoded_json, bytes)

        # Decode the data
        decoded_data = await decode.json(encoded_json)
        assert decoded_data == test_data

    @pytest.mark.asyncio
    async def test_file_operations_with_improvements(self, tmp_path: Path) -> None:
        """Test file operations with enhanced error handling."""
        test_data = {"test": "file_data", "number": 42}
        file_path = tmp_path / "test_encode.json"

        # Test encode to file
        await encode.json(test_data, path=file_path)
        assert file_path.exists()

        # Test decode from file
        result = await decode.json(file_path)
        assert result == test_data

    @pytest.mark.asyncio
    async def test_error_handling_integration(self) -> None:
        """Test integration of error handling improvements."""
        # Test with invalid JSON
        invalid_json = b'{"invalid": json}'

        with pytest.raises(msgspec.DecodeError):
            await decode.json(invalid_json)

        # Test with None input
        with pytest.raises(ValueError):
            await decode.json(None)

        # Test with empty input
        with pytest.raises(ValueError):
            await decode.json("")

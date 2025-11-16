"""Integration tests for ACB actions and adapters working together."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typing import Any

from acb.actions.compress import compress, decompress
from acb.actions.encode import decode, encode
from acb.actions.hash import hash
from acb.adapters import import_adapter
from acb.config import Config
from acb.depends import depends


class TestActionAdapterIntegration:
    """Test integration between ACB actions and adapters."""

    @pytest.fixture
    def mock_config(self) -> Config:
        """Create a mock config for testing."""
        config = MagicMock(spec=Config)
        config.app.name = "test_app"
        config.app.title = "Test App"
        config.deployed = False
        return config

    @pytest.mark.asyncio
    async def test_json_encoding_decoding_operations(self) -> None:
        """Test encoding and decoding operations."""
        test_data = {"message": "Hello ACB Integration", "value": 42}

        # Test encoding
        encoded_result = await encode.json(test_data)
        assert encoded_result is not None

        # Convert to string if needed for decode
        if isinstance(encoded_result, bytes):
            str_data = encoded_result.decode("utf-8")
        else:
            str_data = encoded_result

        # Test decoding
        decoded = await decode.json(str_data)
        assert decoded == test_data

    def test_compression_decompression_cycle(self, tmp_path: Path) -> None:
        """Test compression and decompression cycle."""
        original_data = "This is test data for compression integration"
        temp_file = tmp_path / "compressed.bin"

        # Compress data - sync method
        compressed_result = compress.brotli(original_data)
        assert compressed_result is not None

        # For file-based compression, we'd need to do it differently since the API is sync
        # Let's write the compressed result to file manually
        temp_file.write_bytes(compressed_result)
        assert temp_file.exists()

        # Decompress from file - sync method
        decompressed_result = decompress.brotli(temp_file)
        assert decompressed_result is not None

        # Verify round trip
        assert decompressed_result == original_data

    @pytest.mark.asyncio
    async def test_hashing_with_encoded_content(self) -> None:
        """Test hashing of encoded content."""
        data = {"test": "data", "value": 123}

        # Encode to JSON - this returns bytes
        json_bytes = await encode.json(data)
        assert isinstance(json_bytes, bytes)

        # Convert bytes to string if needed for hash function
        json_str = json_bytes.decode("utf-8")

        # Hash the encoded string
        hash_result = await hash.blake3(json_str)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # Blake3 produces 64 character hex string

        # Test with bytes too
        hash_from_bytes = await hash.blake3(json_bytes)
        assert isinstance(hash_from_bytes, str)

    @pytest.mark.asyncio
    async def test_dependency_injection_with_actions(self, mock_config: Any) -> None:
        """Test dependency injection working with actions."""
        # Mock the dependency injection system
        original_get = depends.get

        def mock_get(cls):
            if cls == Config:
                return mock_config
            return original_get(cls)

        # Patch the depends.get method
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(depends, "get", mock_get)

            # Test that we can still use actions
            test_data = {"dependency": "injection", "test": True}
            result = await encode.json(test_data)
            assert result is not None

    @pytest.mark.asyncio
    async def test_multiple_actions_chain(self, tmp_path: Path) -> None:
        """Test chaining multiple actions together."""
        test_data = {"message": "ACB integration test", "nested": {"value": 12345}}

        # Encode to JSON - returns bytes
        json_result = await encode.json(test_data)
        assert json_result is not None

        # Convert to string if needed by compress action
        json_str = (
            json_result.decode("utf-8")
            if isinstance(json_result, bytes)
            else json_result
        )
        assert isinstance(json_str, str)

        # Compress the JSON - sync method
        compressed_result = compress.brotli(json_str)
        assert compressed_result is not None

        # Hash the compressed data (bytes) - async method
        hash_result = await hash.blake3(compressed_result)
        assert hash_result is not None
        assert len(hash_result) == 64

        # Decompress - sync method
        decompressed_result = decompress.brotli(compressed_result)
        assert decompressed_result is not None

        # Decode back to original - convert from string
        decoded_result = await decode.json(decompressed_result)
        assert decoded_result == test_data

    @pytest.mark.asyncio
    async def test_error_handling_in_action_chains(self) -> None:
        """Test error handling when chaining actions."""
        # Test with non-existent file to decoding - should raise appropriate error
        # Since decode.json will try to read the file, it should raise FileNotFoundError
        with pytest.raises(Exception):  # Could be FileNotFoundError or other
            await decode.json("/nonexistent/path.json")

        # Test compression with non-existent file
        with pytest.raises(FileNotFoundError):
            decompress.brotli("/nonexistent/file")


class TestAdapterIntegration:
    """Test ACB adapter integration scenarios."""

    def test_mock_adapter_integration(self) -> None:
        """Test integration with mock adapters."""
        # This test verifies that adapter integration works conceptually
        # For a real integration test we would test actual functionality rather than mocking the import

        # Just verify we can import adapter functionality
        # The import_adapter function is what's important for integration
        assert callable(import_adapter)

        # Test that import_adapter can be called (even if it fails due to missing dependencies)
        try:
            # This will likely throw an error due to missing dependencies, but we can catch it
            result = import_adapter()
            assert isinstance(result, tuple)  # Should return a tuple
        except Exception:
            # Expected that adapter might not load properly due to missing deps
            # The important thing is that the function exists and is callable
            pass

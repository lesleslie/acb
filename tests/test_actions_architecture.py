"""Tests for ACB Actions architecture patterns.

This module tests that Actions are properly positioned as utility functions
rather than runtime architectural layers, verifying they are stateless,
immediately available, and organized by function.
"""

import pytest

from acb.actions.compress import compress, decompress
from acb.actions.encode import decode, encode
from acb.actions.hash import hash


class TestActionsArchitecture:
    """Test that Actions follow the correct architectural pattern."""

    def test_actions_are_stateless_functions(self):
        """Test that actions are stateless utility functions."""
        # Actions should be available as module attributes without instantiation
        assert hasattr(compress, "gzip")
        assert hasattr(compress, "brotli")
        assert hasattr(decode, "json")
        assert hasattr(encode, "json")
        assert hasattr(hash, "blake3")

        # They should be callable directly
        assert callable(compress.gzip)
        assert callable(encode.json)
        assert callable(hash.blake3)

    @pytest.mark.asyncio
    async def test_compression_actions(self):
        """Test compression and decompression actions."""
        original_data = "Hello, ACB!"

        # Test brotli compression/decompression
        compressed = compress.brotli(original_data, level=1)
        decompressed = decompress.brotli(compressed)

        assert decompressed == original_data

        # Test gzip compression/decompression
        compressed_gzip = compress.gzip(original_data)
        decompressed_gzip = decompress.gzip(compressed_gzip)

        assert decompressed_gzip == original_data

    @pytest.mark.asyncio
    async def test_encoding_actions(self):
        """Test encoding and decoding actions."""
        test_data = {"message": "Hello, ACB!", "number": 42}

        # Test JSON encoding/decoding
        json_str = await encode.json(test_data)
        decoded_json = await decode.json(json_str)

        assert decoded_json == test_data

        # Test YAML encoding/decoding (if available)
        try:
            yaml_str = await encode.yaml(test_data)
            decoded_yaml = await decode.yaml(yaml_str)
            assert decoded_yaml == test_data
        except ImportError:
            # YAML dependencies might not be available in test environment
            pass

    @pytest.mark.asyncio
    async def test_hashing_actions(self):
        """Test hashing actions."""
        test_data = b"Hello, ACB!"

        # Test blake3 hashing
        hash_result = await hash.blake3(test_data)
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

        # Test consistency - same input should produce same hash
        hash_result2 = await hash.blake3(test_data)
        assert hash_result == hash_result2

        # Test different input produces different hash
        different_hash = await hash.blake3(b"different data")
        assert hash_result != different_hash

    def test_actions_no_lifecycle_requirements(self):
        """Test that actions don't require initialization or lifecycle management."""
        # Actions should work immediately without any setup
        test_string = "test data"

        # These should work without any service initialization
        compressed = compress.gzip(test_string)
        encoded = encode.json({"data": test_string})
        hashed = hash.blake3(test_string.encode())

        # Verify operations completed
        assert len(compressed) > 0
        assert len(encoded) > 0
        assert len(hashed) > 0

    def test_actions_organized_by_function(self):
        """Test that actions are organized by function/verb categories."""
        # Verify different action categories exist

        # Check that each category has the expected functions
        assert hasattr(compress, "gzip") or hasattr(compress, "brotli")
        assert hasattr(encode, "json") or hasattr(encode, "yaml")
        assert hasattr(hash, "blake3") or hasattr(hash, "md5")

    @pytest.mark.asyncio
    async def test_actions_integration_with_other_layers(self):
        """Test that actions can be used within other architectural layers."""
        # This demonstrates that actions serve as utilities across layers
        test_data = {"user": "test", "value": 123}

        # Use encoding action to serialize data (utility for other layers)
        serialized = await encode.json(test_data)
        assert isinstance(serialized, str)

        # Use hashing action to create identifier
        data_hash = await hash.blake3(serialized.encode())
        assert isinstance(data_hash, str) and len(data_hash) > 0

        # Use compression action to reduce size
        compressed = compress.gzip(serialized)
        assert len(compressed) < len(serialized.encode())

        # All operations completed without errors
        assert True


class TestActionsVersusServices:
    """Test to ensure Actions are distinct from Services."""

    def test_actions_vs_services_distinction(self):
        """Verify that Actions are different from Services."""
        from acb.services._base import ServiceBase

        # Actions are functions/modules, not classes requiring instantiation
        assert callable(compress.gzip)  # Function that can be called directly

        # Services require class instantiation
        with pytest.raises(TypeError):
            # This should fail because ServiceBase is abstract
            ServiceBase()

        # Actions don't have service lifecycle methods
        assert not hasattr(compress, "initialize")
        assert not hasattr(compress, "shutdown")
        assert not hasattr(compress, "health_check")

        # Actions are immediately available
        result = compress.gzip("test")
        assert result is not None


if __name__ == "__main__":
    # Run tests manually if executed directly
    import pytest

    pytest.main([__file__, "-v"])

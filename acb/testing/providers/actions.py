"""Mock Action Provider for ACB Testing.

Provides mock implementations of ACB actions with realistic behavior
patterns for comprehensive testing scenarios.

Features:
- Realistic mock behavior for all action types
- Configurable response patterns
- Error simulation capabilities
- Performance tracking
- Data transformation simulation
"""

from unittest.mock import MagicMock

import typing as t
from contextlib import contextmanager
from typing import Any

from acb.testing.discovery import (
    TestProviderCapability,
    create_test_provider_metadata_template,
)

# Provider metadata
PROVIDER_METADATA = create_test_provider_metadata_template(
    name="Mock Action Provider",
    category="mocking",
    provider_type="action_mock",
    author="ACB Testing Team",
    description="Mock implementations of ACB actions with realistic behavior",
    version="1.0.0",
    capabilities=[
        TestProviderCapability.ACTION_MOCKING,
        TestProviderCapability.PERFORMANCE_TESTING,
        TestProviderCapability.DATA_SEEDING,
    ],
    settings_class="MockActionProviderSettings",
)


class MockActionProvider:
    """Provider for mock ACB actions."""

    PROVIDER_METADATA = PROVIDER_METADATA

    def __init__(self) -> None:
        self._mock_instances: dict[str, t.Any] = {}
        self._call_history: dict[str, t.Any] = {}

    def create_compress_action_mock(
        self,
        behavior: dict[str, t.Any] | None = None,
    ) -> MagicMock:
        """Create a realistic compress action mock."""
        compress_mock = MagicMock()

        default_behavior = {
            "compression_ratio": 0.6,  # 60% compression ratio
            "processing_delay": 0.001,  # 1ms processing time
            "error_rate": 0.0,  # No errors by default
        }

        if behavior:
            default_behavior.update(behavior)

        def mock_gzip_compress(data: bytes) -> bytes:
            import time

            time.sleep(default_behavior["processing_delay"])

            import random

            if random.random() < default_behavior["error_rate"]:
                msg = "Compression failed"
                raise RuntimeError(msg)

            # Simulate compression
            compressed_size = int(len(data) * default_behavior["compression_ratio"])
            return b"compressed_" + data[:compressed_size]

        def mock_gzip_decompress(data: bytes) -> bytes:
            import time

            time.sleep(default_behavior["processing_delay"])

            # Simple decompression simulation
            if data.startswith(b"compressed_"):
                return data[11:]  # Remove "compressed_" prefix
            return data

        def mock_brotli_compress(data: bytes) -> bytes:
            import time

            time.sleep(default_behavior["processing_delay"])

            # Better compression ratio for brotli
            improved_ratio = default_behavior["compression_ratio"] * 0.8
            compressed_size = int(len(data) * improved_ratio)
            return b"brotli_" + data[:compressed_size]

        def mock_brotli_decompress(data: bytes) -> bytes:
            import time

            time.sleep(default_behavior["processing_delay"])

            if data.startswith(b"brotli_"):
                return data[7:]  # Remove "brotli_" prefix
            return data

        # Assign behaviors
        compress_mock.gzip.side_effect = mock_gzip_compress
        compress_mock.gunzip.side_effect = mock_gzip_decompress
        compress_mock.brotli.side_effect = mock_brotli_compress
        compress_mock.brotli_decompress.side_effect = mock_brotli_decompress

        self._mock_instances["compress"] = compress_mock
        return compress_mock

    def create_encode_action_mock(
        self,
        behavior: dict[str, t.Any] | None = None,
    ) -> MagicMock:
        """Create a realistic encode action mock."""
        encode_mock = MagicMock()

        default_behavior = {
            "encoding_delay": 0.0005,  # 0.5ms encoding time
            "error_rate": 0.0,  # No errors by default
            "validate_json": True,  # Validate JSON structure
        }

        if behavior:
            default_behavior.update(behavior)

        # Assign behaviors using helper methods
        encode_mock.json_encode.side_effect = lambda data: self._mock_json_encode(
            data,
            default_behavior,
        )
        encode_mock.json_decode.side_effect = lambda data: self._mock_json_decode(
            data,
            default_behavior,
        )
        encode_mock.yaml_encode.side_effect = lambda data: self._mock_yaml_encode(
            data,
            default_behavior,
        )
        encode_mock.yaml_decode.side_effect = lambda data: self._mock_yaml_decode(
            data,
            default_behavior,
        )
        encode_mock.toml_encode.side_effect = lambda data: self._mock_toml_encode(
            data,
            default_behavior,
        )
        encode_mock.msgpack_encode.side_effect = lambda data: self._mock_msgpack_encode(
            data,
            default_behavior,
        )
        encode_mock.msgpack_decode.side_effect = lambda data: self._mock_msgpack_decode(
            data,
            default_behavior,
        )

        self._mock_instances["encode"] = encode_mock
        return encode_mock

    def _mock_json_encode(self, data: t.Any, behavior: dict[str, Any]) -> str:
        """Helper for JSON encoding mock."""
        import json
        import random
        import time

        time.sleep(behavior["encoding_delay"])

        if random.random() < behavior["error_rate"]:
            msg = "JSON encoding failed"
            raise ValueError(msg)

        if behavior["validate_json"]:
            try:
                return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            except TypeError as e:
                msg = f"Object not JSON serializable: {e}"
                raise ValueError(msg)
        else:
            return str(data)

    def _mock_json_decode(self, data: str, behavior: dict[str, Any]) -> t.Any:
        """Helper for JSON decoding mock."""
        import json
        import random
        import time

        time.sleep(behavior["encoding_delay"])

        if random.random() < behavior["error_rate"]:
            msg = "JSON decoding failed"
            raise ValueError(msg)

        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON: {e}"
            raise ValueError(msg)

    def _mock_yaml_encode(self, data: t.Any, behavior: dict[str, Any]) -> str:
        """Helper for YAML encoding mock."""
        import time

        time.sleep(behavior["encoding_delay"])

        # Simple YAML simulation
        if isinstance(data, dict):
            return "\n".join([f"{key}: {value}" for key, value in data.items()])
        return str(data)

    def _mock_yaml_decode(self, data: str, behavior: dict[str, Any]) -> t.Any:
        """Helper for YAML decoding mock."""
        import time

        time.sleep(behavior["encoding_delay"])

        # Simple YAML parsing simulation
        result = {}
        for line in data.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def _mock_toml_encode(self, data: dict[str, Any], behavior: dict[str, Any]) -> str:
        """Helper for TOML encoding mock."""
        import time

        time.sleep(behavior["encoding_delay"])

        # Simple TOML simulation
        lines = []
        for key, value in data.items():
            if isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            else:
                lines.append(f"{key} = {value}")
        return "\n".join(lines)

    def _mock_msgpack_encode(self, data: t.Any, behavior: dict[str, Any]) -> bytes:
        """Helper for msgpack encoding mock."""
        import time

        time.sleep(behavior["encoding_delay"])

        # Simple msgpack simulation (just use string representation)
        return f"msgpack:{data}".encode()

    def _mock_msgpack_decode(self, data: bytes, behavior: dict[str, Any]) -> t.Any:
        """Helper for msgpack decoding mock."""
        import time

        time.sleep(behavior["encoding_delay"])

        # Simple msgpack decoding simulation
        text = data.decode()
        if text.startswith("msgpack:"):
            # Very basic evaluation (unsafe, just for testing)
            return text[8:]
        return text

    def create_hash_action_mock(
        self,
        behavior: dict[str, t.Any] | None = None,
    ) -> MagicMock:
        """Create a realistic hash action mock."""
        hash_mock = MagicMock()

        default_behavior = {
            "hash_delay": 0.0001,  # 0.1ms hashing time
            "hash_length": 32,  # Default hash length
            "use_random_hashes": False,  # Use deterministic hashes for testing
        }

        if behavior:
            default_behavior.update(behavior)

        def mock_blake3_hash(data: bytes) -> str:
            import hashlib
            import time

            time.sleep(default_behavior["hash_delay"])

            if default_behavior["use_random_hashes"]:
                import random

                return "".join(random.choices("0123456789abcdef", k=64))
            # Use SHA256 as blake3 substitute for testing
            return hashlib.sha256(data).hexdigest()

        def mock_md5_hash(data: bytes) -> str:
            import hashlib
            import time

            time.sleep(default_behavior["hash_delay"])

            if default_behavior["use_random_hashes"]:
                import random

                return "".join(random.choices("0123456789abcdef", k=32))
            return hashlib.md5(data, usedforsecurity=False).hexdigest()

        def mock_crc32c_hash(data: bytes) -> str:
            import binascii
            import time

            time.sleep(default_behavior["hash_delay"])

            if default_behavior["use_random_hashes"]:
                import random

                return f"{random.randint(0, 2**32 - 1):08x}"
            # Use standard CRC32 as crc32c substitute
            return f"{binascii.crc32(data) & 0xFFFFFFFF:08x}"

        def mock_sha256_hash(data: bytes) -> str:
            import hashlib
            import time

            time.sleep(default_behavior["hash_delay"])

            if default_behavior["use_random_hashes"]:
                import random

                return "".join(random.choices("0123456789abcdef", k=64))
            return hashlib.sha256(data).hexdigest()

        # Assign behaviors
        hash_mock.blake3.side_effect = mock_blake3_hash
        hash_mock.md5.side_effect = mock_md5_hash
        hash_mock.crc32c.side_effect = mock_crc32c_hash
        hash_mock.sha256.side_effect = mock_sha256_hash

        self._mock_instances["hash"] = hash_mock
        return hash_mock

    def get_mock_instance(self, action_type: str) -> MagicMock | None:
        """Get a previously created mock instance."""
        return self._mock_instances.get(action_type)

    def reset_mocks(self) -> None:
        """Reset all mock instances and call history."""
        for mock in self._mock_instances.values():
            mock.reset_mock()
        self._call_history.clear()

    def get_call_history(self, action_type: str) -> list[t.Any]:
        """Get call history for a specific action type."""
        return list(self._call_history.get(action_type, []))

    def record_call(
        self,
        action_type: str,
        method: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        """Record a method call for analysis."""
        if action_type not in self._call_history:
            self._call_history[action_type] = []

        self._call_history[action_type].append(
            {
                "method": method,
                "args": args,
                "kwargs": kwargs,
                "timestamp": "2024-01-01T12:00:00Z",  # Mock timestamp
            },
        )

    @contextmanager
    def mock_action_context(
        self,
        action_type: str,
        behavior: dict[str, t.Any] | None = None,
    ) -> t.Generator[MagicMock]:
        """Context manager for temporary mock action."""
        # Create mock based on type
        if action_type == "compress":
            mock = self.create_compress_action_mock(behavior)
        elif action_type == "encode":
            mock = self.create_encode_action_mock(behavior)
        elif action_type == "hash":
            mock = self.create_hash_action_mock(behavior)
        else:
            msg = f"Unknown action type: {action_type}"
            raise ValueError(msg)

        try:
            yield mock
        finally:
            # Cleanup if needed
            pass

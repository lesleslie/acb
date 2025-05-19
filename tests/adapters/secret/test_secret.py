"""Tests for the Secret adapters.

This module contains tests for the Secret adapter implementations.
It extends the standard SecretTestInterface with additional tests
specific to the Secret adapter implementation.
"""

from unittest.mock import patch

import pytest
from tests.test_interfaces import MockSecret, SecretAdapterProtocol, SecretTestInterface


@pytest.fixture
async def secret() -> MockSecret:
    secret = MockSecret()
    await secret.init()
    return secret


class TestSecret(SecretTestInterface):
    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_error_handling(self, secret: SecretAdapterProtocol) -> None:
        with patch.object(secret, "get_secret", side_effect=Exception("Test error")):
            try:
                result = await secret.secret_exists("error_secret")
                assert not result
            except Exception:
                pytest.fail("secret_exists should handle exceptions gracefully")

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_multiple_operations(self, secret: SecretAdapterProtocol) -> None:
        await secret.set_secret("secret1", "value1")
        await secret.set_secret("secret2", "value2")
        await secret.set_secret("secret3", "value3")

        assert await secret.secret_exists("secret1")
        assert await secret.secret_exists("secret2")
        assert await secret.secret_exists("secret3")

        await secret.set_secret("secret2", "updated_value")

        await secret.delete_secret("secret3")

        assert await secret.get_secret("secret1") == "value1"
        assert await secret.get_secret("secret2") == "updated_value"
        assert not await secret.secret_exists("secret3")

        versions1 = await secret.list_versions("secret1")
        versions2 = await secret.list_versions("secret2")
        assert len(versions1) == 1
        assert len(versions2) == 2

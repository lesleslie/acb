"""Simplified tests for the Secret adapters."""

import pytest
from tests.test_interfaces import MockSecret, SecretTestInterface


@pytest.fixture
async def secret() -> MockSecret:
    secret = MockSecret()
    await secret.init()
    return secret


class TestSecret(SecretTestInterface):
    pass

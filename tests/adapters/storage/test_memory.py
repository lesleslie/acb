"""Simplified tests for the Memory Storage adapter."""

import pytest
from tests.test_interfaces import MockStorage, StorageTestInterface


@pytest.fixture
async def storage() -> MockStorage:
    storage = MockStorage()
    await storage.init()
    return storage


class TestMemoryStorage(StorageTestInterface):
    pass

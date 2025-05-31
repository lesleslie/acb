"""Tests for the Memory Storage adapter."""

import pytest
from tests.test_interfaces import MockStorage, StorageTestInterface


@pytest.fixture
async def storage():
    mock_storage = MockStorage()
    await mock_storage.init()
    return mock_storage


@pytest.mark.unit
class TestMemoryStorage(StorageTestInterface):
    pass

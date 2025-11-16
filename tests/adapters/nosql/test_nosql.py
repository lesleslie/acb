"""Simplified tests for the NoSQL adapters."""

import pytest

from tests.test_interfaces import MockNoSQL, NoSQLTestInterface


@pytest.fixture
async def nosql() -> MockNoSQL:
    nosql = MockNoSQL()
    await nosql.init()
    return nosql


class TestNoSQL(NoSQLTestInterface):
    pass

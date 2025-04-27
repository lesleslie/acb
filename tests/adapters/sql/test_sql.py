"""Simplified tests for the SQL adapters."""

import pytest
from tests.test_interfaces import MockSQL, SQLTestInterface


@pytest.fixture
async def sql() -> MockSQL:
    sql = MockSQL()
    await sql.init()
    return sql


class TestSQL(SQLTestInterface):
    pass

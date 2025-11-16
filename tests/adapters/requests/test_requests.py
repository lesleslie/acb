"""Simplified tests for the Requests adapters."""

import pytest

from tests.test_interfaces import MockRequests, RequestsTestInterface


@pytest.fixture
async def requests() -> MockRequests:
    requests = MockRequests()
    await requests.init()
    return requests


class TestRequests(RequestsTestInterface):
    pass

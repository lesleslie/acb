"""Simplified tests for the SMTP adapters."""

import pytest
from tests.test_interfaces import MockSMTP, SMTPTestInterface


@pytest.fixture
async def smtp() -> MockSMTP:
    smtp: MockSMTP = MockSMTP()
    await smtp.init()
    return smtp


class TestSMTP(SMTPTestInterface):
    pass

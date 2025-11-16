"""Simplified tests for the Monitoring adapters."""

import pytest

from tests.test_interfaces import MockMonitoring, MonitoringTestInterface


@pytest.fixture
async def monitoring() -> MockMonitoring:
    monitoring = MockMonitoring()
    await monitoring.init()
    return monitoring


class TestMonitoring(MonitoringTestInterface):
    pass

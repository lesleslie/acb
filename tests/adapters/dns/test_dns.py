"""Simplified tests for the DNS adapters."""

import pytest

from tests.test_interfaces import DNSTestInterface, MockDNS


@pytest.fixture
async def dns() -> MockDNS:
    dns: MockDNS = MockDNS()
    await dns.init()
    return dns


class TestDNS(DNSTestInterface):
    pass

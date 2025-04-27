"""Simplified tests for the FTPD adapters."""

import pytest
from tests.test_interfaces import FTPDTestInterface, MockFTPD


@pytest.fixture
async def ftpd() -> MockFTPD:
    ftpd = MockFTPD()
    await ftpd.init()
    return ftpd


class TestFTPD(FTPDTestInterface):
    pass

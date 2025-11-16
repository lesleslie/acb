"""Tests for the Cloud DNS adapter."""

from unittest.mock import MagicMock

import pytest

from acb.adapters.dns.gcdns import Dns, DnsSettings
from acb.config import Config


class TestCloudDnsSettings:
    def test_init_defaults(self) -> None:
        # The DnsSettings class is empty (...) so just test basic instantiation
        settings = DnsSettings()
        assert isinstance(settings, DnsSettings)


class TestCloudDns:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        config = MagicMock(spec=Config)
        config.app = MagicMock()
        config.app.project = "test-project"
        config.app.name = "test-app"
        config.app.domain = "example.com"
        return config

    @pytest.fixture
    def cloud_dns(self, mock_config: MagicMock) -> Dns:
        dns = Dns()
        dns.config = mock_config
        dns.logger = MagicMock()
        return dns

    @pytest.mark.asyncio
    async def test_init_test_mode(self, cloud_dns: Dns) -> None:
        # Test mode should set up mock client and zone
        await cloud_dns.init()

        assert hasattr(cloud_dns, "client")
        assert hasattr(cloud_dns, "zone")

    def test_create_zone_test_mode(self, cloud_dns: Dns) -> None:
        # In test mode, create_zone should return early
        cloud_dns.create_zone()

        # Should complete without error
        assert True

    def test_list_records_test_mode(self, cloud_dns: Dns) -> None:
        # In test mode, should return predefined test records
        records = cloud_dns.list_records()

        assert len(records) == 1
        assert records[0].name == "test.example.com."
        assert records[0].type == "A"
        assert records[0].ttl == 300
        assert records[0].rrdata == ["192.0.2.1"]

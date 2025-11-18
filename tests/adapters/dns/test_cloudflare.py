"""Tests for the Cloudflare DNS adapter."""

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

# Skip entire module if validators is not installed
pytest.importorskip("validators")

from acb.adapters.dns._base import DnsRecord
from acb.adapters.dns.cloudflare import Dns, DnsSettings
from acb.config import Config


class TestCloudflareDnsSettings:
    def test_init(self) -> None:
        settings = DnsSettings(
            api_email="test@example.com",
            api_key=SecretStr("test-api-key"),
            api_token=SecretStr("test-api-token"),
            account_id="test-account-id",
            zone_name="example.com",
            proxied=True,
            ttl=600,
        )
        assert settings.api_email == "test@example.com"
        assert settings.api_key.get_secret_value() == "test-api-key"
        assert settings.api_token.get_secret_value() == "test-api-token"
        assert settings.account_id == "test-account-id"
        assert settings.zone_name == "example.com"
        assert settings.proxied is True
        assert settings.ttl == 600

    def test_default_values(self) -> None:
        settings = DnsSettings()
        assert settings.api_email is None
        assert settings.api_key is None
        assert settings.api_token is None
        assert settings.account_id is None
        assert settings.zone_name is None
        assert settings.proxied is False
        assert settings.ttl == 300


class TestCloudflareDns:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        config = MagicMock(spec=Config)
        config.dns = MagicMock(spec=DnsSettings)
        config.dns.api_email = "test@example.com"
        config.dns.api_key = SecretStr("test-api-key")
        config.dns.api_token = SecretStr("test-api-token")
        config.dns.account_id = "test-account-id"
        config.dns.zone_name = "example.com"
        config.dns.proxied = False
        config.dns.ttl = 300
        config.app = MagicMock()
        config.app.domain = "example.com"
        return config

    @pytest.fixture
    def cloudflare_dns(self, mock_config: MagicMock) -> Dns:
        dns = Dns()
        dns.config = mock_config
        dns.logger = MagicMock()
        return dns

    @pytest.mark.asyncio
    async def test_init_test_mode(self, cloudflare_dns: Dns) -> None:
        # Test mode should set up mock client
        await cloudflare_dns.init()

        assert hasattr(cloudflare_dns, "client")
        assert cloudflare_dns.zone_id == "test-zone-id"

    @pytest.mark.asyncio
    async def test_get_zone_id(self, cloudflare_dns: Dns) -> None:
        # Set up mock client
        mock_client = MagicMock()
        mock_zone = MagicMock()
        mock_zone.id = "zone-456"
        mock_client.zones.list.return_value = [mock_zone]
        cloudflare_dns.client = mock_client

        await cloudflare_dns.get_zone_id()

        assert cloudflare_dns.zone_id == "zone-456"
        mock_client.zones.list.assert_called_once_with(name="example.com")

    def test_create_zone_success(self, cloudflare_dns: Dns) -> None:
        # Mock client and zone creation
        mock_client = MagicMock()
        mock_zone = MagicMock()
        mock_zone.id = "zone-new"
        mock_client.zones.create.return_value = mock_zone
        cloudflare_dns.client = mock_client
        cloudflare_dns.zone_id = None

        cloudflare_dns.create_zone()

        assert cloudflare_dns.zone_id == "zone-new"
        mock_client.zones.create.assert_called_once()

    def test_create_zone_already_exists(self, cloudflare_dns: Dns) -> None:
        cloudflare_dns.zone_id = "existing-zone"

        cloudflare_dns.create_zone()

        cloudflare_dns.logger.info.assert_called_once_with(
            "Zone 'example.com' already exists"
        )

    def test_create_zone_no_account_id(self, cloudflare_dns: Dns) -> None:
        cloudflare_dns.config.dns.account_id = None

        with pytest.raises(ValueError, match="Account ID is required to create a zone"):
            cloudflare_dns.create_zone()

    def test_list_records(self, cloudflare_dns: Dns) -> None:
        # Mock client and records
        mock_client = MagicMock()
        mock_record = MagicMock()
        mock_record.name = "test.example.com"
        mock_record.type = "A"
        mock_record.ttl = 300
        mock_record.content = "192.168.1.1"
        mock_client.dns.records.list.return_value = [mock_record]

        cloudflare_dns.client = mock_client
        cloudflare_dns.zone_id = "zone-123"

        records = cloudflare_dns.list_records()

        assert len(records) == 1
        assert records[0].name == "test.example.com"

    def test_list_records_no_zone_id(self, cloudflare_dns: Dns) -> None:
        cloudflare_dns.zone_id = None

        with pytest.raises(ValueError, match="Zone ID not found"):
            cloudflare_dns.list_records()

    def test_normalize_record(self, cloudflare_dns: Dns) -> None:
        record = DnsRecord(
            name="test.example.com", type="A", ttl=300, rrdata="192.168.1.1"
        )

        cloudflare_dns._normalize_record(record)

        assert record.name == "test.example.com."
        assert record.rrdata == ["192.168.1.1"]

"""Tests for the Route53 DNS adapter."""

from unittest.mock import MagicMock, patch

import pytest

from acb.adapters.dns._base import DnsRecord
from acb.adapters.dns.route53 import Dns, DnsSettings
from acb.config import Config


class TestRoute53DnsSettings:
    def test_init(self) -> None:
        settings = DnsSettings(
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            aws_region="us-west-2",
            zone_name="example.com",
            ttl=600,
        )
        assert settings.aws_access_key_id == "test-access-key"
        assert settings.aws_secret_access_key == "test-secret-key"
        assert settings.aws_region == "us-west-2"
        assert settings.zone_name == "example.com"
        assert settings.ttl == 600

    def test_default_values(self) -> None:
        settings = DnsSettings()
        assert settings.aws_region == "us-east-1"
        assert settings.ttl == 300


class TestRoute53Dns:
    @pytest.fixture
    def mock_boto3_client(self) -> MagicMock:
        mock_client = MagicMock()
        mock_client.list_hosted_zones_by_name = MagicMock()
        mock_client.list_resource_record_sets = MagicMock()
        mock_client.change_resource_record_sets = MagicMock()
        mock_client.get_hosted_zone = MagicMock()
        mock_client.get_waiter = MagicMock()
        return mock_client

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        config = MagicMock(spec=Config)
        config.dns = MagicMock(spec=DnsSettings)
        config.dns.aws_access_key_id = "test-access-key"
        config.dns.aws_secret_access_key = "test-secret-key"
        config.dns.aws_region = "us-east-1"
        config.dns.zone_name = "example.com"
        config.dns.ttl = 300
        return config

    @pytest.fixture
    def route53_dns(self, mock_config: MagicMock) -> Dns:
        with patch("acb.adapters.dns.route53._boto3_available", True):
            dns = Dns()
            dns.config = mock_config
            dns.logger = MagicMock()
            return dns

    def test_init_missing_boto3(self) -> None:
        with patch("acb.adapters.dns.route53._boto3_available", False):
            with pytest.raises(ImportError, match="boto3 not available"):
                Dns()

    @pytest.mark.asyncio
    async def test_create_client_with_credentials(self, route53_dns: Dns) -> None:
        with patch("acb.adapters.dns.route53.boto3") as mock_boto3:
            mock_session = MagicMock()
            mock_client = MagicMock()
            mock_session.client.return_value = mock_client
            mock_boto3.Session.return_value = mock_session

            client = await route53_dns._create_client()

            assert client == mock_client
            mock_boto3.Session.assert_called_once_with(
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
                region_name="us-east-1",
            )
            mock_session.client.assert_called_once_with("route53")

    @pytest.mark.asyncio
    async def test_create_client_without_credentials(self, route53_dns: Dns) -> None:
        route53_dns.config.dns.aws_access_key_id = None
        route53_dns.config.dns.aws_secret_access_key = None

        with patch("acb.adapters.dns.route53.boto3") as mock_boto3:
            mock_session = MagicMock()
            mock_client = MagicMock()
            mock_session.client.return_value = mock_client
            mock_boto3.Session.return_value = mock_session

            client = await route53_dns._create_client()

            assert client == mock_client
            mock_boto3.Session.assert_called_once_with(region_name="us-east-1")

    @pytest.mark.asyncio
    async def test_get_zone_id_success(
        self,
        route53_dns: Dns,
        mock_boto3_client: MagicMock,
    ) -> None:
        mock_boto3_client.list_hosted_zones_by_name.return_value = {
            "HostedZones": [
                {
                    "Id": "/hostedzone/Z1234567890",
                    "Name": "example.com.",
                    "ResourceRecordSetCount": 10,
                }
            ]
        }

        route53_dns._client = mock_boto3_client

        zone_id = await route53_dns._get_zone_id()

        assert zone_id == "Z1234567890"
        assert route53_dns.zone_id == "Z1234567890"
        mock_boto3_client.list_hosted_zones_by_name.assert_called_once_with(
            DNSName="example.com"
        )

    @pytest.mark.asyncio
    async def test_get_zone_id_not_found(
        self,
        route53_dns: Dns,
        mock_boto3_client: MagicMock,
    ) -> None:
        mock_boto3_client.list_hosted_zones_by_name.return_value = {"HostedZones": []}

        route53_dns._client = mock_boto3_client

        with pytest.raises(ValueError, match="Hosted zone not found"):
            await route53_dns._get_zone_id()

    @pytest.mark.asyncio
    async def test_get_zone_id_no_zone_name(self, route53_dns: Dns) -> None:
        route53_dns.config.dns.zone_name = None

        with pytest.raises(ValueError, match="Zone name is required"):
            await route53_dns._get_zone_id()

    @pytest.mark.asyncio
    async def test_init_success(self, route53_dns: Dns) -> None:
        mock_logger = MagicMock()
        # Patch sys.modules to exclude pytest for this test
        with (
            patch("sys.modules", {}),
            patch("acb.adapters.dns.route53.os.getenv", return_value="False"),
            patch.object(route53_dns, "get_client") as mock_get_client,
            patch.object(route53_dns, "_get_zone_id") as mock_get_zone_id,
        ):
            mock_get_client.return_value = MagicMock()
            mock_get_zone_id.return_value = "Z1234567890"

            await route53_dns.init(logger=mock_logger)

            mock_get_client.assert_called_once()
            mock_get_zone_id.assert_called_once()
            mock_logger.info.assert_called_once_with(
                "Route53 DNS adapter initialized for zone: example.com"
            )

    @pytest.mark.asyncio
    async def test_init_failure(self, route53_dns: Dns) -> None:
        mock_logger = MagicMock()
        # Patch sys.modules to exclude pytest for this test
        with (
            patch("sys.modules", {}),
            patch("acb.adapters.dns.route53.os.getenv", return_value="False"),
            patch.object(route53_dns, "get_client") as mock_get_client,
        ):
            mock_get_client.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await route53_dns.init(logger=mock_logger)

            mock_logger.exception.assert_called_once_with(
                "Failed to initialize Route53 DNS adapter: Connection failed"
            )

    def test_create_zone_not_implemented(self, route53_dns: Dns) -> None:
        with pytest.raises(NotImplementedError, match="Zone creation should be done"):
            route53_dns.create_zone()

    def test_list_records(
        self,
        route53_dns: Dns,
        mock_boto3_client: MagicMock,
    ) -> None:
        # Patch to disable test mode for this test
        with (
            patch("sys.modules", {}),
            patch("acb.adapters.dns.route53.os.getenv", return_value="False"),
        ):
            mock_boto3_client.list_resource_record_sets.return_value = {
                "ResourceRecordSets": [
                    {
                        "Name": "test.example.com.",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "192.168.1.1"}],
                    },
                    {
                        "Name": "txt.example.com.",
                        "Type": "TXT",
                        "TTL": 600,
                        "ResourceRecords": [{"Value": '"test-txt-record"'}],
                    },
                    {
                        "Name": "example.com.",
                        "Type": "NS",
                        "TTL": 172800,
                        "ResourceRecords": [{"Value": "ns1.example.com"}],
                    },
                ]
            }

            route53_dns._client = mock_boto3_client
            route53_dns.zone_id = "Z1234567890"

            records = route53_dns.list_records()

            # Should exclude NS records for the zone itself
            assert len(records) == 2

            # Check A record
            assert records[0].name == "test.example.com"
            assert records[0].type == "A"
            assert records[0].ttl == 300
            assert records[0].rrdata == "192.168.1.1"

            # Check TXT record
            assert records[1].name == "txt.example.com"
            assert records[1].type == "TXT"
            assert records[1].ttl == 600
            assert records[1].rrdata == '"test-txt-record"'

            mock_boto3_client.list_resource_record_sets.assert_called_once_with(
                HostedZoneId="Z1234567890"
            )

    @pytest.mark.asyncio
    async def test_create_records_single(
        self,
        route53_dns: Dns,
        mock_boto3_client: MagicMock,
    ) -> None:
        # Patch to disable test mode for this test
        with (
            patch("sys.modules", {}),
            patch("acb.adapters.dns.route53.os.getenv", return_value="False"),
        ):
            # Mock waiter
            mock_waiter = MagicMock()
            mock_boto3_client.get_waiter.return_value = mock_waiter

            mock_boto3_client.change_resource_record_sets.return_value = {
                "ChangeInfo": {"Id": "C1234567890"}
            }

            route53_dns._client = mock_boto3_client
            route53_dns.zone_id = "Z1234567890"

            record = DnsRecord(
                name="test.example.com", type="A", ttl=300, rrdata="192.168.1.1"
            )

            await route53_dns.create_records(record)

            mock_boto3_client.change_resource_record_sets.assert_called_once()
            call_args = mock_boto3_client.change_resource_record_sets.call_args[1]

            assert call_args["HostedZoneId"] == "Z1234567890"
            assert len(call_args["ChangeBatch"]["Changes"]) == 1

            change = call_args["ChangeBatch"]["Changes"][0]
            assert change["Action"] == "UPSERT"
            assert change["ResourceRecordSet"]["Name"] == "test.example.com"
            assert change["ResourceRecordSet"]["Type"] == "A"
            assert change["ResourceRecordSet"]["TTL"] == 300
            assert change["ResourceRecordSet"]["ResourceRecords"] == [
                {"Value": "192.168.1.1"}
            ]

            mock_waiter.wait.assert_called_once_with(
                Id="C1234567890", WaiterConfig={"Delay": 10, "MaxAttempts": 30}
            )

    @pytest.mark.asyncio
    async def test_create_records_multiple(
        self,
        route53_dns: Dns,
        mock_boto3_client: MagicMock,
    ) -> None:
        # Patch to disable test mode for this test
        with (
            patch("sys.modules", {}),
            patch("acb.adapters.dns.route53.os.getenv", return_value="False"),
        ):
            # Mock waiter
            mock_waiter = MagicMock()
            mock_boto3_client.get_waiter.return_value = mock_waiter

            mock_boto3_client.change_resource_record_sets.return_value = {
                "ChangeInfo": {"Id": "C1234567890"}
            }

            route53_dns._client = mock_boto3_client
            route53_dns.zone_id = "Z1234567890"

            records = [
                DnsRecord(
                    name="test1.example.com", type="A", ttl=300, rrdata="192.168.1.1"
                ),
                DnsRecord(
                    name="test2.example.com",
                    type="A",
                    ttl=300,
                    rrdata=["192.168.1.2", "192.168.1.3"],
                ),
            ]

            await route53_dns.create_records(records)

            mock_boto3_client.change_resource_record_sets.assert_called_once()
            call_args = mock_boto3_client.change_resource_record_sets.call_args[1]

            assert len(call_args["ChangeBatch"]["Changes"]) == 2

            # Check first record
            change1 = call_args["ChangeBatch"]["Changes"][0]
            assert change1["ResourceRecordSet"]["ResourceRecords"] == [
                {"Value": "192.168.1.1"}
            ]

            # Check second record (multiple values)
            change2 = call_args["ChangeBatch"]["Changes"][1]
            assert change2["ResourceRecordSet"]["ResourceRecords"] == [
                {"Value": "192.168.1.2"},
                {"Value": "192.168.1.3"},
            ]

    @pytest.mark.asyncio
    async def test_delete_records(
        self,
        route53_dns: Dns,
        mock_boto3_client: MagicMock,
    ) -> None:
        # Patch to disable test mode for this test
        with (
            patch("sys.modules", {}),
            patch("acb.adapters.dns.route53.os.getenv", return_value="False"),
        ):
            mock_boto3_client.change_resource_record_sets.return_value = {
                "ChangeInfo": {"Id": "C1234567890"}
            }

            route53_dns._client = mock_boto3_client
            route53_dns.zone_id = "Z1234567890"

            record = DnsRecord(
                name="test.example.com", type="A", ttl=300, rrdata="192.168.1.1"
            )

            await route53_dns.delete_records(record)

            mock_boto3_client.change_resource_record_sets.assert_called_once()
            call_args = mock_boto3_client.change_resource_record_sets.call_args[1]

            assert call_args["HostedZoneId"] == "Z1234567890"
            assert len(call_args["ChangeBatch"]["Changes"]) == 1

            change = call_args["ChangeBatch"]["Changes"][0]
            assert change["Action"] == "DELETE"
            assert change["ResourceRecordSet"]["Name"] == "test.example.com"

    @pytest.mark.asyncio
    async def test_get_zone_info(
        self,
        route53_dns: Dns,
        mock_boto3_client: MagicMock,
    ) -> None:
        mock_boto3_client.get_hosted_zone.return_value = {
            "HostedZone": {
                "Name": "example.com.",
                "ResourceRecordSetCount": 10,
                "Config": {"PrivateZone": False, "Comment": "Test zone"},
            }
        }

        route53_dns._client = mock_boto3_client
        route53_dns.zone_id = "Z1234567890"

        zone_info = await route53_dns.get_zone_info()

        assert zone_info["zone_id"] == "Z1234567890"
        assert zone_info["name"] == "example.com."
        assert zone_info["record_count"] == 10
        assert zone_info["private_zone"] is False
        assert zone_info["comment"] == "Test zone"

        mock_boto3_client.get_hosted_zone.assert_called_once_with(Id="Z1234567890")

    def test_client_property_not_initialized(self, route53_dns: Dns) -> None:
        route53_dns._client = None

        with pytest.raises(RuntimeError, match="Client not initialized"):
            route53_dns.client

    def test_client_property_initialized(self, route53_dns: Dns) -> None:
        mock_client = MagicMock()
        route53_dns._client = mock_client

        assert route53_dns.client == mock_client

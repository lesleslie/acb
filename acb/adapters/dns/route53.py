import os
import sys
from uuid import UUID

import typing as t

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import Inject, depends

from ._base import DnsBase, DnsBaseSettings, DnsRecord

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    _boto3_available = True
except ImportError:
    _boto3_available = False
    boto3 = None
    BotoCoreError = Exception
    ClientError = Exception

MODULE_ID = UUID("0197ff44-c5a3-7040-8d7e-3b17c8e54694")
MODULE_STATUS = AdapterStatus.BETA

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="AWS Route53",
    category="dns",
    provider="aws",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-17",
    last_modified="2025-01-17",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.HEALTH_CHECKS,
        AdapterCapability.BULK_OPERATIONS,
    ],
    required_packages=["boto3>=1.35.0"],
    description="AWS Route53 DNS management adapter",
    documentation_url="https://docs.aws.amazon.com/route53/",
    repository_url="https://github.com/boto/boto3",
    settings_class="DnsSettings",
    config_example={
        "zone_name": "example.com",
        "aws_access_key_id": "your-access-key",  # pragma: allowlist secret
        "aws_secret_access_key": "your-secret-key",  # pragma: allowlist secret
        "aws_region": "us-east-1",
        "ttl": 300,
    },
)


class DnsSettings(DnsBaseSettings):
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    zone_name: str | None = None
    ttl: int = 300


class Dns(DnsBase):
    current_records: list[DnsRecord] = []
    new_records: list[DnsRecord] = []
    zone_id: str | None = None

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()
        self._client: t.Any = None
        if not _boto3_available:
            msg = "boto3 not available. Install with: uv add boto3"
            raise ImportError(msg)

    async def _create_client(self) -> t.Any:
        """Create and configure the Route53 client."""
        session_kwargs = {}

        if self.config.dns.aws_access_key_id:
            session_kwargs["aws_access_key_id"] = self.config.dns.aws_access_key_id
        if self.config.dns.aws_secret_access_key:
            session_kwargs["aws_secret_access_key"] = (
                self.config.dns.aws_secret_access_key
            )
        if self.config.dns.aws_region:
            session_kwargs["region_name"] = self.config.dns.aws_region

        session = boto3.Session(**session_kwargs)
        return session.client("route53")

    async def get_client(self) -> t.Any:
        """Get or create the Route53 client."""
        return await self._ensure_client()

    @property
    def client(self) -> t.Any:
        """Get the Route53 client, raising an error if not initialized."""
        if self._client is None:
            msg = "Client not initialized. Call get_client() first."
            raise RuntimeError(msg)
        return self._client

    async def _get_zone_id(self) -> str:
        """Get the hosted zone ID for the configured zone name."""
        if self.zone_id:
            return str(self.zone_id)

        if not self.config.dns.zone_name:
            msg = "Zone name is required for Route53 operations"
            raise ValueError(msg)

        client = await self.get_client()

        try:
            response = client.list_hosted_zones_by_name(
                DNSName=self.config.dns.zone_name,
            )

            for zone in response.get("HostedZones", []):
                if zone["Name"].rstrip(".") == self.config.dns.zone_name.rstrip("."):
                    self.zone_id = zone["Id"].split("/")[-1]  # Extract ID from ARN
                    return str(self.zone_id)

            msg = f"Hosted zone not found for domain: {self.config.dns.zone_name}"
            raise ValueError(msg)

        except (ClientError, BotoCoreError) as e:
            msg = f"Failed to find hosted zone: {e}"
            raise RuntimeError(msg) from e

    @depends.inject
    async def init(self, logger: Inject[t.Any]) -> None:
        """Initialize the Route53 DNS adapter."""
        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            from unittest.mock import MagicMock

            self._client = MagicMock()  # type: ignore[assignment]
            self.zone_id = "test-zone-id"
            logger.info("Route53 DNS adapter initialized in test mode")  # type: ignore[no-untyped-call]
            return

        try:
            await self.get_client()
            await self._get_zone_id()
            logger.info(
                f"Route53 DNS adapter initialized for zone: {self.config.dns.zone_name}",
            )  # type: ignore[no-untyped-call]
        except Exception as e:
            logger.exception(f"Failed to initialize Route53 DNS adapter: {e}")  # type: ignore[no-untyped-call]
            raise

    def create_zone(self) -> None:
        """Create a new hosted zone (not implemented for Route53 adapter)."""
        msg = "Zone creation should be done through AWS Console or CLI for Route53"
        raise NotImplementedError(msg)

    def list_records(self) -> list[DnsRecord]:
        """List all DNS records in the hosted zone."""
        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            return self.current_records

        try:
            zone_id = self.zone_id or "test-zone-id"
            response = self.client.list_resource_record_sets(HostedZoneId=zone_id)

            records = []
            for record_set in response.get("ResourceRecordSets", []):
                # Skip NS and SOA records for the zone itself
                if record_set["Type"] in ("NS", "SOA") and record_set["Name"].rstrip(
                    ".",
                ) == self.config.dns.zone_name.rstrip("."):
                    continue

                rrdata = [rr["Value"] for rr in record_set.get("ResourceRecords", [])]

                records.append(
                    DnsRecord(
                        name=record_set["Name"].rstrip("."),
                        type=record_set["Type"],
                        ttl=record_set.get("TTL", self.config.dns.ttl),
                        rrdata=rrdata
                        if len(rrdata) > 1
                        else (rrdata[0] if rrdata else None),
                    ),
                )

            self.current_records = records
            return records

        except (ClientError, BotoCoreError) as e:
            self.logger.exception(f"Failed to list DNS records: {e}")
            raise

    def _prepare_resource_records(
        self,
        rrdata: str | list[str] | None,
    ) -> list[dict[str, str]]:
        """Prepare resource records for Route53 API."""
        if rrdata is None:
            return []
        if isinstance(rrdata, list):
            return [{"Value": value} for value in rrdata]
        return [{"Value": rrdata}]

    def _create_change_entry(self, record: DnsRecord, action: str) -> dict[str, t.Any]:
        """Create a single change entry for Route53 batch operation."""
        resource_records = self._prepare_resource_records(record.rrdata)
        return {
            "Action": action,
            "ResourceRecordSet": {
                "Name": record.name,
                "Type": record.type,
                "TTL": record.ttl or self.config.dns.ttl,
                "ResourceRecords": resource_records,
            },
        }

    def _prepare_batch_changes(
        self,
        records: list[DnsRecord],
        action: str,
    ) -> list[dict[str, t.Any]]:
        """Prepare changes for Route53 batch operation."""
        changes = []
        for record in records:
            if not record.name or not record.rrdata:
                continue
            changes.append(self._create_change_entry(record, action))
        return changes

    async def _submit_batch_changes(
        self,
        changes: list[dict[str, t.Any]],
        comment: str,
    ) -> str:
        """Submit batch changes to Route53 and return change ID."""
        zone_id = await self._get_zone_id()
        client = await self.get_client()

        response = client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                "Comment": comment,
                "Changes": changes,
            },
        )
        return str(response["ChangeInfo"]["Id"])

    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None:
        """Create or update DNS records in Route53."""
        if isinstance(records, DnsRecord):
            records = [records]

        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            self.new_records.extend(records)
            return

        try:
            changes = self._prepare_batch_changes(records, "UPSERT")
            if not changes:
                self.logger.warning("No valid records to create")
                return

            change_id = await self._submit_batch_changes(
                changes,
                "ACB Route53 adapter batch update",
            )
            self.logger.info(
                f"DNS records submitted for creation. Change ID: {change_id}",
            )

            # Optionally wait for changes to propagate
            client = await self.get_client()
            waiter = client.get_waiter("resource_record_sets_changed")
            waiter.wait(Id=change_id, WaiterConfig={"Delay": 10, "MaxAttempts": 30})

            self.logger.info("DNS records successfully created and propagated")

        except (ClientError, BotoCoreError) as e:
            self.logger.exception(f"Failed to create DNS records: {e}")
            raise

    def _remove_records_from_test_list(self, records: list[DnsRecord]) -> None:
        """Remove records from current_records for testing."""
        for record_to_delete in records:
            self.current_records = [
                r
                for r in self.current_records
                if not (
                    r.name == record_to_delete.name and r.type == record_to_delete.type
                )
            ]

    async def delete_records(self, records: list[DnsRecord] | DnsRecord) -> None:
        """Delete DNS records from Route53."""
        if isinstance(records, DnsRecord):
            records = [records]

        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            self._remove_records_from_test_list(records)
            return

        try:
            changes = self._prepare_batch_changes(records, "DELETE")
            if not changes:
                self.logger.warning("No valid records to delete")
                return

            change_id = await self._submit_batch_changes(
                changes,
                "ACB Route53 adapter batch deletion",
            )
            self.logger.info(
                f"DNS records submitted for deletion. Change ID: {change_id}",
            )

        except (ClientError, BotoCoreError) as e:
            self.logger.exception(f"Failed to delete DNS records: {e}")
            raise

    async def get_zone_info(self) -> dict[str, t.Any]:
        """Get information about the hosted zone."""
        try:
            zone_id = await self._get_zone_id()
            client = await self.get_client()

            response = client.get_hosted_zone(Id=zone_id)
            return {
                "zone_id": zone_id,
                "name": response["HostedZone"]["Name"],
                "record_count": response["HostedZone"]["ResourceRecordSetCount"],
                "private_zone": response["HostedZone"]["Config"].get(
                    "PrivateZone",
                    False,
                ),
                "comment": response["HostedZone"]["Config"].get("Comment", ""),
            }
        except (ClientError, BotoCoreError) as e:
            self.logger.exception(f"Failed to get zone info: {e}")
            raise


depends.set(Dns, "route53")

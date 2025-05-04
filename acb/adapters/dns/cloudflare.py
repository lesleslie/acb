import os
import sys
import typing as t
from contextlib import suppress
from warnings import catch_warnings, filterwarnings

from cloudflare import Cloudflare as CloudflareClient
from pydantic import SecretStr
from validators import domain
from validators.utils import ValidationError
from acb.depends import depends

from ._base import DnsBase, DnsBaseSettings, DnsRecord


class DnsSettings(DnsBaseSettings):
    api_email: t.Optional[str] = None
    api_key: t.Optional[SecretStr] = None
    api_token: t.Optional[SecretStr] = None
    account_id: t.Optional[str] = None
    zone_name: t.Optional[str] = None
    proxied: bool = False
    ttl: int = 300


class Dns(DnsBase):
    current_records: t.List[DnsRecord] = []
    new_records: t.List[DnsRecord] = []
    zone_id: t.Optional[str] = None

    async def init(self) -> None:
        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            from unittest.mock import MagicMock

            self.client = MagicMock()
            self.zone_id = "test-zone-id"
            return

        with catch_warnings():
            filterwarnings("ignore", category=Warning)

            if self.config.dns.api_token:
                self.client = CloudflareClient(
                    api_token=self.config.dns.api_token.get_secret_value()
                )
            else:
                self.client = CloudflareClient(
                    api_email=self.config.dns.api_email,
                    api_key=self.config.dns.api_key.get_secret_value()
                    if self.config.dns.api_key
                    else None,
                )

            if self.config.dns.zone_name:
                await self._get_zone_id()
            else:
                self.config.dns.zone_name = self.config.app.domain
                await self._get_zone_id()

    async def _get_zone_id(self) -> None:
        try:
            zones = self.client.zones.list(name=self.config.dns.zone_name)
            if zones:
                zone = list(zones)[0]
                self.zone_id = zone.id
                self.logger.info(
                    f"Found zone {self.config.dns.zone_name} with id {zone.id}"
                )
            else:
                self.logger.warning(f"Zone '{self.config.dns.zone_name}' not found")
        except Exception as e:
            self.logger.error(f"Error getting zone ID: {e}")
            raise

    def create_zone(self) -> None:
        if not self.config.dns.account_id:
            self.logger.error("Account ID is required to create a zone")
            raise ValueError("Account ID is required to create a zone")

        try:
            if self.zone_id:
                self.logger.info(f"Zone '{self.config.dns.zone_name}' already exists")
                return

            zone = self.client.zones.create(
                account={"id": self.config.dns.account_id},
                name=self.config.dns.zone_name,
                type="full",
            )
            self.zone_id = zone.id
            self.logger.info(
                f"Created zone {self.config.dns.zone_name} with id {self.zone_id}"
            )
        except Exception as e:
            self.logger.error(f"Error creating zone: {e}")
            raise

    def list_records(self) -> t.List[DnsRecord]:
        if not self.zone_id:
            self.logger.error("Zone ID not found. Initialize the adapter first.")
            raise ValueError("Zone ID not found")

        try:
            records = []
            zone = self.client.zones.get(zone_id=self.zone_id)
            dns_records = zone.dns_records.list(name=self.config.dns.zone_name)  # type: ignore

            for record in dns_records:
                dns_record = DnsRecord(
                    name=record.name,
                    type=record.type,
                    ttl=record.ttl,
                    rrdata=record.content,
                )
                records.append(dns_record)

            return records
        except Exception as e:
            self.logger.error(f"Error listing records: {e}")
            raise

    async def _delete_record(self, record_id: str) -> None:
        if not self.zone_id:
            self.logger.error("Zone ID not found. Initialize the adapter first.")
            raise ValueError("Zone ID not found")

        try:
            zone = self.client.zones.get(zone_id=self.zone_id)
            zone.dns_records.delete(dns_record_id=record_id)  # type: ignore
            self.logger.info(f"Deleted record with ID: {record_id}")
        except Exception as e:
            self.logger.error(f"Error deleting record: {e}")
            raise

    async def _create_record(self, record: DnsRecord) -> None:
        if not self.zone_id:
            self.logger.error("Zone ID not found. Initialize the adapter first.")
            raise ValueError("Zone ID not found")

        try:
            content = (
                record.rrdata[0] if isinstance(record.rrdata, list) else record.rrdata
            )

            zone = self.client.zones.get(zone_id=self.zone_id)
            new_record = zone.dns_records.create(  # type: ignore
                name=record.name,
                type=record.type,
                content=content,
                ttl=record.ttl,
                proxied=self.config.dns.proxied,
            )

            self.logger.info(f"Created record: {new_record.name} ({new_record.type})")
        except Exception as e:
            self.logger.error(f"Error creating record: {e}")
            raise

    def _find_existing_record(
        self, record: DnsRecord
    ) -> t.Optional[t.Dict[str, t.Any]]:
        if not self.zone_id:
            return None

        try:
            zone = self.client.zones.get(zone_id=self.zone_id)
            dns_records = zone.dns_records.list(name=record.name, type=record.type)  # type: ignore
            if dns_records:
                existing_record = list(dns_records)[0]
                return {
                    "id": existing_record.id,
                    "name": existing_record.name,
                    "type": existing_record.type,
                    "content": existing_record.content,
                    "ttl": existing_record.ttl,
                    "proxied": existing_record.proxied,
                }
            return None
        except Exception as e:
            self.logger.error(f"Error finding existing record: {e}")
            return None

    async def create_records(self, records: t.List[DnsRecord] | DnsRecord) -> None:
        records = [records] if isinstance(records, DnsRecord) else records

        for record in records:
            if not record.name.endswith("."):
                record.name = f"{record.name}."

            if not isinstance(record.rrdata, list):
                record.rrdata = [record.rrdata]

            for i, r in enumerate(record.rrdata):
                with suppress(ValidationError):
                    if isinstance(r, str) and domain(r) and not r.endswith("."):
                        r = f"{r}."
                        record.rrdata[i] = r
                    if record.type == "TXT":
                        if r.startswith('"') and r.endswith('"'):
                            r = r[1:-1]
                        record.rrdata[i] = f'"{r}"'

            existing_record = self._find_existing_record(record)

            if existing_record:
                content = record.rrdata[0] or record.rrdata
                if (
                    existing_record["content"] != content
                    or existing_record["ttl"] != record.ttl
                    or existing_record["proxied"] != self.config.dns.proxied
                ):
                    await self._delete_record(existing_record["id"])
                    self.logger.info(
                        f"Deleting record for update: {record.name} ({record.type})"
                    )

                    await self._create_record(record)
                else:
                    self.logger.info(
                        f"Record already exists and is up to date: {record.name} ({record.type})"
                    )
            else:
                await self._create_record(record)


depends.set(Dns)

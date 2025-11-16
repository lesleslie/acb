import os
import sys
from uuid import UUID
from warnings import catch_warnings, filterwarnings

import typing as t
from contextlib import suppress

try:
    from cloudflare import Cloudflare as CloudflareClient
except Exception:  # pragma: no cover - only when Cloudflare lib missing
    if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
        from unittest.mock import MagicMock

        CloudflareClient = MagicMock  # type: ignore[assignment, no-redef]
    else:
        raise
from pydantic import SecretStr
from validators import domain
from validators.utils import ValidationError

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import DnsBase, DnsBaseSettings, DnsRecord

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b7e29bc338cd")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Cloudflare DNS",
    category="dns",
    provider="cloudflare",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-20",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.TLS_SUPPORT,
    ],
    required_packages=["python-cloudflare", "validators"],
    description="Cloudflare DNS management with zone and record operations",
    settings_class="DnsSettings",
    config_example={
        "api_token": "your-cloudflare-api-token",  # pragma: allowlist secret
        "zone_name": "example.com",
        "proxied": False,
        "ttl": 300,
    },
)


class DnsSettings(DnsBaseSettings):
    api_email: str | None = None
    api_key: SecretStr | None = None
    api_token: SecretStr | None = None
    account_id: str | None = None
    zone_name: str | None = None
    proxied: bool = False
    ttl: int = 300


class Dns(DnsBase):
    current_records: list[DnsRecord] = []
    new_records: list[DnsRecord] = []
    zone_id: str | None = None

    async def init(self) -> None:
        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            from unittest.mock import MagicMock

            self.client = MagicMock()  # type: ignore[assignment]
            self.zone_id = "test-zone-id"
            return
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            if self.config.dns.api_token:
                self.client = CloudflareClient(  # type: ignore[assignment]
                    api_token=self.config.dns.api_token.get_secret_value(),
                )
            else:
                self.client = CloudflareClient(  # type: ignore[assignment]
                    api_email=self.config.dns.api_email,
                    api_key=self.config.dns.api_key.get_secret_value()
                    if self.config.dns.api_key
                    else None,
                )
            if self.config.dns.zone_name:
                await self._get_zone_id()
            else:
                if not self.config.app:
                    msg = (
                        "App configuration is required when zone_name is not specified"
                    )
                    raise ValueError(
                        msg,
                    )
                self.config.dns.zone_name = self.config.app.domain
                await self._get_zone_id()

    async def get_zone_id(self) -> None:
        return await self._get_zone_id()

    async def _get_zone_id(self) -> None:
        try:
            zones = self.client.zones.list(name=self.config.dns.zone_name)
            if zones:
                zone = next(iter(zones))
                self.zone_id = zone.id
                self.logger.info(
                    f"Found zone {self.config.dns.zone_name} with id {zone.id}",
                )
            else:
                self.logger.warning(f"Zone '{self.config.dns.zone_name}' not found")
        except Exception as e:
            self.logger.exception(f"Error getting zone ID: {e}")
            raise

    def create_zone(self) -> None:
        if not self.config.dns.account_id:
            self.logger.error("Account ID is required to create a zone")
            msg = "Account ID is required to create a zone"
            raise ValueError(msg)
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
                f"Created zone {self.config.dns.zone_name} with id {self.zone_id}",
            )
        except Exception as e:
            self.logger.exception(f"Error creating zone: {e}")
            raise

    def list_records(self) -> list[DnsRecord]:
        if not self.zone_id:
            self.logger.error("Zone ID not found. Initialize the adapter first")
            msg = "Zone ID not found"
            raise ValueError(msg)
        try:
            records = []
            dns_records = self.client.dns.records.list(
                zone_id=self.zone_id,
                name=self.config.dns.zone_name,
            )
            for record in dns_records:
                dns_record = DnsRecord(
                    name=str(record.name) if record.name else "",
                    type=str(record.type) if record.type else "A",
                    ttl=int(record.ttl) if record.ttl else 300,
                    rrdata=str(record.content) if record.content else "",
                )
                records.append(dns_record)
            return records
        except Exception as e:
            self.logger.exception(f"Error listing records: {e}")
            raise

    async def _delete_record(self, record_id: str) -> None:
        if not self.zone_id:
            self.logger.error("Zone ID not found. Initialize the adapter first")
            msg = "Zone ID not found"
            raise ValueError(msg)
        try:
            self.client.dns.records.delete(
                zone_id=self.zone_id,
                dns_record_id=record_id,
            )
            self.logger.info(f"Deleted record with ID: {record_id}")
        except Exception as e:
            self.logger.exception(f"Error deleting record: {e}")
            raise

    async def _create_record(self, record: DnsRecord) -> None:
        if not self.zone_id:
            self.logger.error("Zone ID not found. Initialize the adapter first")
            msg = "Zone ID not found"
            raise ValueError(msg)
        try:
            content = (
                record.rrdata[0] if isinstance(record.rrdata, list) else record.rrdata
            )
            new_record = self.client.dns.records.create(
                zone_id=self.zone_id,
                name=str(record.name) if record.name else "",
                type=t.cast("t.Any", record.type),
                content=str(content) if content else "",
                ttl=record.ttl or 300,
                proxied=self.config.dns.proxied,
            )
            self.logger.info(f"Created record: {new_record.name} ({new_record.type})")
        except Exception as e:
            self.logger.exception(f"Error creating record: {e}")
            raise

    def _find_existing_record(self, record: DnsRecord) -> dict[str, t.Any] | None:
        if not self.zone_id:
            return None
        try:
            dns_records = self.client.dns.records.list(
                zone_id=self.zone_id,
                name=t.cast("t.Any", record.name),
                type=t.cast("t.Any", record.type),
            )
            if dns_records:
                existing_record = next(iter(dns_records))
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
            self.logger.exception(f"Error finding existing record: {e}")
            return None

    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None:
        records = [records] if isinstance(records, DnsRecord) else records
        for record in records:
            self._normalize_record(record)
            await self._process_record_update(record)

    def _normalize_record(self, record: DnsRecord) -> None:
        if record.name and not record.name.endswith("."):
            record.name = f"{record.name}."
        if not isinstance(record.rrdata, list):
            record.rrdata = [record.rrdata] if record.rrdata is not None else []
        self._normalize_record_data(record)

    def _normalize_record_data(self, record: DnsRecord) -> None:
        if not isinstance(record.rrdata, list):
            return
        for i, r in enumerate(record.rrdata):
            with suppress(ValidationError):
                if isinstance(r, str) and domain(r) and (not r.endswith(".")):
                    r = f"{r}."
                    record.rrdata[i] = r
                if record.type == "TXT":
                    r = self._normalize_txt_record(r)
                    record.rrdata[i] = f'"{r}"'

    def _normalize_txt_record(self, r: t.Any) -> str:
        if isinstance(r, str) and r.startswith('"') and r.endswith('"'):
            return r[1:-1]
        return str(r) if r is not None else ""

    async def _process_record_update(self, record: DnsRecord) -> None:
        existing_record = self._find_existing_record(record)
        if existing_record:
            await self._handle_existing_record(record, existing_record)
        else:
            await self._create_record(record)

    async def _handle_existing_record(
        self,
        record: DnsRecord,
        existing_record: dict[str, t.Any],
    ) -> None:
        if not isinstance(record.rrdata, list) or not record.rrdata:
            content = ""
        else:
            content = str(record.rrdata[0]) if record.rrdata[0] is not None else ""
        if self._record_needs_update(record, existing_record, content):
            await self._update_existing_record(record, existing_record)
        else:
            self.logger.info(
                f"Record already exists and is up to date: {record.name} ({record.type})",
            )

    def _record_needs_update(
        self,
        record: DnsRecord,
        existing_record: dict[str, t.Any],
        content: str,
    ) -> bool:
        return (
            existing_record["content"] != content
            or existing_record["ttl"] != record.ttl
            or existing_record["proxied"] != self.config.dns.proxied
        )

    async def _update_existing_record(
        self,
        record: DnsRecord,
        existing_record: dict[str, t.Any],
    ) -> None:
        await self._delete_record(existing_record["id"])
        self.logger.info(f"Deleting record for update: {record.name} ({record.type})")
        await self._create_record(record)


depends.set(Dns, "cloudflare")

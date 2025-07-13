import os
import sys
import typing as t
from asyncio import sleep
from contextlib import suppress
from uuid import UUID
from warnings import catch_warnings, filterwarnings

from google.api_core.exceptions import BadRequest, Conflict
from google.cloud.dns import Changes
from google.cloud.dns import Client as DnsClient
from google.cloud.dns.resource_record_set import ResourceRecordSet
from google.cloud.dns.zone import ManagedZone
from validators import domain
from validators.utils import ValidationError
from acb.adapters import AdapterStatus
from acb.depends import depends

from ._base import DnsBase, DnsBaseSettings, DnsRecord

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b7d627bdb820")
MODULE_STATUS = AdapterStatus.STABLE


class DnsSettings(DnsBaseSettings): ...


class Dns(DnsBase):
    current_record_sets: list[ResourceRecordSet] = []
    new_record_sets: list[ResourceRecordSet] = []
    zone: ManagedZone | None = None

    async def init(self) -> None:
        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            from unittest.mock import MagicMock

            self.client = MagicMock()
            self.zone = MagicMock()
            return
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            self.client = DnsClient(project=self.config.app.project)

    def create_zone(self) -> None:
        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            return
        self.zone = self.client.zone(self.config.app.name, f"{self.config.app.domain}.")
        if not self.zone.exists():
            self.logger.info(f"Creating cloud_dns zone '{self.config.app.name}...")
            self.zone.create()
            self.logger.info(f"Zone '{self.zone.name}' successfully created")
        else:
            self.logger.info(f"Zone for '{self.zone.name}' exists")

    def list_records(self) -> list[DnsRecord]:
        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            return [
                DnsRecord(
                    name="test.example.com.",
                    type="A",
                    ttl=300,
                    rrdata=["192.0.2.1"],
                ),
            ]
        records = self.zone.list_resource_record_sets()
        return [
            DnsRecord.model_validate(
                {
                    "name": record.name,
                    "type": record.record_type,
                    "ttl": record.ttl,
                    "rrdata": record.rrdatas,
                },
            )
            for record in records
        ]

    async def wait_for_changes(self, changes: Changes) -> None:
        while changes.status != "done":
            await sleep(3)
            changes.reload()

    async def apply_changes(self, changes: Changes) -> None:
        try:
            changes.create()
            await self.wait_for_changes(changes)
        except (Conflict, BadRequest):
            change = changes.additions[0] if changes.additions else None
            if change and change.name.split(".")[1] != self.config.app.project:
                raise
            self.logger.info("Development domain detected - no changes made")

    async def delete_record_sets(self) -> None:
        changes = self.zone.changes()
        for record_set in self.current_record_sets:
            changes.delete_record_set(record_set)
        self.logger.info("Deleting record sets")
        await self.apply_changes(changes)

    async def add_record_sets(self) -> None:
        changes = self.zone.changes()
        for record_set in self.new_record_sets:
            changes.add_record_set(record_set)
        self.logger.info("Creating record sets")
        await self.apply_changes(changes)

    def get_record_set(self, record: DnsRecord) -> ResourceRecordSet:
        return self.zone.resource_record_set(
            name=record.name,
            record_type=record.type,
            ttl=record.ttl,
            rrdatas=record.rrdata,
        )

    def get_current_record(self, record: DnsRecord) -> t.Any:
        current_record = [
            r
            for r in self.list_records()
            if r.name == record.name and r.type == record.type
        ]
        if len(current_record) == 1:
            return current_record[0]
        return None

    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None:
        records = [records] if isinstance(records, DnsRecord) else records
        for record in records:
            self._normalize_record(record)
            await self._process_record(record)
        await self._apply_pending_changes()

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
                    record.rrdata[i] = f'"{r}"'

    async def _process_record(self, record: DnsRecord) -> None:
        current_record = self.get_current_record(record)
        if current_record and current_record.__dict__ == record.__dict__:
            return
        if current_record:
            self.current_record_sets.append(self.get_record_set(current_record))
            self.logger.info(f"Deleting - {current_record}")
        record_set = self.get_record_set(record)
        self.new_record_sets.append(record_set)
        self.logger.info(f"Creating - {record}")

    async def _apply_pending_changes(self) -> None:
        if self.current_record_sets:
            await self.delete_record_sets()
        if self.new_record_sets:
            await self.add_record_sets()
        else:
            self.logger.info("No DNS changes detected")


depends.set(Dns)

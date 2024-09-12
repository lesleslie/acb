import typing as t
from asyncio import sleep
from contextlib import suppress
from warnings import catch_warnings, filterwarnings

from google.api_core.exceptions import BadRequest, Conflict
from google.cloud.dns import Changes
from google.cloud.dns import Client as DnsClient
from google.cloud.dns.resource_record_set import ResourceRecordSet
from google.cloud.dns.zone import ManagedZone
from validators import domain
from validators.utils import ValidationError
from acb.depends import depends
from ._base import DnsBase, DnsBaseSettings, DnsRecord


class DnsSettings(DnsBaseSettings): ...


class Dns(DnsBase):
    current_record_sets: list[ResourceRecordSet] = []
    new_record_sets: list[ResourceRecordSet] = []
    zone: ManagedZone | None = None

    async def init(self) -> None:
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            self.client = DnsClient(project=self.config.app.project)

    def create_zone(self) -> None:
        self.zone = self.client.zone(self.config.app.name, f"{self.config.app.domain}.")
        if not self.zone.exists():
            self.logger.info(f"Creating cloud_dns zone '{self.config.app.name}...")
            self.zone.create()
            self.logger.info(f"Zone '{self.zone.name}' successfully created")
        else:
            self.logger.info(f"Zone for '{self.zone.name}' exists")

    def list_records(self) -> list[DnsRecord]:
        records = self.zone.list_resource_record_sets()
        records = [
            DnsRecord.model_validate(
                dict(
                    name=record.name,
                    type=record.record_type,
                    ttl=record.ttl,
                    rrdata=record.rrdatas,
                )
            )
            for record in records
        ]
        return records

    async def wait_for_changes(self, changes: Changes) -> None:
        while changes.status != "done":
            await sleep(3)
            changes.reload()  # API request

    async def apply_changes(self, changes: Changes):
        try:
            changes.create()  # API request
            await self.wait_for_changes(changes)
        except (Conflict, BadRequest) as err:
            change = changes.additions[0]  # type: ignore
            if change.name.split(".")[1] != self.config.app.project:
                raise err
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

    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None:
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
                        record.rrdata[i] = f'"{r}"'
            current_record = self.get_current_record(record)
            if current_record:
                if current_record.__dict__ == record.__dict__:
                    continue
                self.current_record_sets.append(self.get_record_set(current_record))
                self.logger.info(f"Deleting - {current_record}")
            record_set = self.get_record_set(record)
            self.new_record_sets.append(record_set)
            self.logger.info(f"Creating - {record}")
        if self.current_record_sets:
            await self.delete_record_sets()
        if self.new_record_sets:
            return await self.add_record_sets()
        self.logger.info("No DNS changes detected")


depends.set(Dns)

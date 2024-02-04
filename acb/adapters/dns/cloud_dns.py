from asyncio import sleep
from contextlib import suppress
from warnings import catch_warnings
from warnings import filterwarnings

from acb.depends import depends
from google.api_core.exceptions import BadRequest
from google.api_core.exceptions import Conflict
from google.cloud.dns import Changes
from google.cloud.dns import Client as DnsClient
from validators import domain
from validators.utils import ValidationError
from ._base import DnsBase
from ._base import DnsBaseSettings
from ._base import DnsRecord


class DnsSettings(DnsBaseSettings): ...


class Dns(DnsBase):
    async def init(self) -> None:
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            self.client = DnsClient(project=self.config.app.project)

    async def create_zone(self) -> None:
        self.zone = self.client.zone(self.config.app.name, f"{self.config.app.domain}.")
        if not self.zone.exists():
            self.logger.info(f"Creating gdns zone '{self.config.app.name}...")
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

    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None:
        if isinstance(records, DnsRecord):
            records = [records]
        changes = self.zone.changes()
        current_record_sets = []
        new_record_sets = []
        for record in records:
            if not record.name.endswith("."):
                record.name = f"{record.name}."
            record.rrdata = (
                [record.rrdata]
                if not isinstance(record.rrdata, list)
                else record.rrdata
            )
            for i, r in enumerate(record.rrdata):
                with suppress(ValidationError):
                    if isinstance(r, str) and domain(r) and not r.endswith("."):
                        r = f"{r}."
                        record.rrdata[i] = r
                    if record.type == "TXT":
                        record.rrdata[i] = f'"{r}"'
            current_record = [
                r
                for r in self.list_records()
                if r.name == record.name and r.type == record.type
            ]
            if len(current_record) == 1:
                # print(current_record[0])
                current_record = current_record[0]
                if current_record.__dict__ == record.__dict__:
                    continue
                current_record_set = self.zone.resource_record_set(
                    name=current_record.name,
                    record_type=current_record.type,
                    ttl=current_record.ttl,
                    rrdatas=current_record.rrdata,
                )
                current_record_sets.append(current_record_set)
                self.logger.info(f"Deleting - {current_record}")
            record_set = self.zone.resource_record_set(
                name=record.name,
                record_type=record.type,
                ttl=record.ttl,
                rrdatas=record.rrdata,
            )
            new_record_sets.append(record_set)
            self.logger.info(f"Creating - {record}")
        if current_record_sets:
            for record_set in current_record_sets:
                changes.delete_record_set(record_set)
            self.logger.info("Deleting record sets")
            await self.apply_changes(changes)
        changes = self.zone.changes()
        if new_record_sets:
            for record_set in new_record_sets:
                changes.add_record_set(record_set)
            self.logger.info("Creating record sets")
            await self.apply_changes(changes)
        else:
            self.logger.info("No DNS changes detected")


depends.set(Dns)

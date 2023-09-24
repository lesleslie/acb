from contextlib import suppress
from warnings import catch_warnings
from warnings import filterwarnings
import typing as t
from asyncio import sleep

from acb.config import ac
from acb.logger import logger
from google.api_core.exceptions import BadRequest
from google.api_core.exceptions import Conflict
from google.cloud.dns import Client as DnsClient
from google.cloud.dns import ManagedZone
from google.cloud.dns import Changes
from validators import domain
from validators.utils import ValidationError
from . import DnsBaseSettings
from . import DnsRecord


class DnsSettings(DnsBaseSettings):
    ...


class Dns:
    client: t.Optional[DnsClient] = None
    zone: t.Optional[ManagedZone] = None

    async def init(self) -> None:
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            self.client = DnsClient(project=ac.app.project)

    async def create_zone(self) -> None:
        self.zone = self.client.zone(ac.app.name, f"{ac.app.domain}.")
        if not self.zone.exists():
            logger.info(f"Creating gdns zone '{ac.app.name}...")
            self.zone.create()
            logger.info(f"Zone '{self.zone.name}' successfully created.")
        else:
            logger.info(f"Zone for '{self.zone.name}' exists.")

    async def list_records(self):
        records = self.zone.list_resource_record_sets()
        records = [
            DnsRecord(
                name=record.name,
                type=record.record_type,
                ttl=record.ttl,
                rrdata=record.rrdatas,
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
            if change.name.split(".")[1] != ac.app.project:
                raise err
            logger.info("Development domain detected. No changes made.")

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
                for r in await self.list_records()
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
                logger.info(f"Deleting - {current_record}")
            record_set = self.zone.resource_record_set(
                name=record.name,
                record_type=record.type,
                ttl=record.ttl,
                rrdatas=record.rrdata,
            )
            new_record_sets.append(record_set)
            logger.info(f"Creating - {record}")
        if current_record_sets:
            for record_set in current_record_sets:
                changes.delete_record_set(record_set)
            logger.info("Deleting record sets")
            await self.apply_changes(changes)
        changes = self.zone.changes()
        if new_record_sets:
            for record_set in new_record_sets:
                changes.add_record_set(record_set)
            logger.info("Creating record sets")
            await self.apply_changes(changes)
        else:
            logger.info("No DNS changes detected.")


dns: Dns = Dns()

from contextlib import suppress
from time import sleep
from warnings import catch_warnings
from warnings import filterwarnings

from acb import ac
from acb.logger import apformat
from google.api_core.exceptions import BadRequest
from google.api_core.exceptions import Conflict
from google.cloud.dns import Client as DnsClient
from pydantic import BaseModel
from validators import domain
from validators import ValidationFailure

with catch_warnings():
    filterwarnings("ignore", category=Warning)
    dns_client = DnsClient(project=ac.project)

dns_zone = dns_client.zone(ac.app_name, f"{ac.raw_domain}.")
splashstand_zone = dns_client.zone("sstand", "splashstand.com.")


class DnsRecord(BaseModel):
    name: str = ac.mail_domain
    type: str = "TXT"
    ttl: int = 300
    rrdata: str | list = None


class GoogleDNS:
    @staticmethod
    def create_dns_zone() -> None:
        if not dns_zone.exists():
            print(f"Creating gdns zone '{ac.app_name}...")
            dns_zone.create()
            print(f"Zone '{dns_zone.name}' successfully created.")
        else:
            print(f"Zone for '{dns_zone.name}' exists.")

    async def list_dns_records(zone: DnsClient.zone = dns_zone):
        records = zone.list_resource_record_sets()
        records = [
            DnsRecord(
                name=record.name,
                type=record.record_type,
                ttl=record.ttl,
                rrdata=record.rrdatas,
            )
            for record in records
        ]
        if ac.debug.dns or ac.debug.mail:
            await apformat(records)
        return records

    async def create_dns_records(
        self, records: list | DnsRecord, zone: DnsClient.zone = dns_zone
    ):
        if type(records) == DnsRecord:
            records = [records]
        changes = zone.changes()
        current_record_sets = []
        new_record_sets = []
        for record in records:
            if not record.name.endswith("."):
                record.name = f"{record.name}."
            record.rrdata = (
                [record.rrdata] if type(record.rrdata) != list else record.rrdata
            )
            for i, r in enumerate(record.rrdata):
                with suppress(ValidationFailure):
                    if type(r) == str and domain(r) and not r.endswith("."):
                        r = f"{r}."
                        record.rrdata[i] = r
                    if record.type == "TXT":
                        record.rrdata[i] = f'"{r}"'
            current_record = [
                r
                for r in await self.list_dns_records()
                if r.name == record.name and r.type == record.type
            ]
            if len(current_record) == 1:
                # print(current_record[0])
                current_record = current_record[0]
                if current_record.__dict__ == record.__dict__:
                    continue
                current_record_set = zone.resource_record_set(
                    name=current_record.name,
                    record_type=current_record.type,
                    ttl=current_record.ttl,
                    rrdatas=current_record.rrdata,
                )
                current_record_sets.append(current_record_set)
                print(f"Deleting - {current_record}")
            record_set = zone.resource_record_set(
                name=record.name,
                record_type=record.type,
                ttl=record.ttl,
                rrdatas=record.rrdata,
            )
            new_record_sets.append(record_set)
            print(f"Creating - {record}")
        if current_record_sets:
            for set in current_record_sets:
                changes.delete_record_set(set)
            changes.create()  # API request
            print("Deleting record sets", end="")
            while changes.status != "done":
                print(".", end="")
                sleep(5)
                changes.reload()  # API request
            print()
        changes = zone.changes()
        if new_record_sets:
            for set in new_record_sets:
                changes.add_record_set(set)
            try:
                changes.create()  # API request
                print("Creating record sets", end="")
                while changes.status != "done":
                    print(".", end="")
                    sleep(5)
                    changes.reload()  # API request
                print()
            except (Conflict, BadRequest) as err:
                if not changes.additions[0].name.split(".")[1] == "splashstand":
                    raise err
                print("SplashStand development domain detected. No changes made.")
        else:
            print("No DNS changes detected.")


gdns = GoogleDNS()

from asyncio import gather
from pathlib import Path
from pprint import pformat
from pprint import pprint
from re import search
from typing import Any

from actions.encode import load
from actions.log import *
from adapters.dns import create_dns_records
from adapters.dns import DnsRecord
from config import ac
from config import debug

from httpx import AsyncClient
from pydantic import BaseModel


class Mailgun(BaseModel):
    def __init__(self, **data: Any):
        super().__init__(**data)

    # conf = ConnectionConfig(
    #     MAIL_SERVER="smtp.ac.mail.mailgun.org",
    #     MAIL_PORT=587,
    #     MAIL_USERNAME=f"postmaster@{app.domain}",
    #     MAIL_PASSWORD=secrets.app_mail_password,
    #     MAIL_FROM="info@{app.domain}",
    #     MAIL_TLS=True,
    #     MAIL_SSL=False,
    #     TEMPLATE_FOLDER=theme.path / "utility" / "mail",
    # )

    def get_response(self, req_type: str, domain=None, data=None, params=None):
        pass

    #     caller = inspect_.calling_function()
    #     match caller:
    #         case search(caller, "domain"):
    #             caller = "domain"
    #         case search(caller, "route"):
    #             caller = "route"
    #     url = "/".join([ac.mailgun.api_url, caller, domain])
    #     data = dict(auth=("api", ac.mailgun.api_key), params=params, data=data)
    #     resp = None
    #     async with AsyncClient() as client:
    #         match req_type:
    #             case "get":
    #                 resp = await client.get(url)
    #             case "put":
    #                 url = "".join([url, "/connection"])
    #                 resp = await client.put(url, data=data)
    #             case "post":
    #                 url = "".join([url, "/connection"])
    #                 resp = await client.post(url, data=data)
    #             case "delete":
    #                 resp = await client.delete(url)
    #     if debug.mail:
    #         print(resp)
    #     return load.json(resp.json())

    async def list_domains(self):
        resp = await self.get_response("get", params={"skip": 0, "limit": 1000})
        domains = [d["name"] for d in resp["items"]]
        return domains

    async def get_domain(self, domain):
        return await self.get_response("get", domain=domain)

    async def create_domain(self, domain):
        resp = await self.get_response(
            "post",
            data={
                "name": domain,
                "smtp_password": ac.mail.password,
                "web_scheme": "https",
            },
        )
        if debug.mail:
            logger.debug(resp)
        resp = await self.get_response(
            "put", data={"require_tls": True, "skip_verification": True}
        )
        return resp

    async def delete_domain(self, domain):
        return await self.get_response("delete", domain=domain)

    async def create_domain_credentials(self, domain):
        return await self.get_response(
            "post",
            domain=domain,
            data={"login": f"postmaster@{domain}", "password": ac.mail.password},
        )

    async def update_domain_credentials(self, domain):  # this is prob not necessary
        return await self.get_response(
            "put", domain=domain, data={"password": ac.mail.ac.mail.mailgun.password}
        )

    async def get_dns_records(self, domain):
        records = await self.get_domain(domain)
        mx_records = records["receiving_dns_records"]
        sending_records = records["sending_dns_records"]
        records = []
        rrdata = []
        for r in mx_records:
            mx_host = f"{r['priority']} {r['value']}."
            rrdata.append(mx_host)
        record = DnsRecord(name=domain, type="MX", rrdata=rrdata)
        records.append(record)
        for r in sending_records:
            record = DnsRecord(name=r["name"], type=r["record_type"], rrdata=r["value"])
            records.append(record)
        return records

    async def create_dns_records(self):
        # if not ac.mail.mailgun.domain in list_domains(self):
        await self.create_domain(ac.mail.mailgun.domain)
        await self.create_domain_credentials(ac.mail.mailgun.domain)
        records = await self.get_dns_records(ac.mail.mailgun.domain)
        if ac.mail.mailgun.gmail.enabled:
            await self.delete_domain(ac.mail.mailgun.domain)
            rrdata = ac.mail.gmail.mx_servers
            record = DnsRecord(name=ac.mail.mailgun.domain, type="MX", rrdata=rrdata)
            records.append(record)
        else:
            await self.delete_domain(ac.mail.mailgun.domain)
        if debug.mail:
            pprint(records)
        await create_dns_records(records)

    async def list_routes(self):
        resp = await self.get_response("get", params={"skip": 0, "limit": 1000})
        domain_routes = [
            r for r in resp["items"] if ac.mail.mailgun.domain in r["expression"]
        ]
        if debug.mail:
            logger.debug(pformat(resp["items"]))
            logger.debug(len(resp["items"]))
            logger.debug(pformat(domain_routes))
            logger.debug(len(domain_routes))

        return domain_routes

    async def delete_route(self, route):
        with AsyncClient() as client:
            resp = await client.delete("delete", domain={route["id"]})
        logger.info(f"Deleted route for {route['description']}")
        return resp

    @staticmethod
    def get_name(address: str):
        name = search("'(.+)@.+", address)
        return name.group(1) if name else ""

    async def delete_routes(self, delete_all=False):
        forwards = await load.yaml(Path("mail.yml")).keys()
        routes = await self.list_routes()
        deletes = []
        deletes.extend(
            [r for r in routes if self.get_name(r["expression"]) not in forwards]
        )
        if debug.mail:
            pprint(deletes)
        for f in forwards:
            fs = [r for r in routes if self.get_name(r["expression"]) == f]
            deletes.extend(fs[1:])
        if delete_all or ac.mail.mailgun.gmail.enabled:
            deletes = [r for r in routes if len(self.get_name(r["expression"]))]
        if debug.mail:
            pprint(deletes)
            print(len(deletes))
        else:
            for d in deletes:
                await self.delete_route(d)

    async def create_route(self, domain_address, forwarding_addresses):
        domain_address = f"{domain_address}@{ac.mail.mailgun.domain}"
        if not isinstance(forwarding_addresses, list):
            forwarding_addresses = [forwarding_addresses]
        actions = ["stop(self)"]

        for addr in forwarding_addresses:
            actions.insert(0, f"forward('{addr}')")
        if debug.mail:
            print(actions)
        route = {
            "priority": 0,
            "description": domain_address,
            "expression": f"match_recipient('{domain_address}')",
            "action": actions,
        }
        routes = await self.list_routes()
        await gather(*routes)

        for r in routes:
            if (r["expression"] == route["expression"]) and (
                r["actions"] == route["action"]
            ):
                print(
                    f"Route for {domain_address}  ==> "
                    f"{', '.join(forwarding_addresses)} exists"
                )
                return
            elif r["expression"] == route["expression"]:
                await self.delete_route(r)
                break
        resp = await self.get_response("post", data=route)
        logger.info(
            f"Created route for {domain_address}  ==> "
            f" {', '.join(forwarding_addresses)}"
        )
        return resp

    async def create_routes(self, ordered=True):
        if ac.mail.mailgun.gmail.enabled:
            logger.info("Using gmail mx servers. No routes created.")
            return
        else:
            forwards = await load.yaml(Path("mail.yml"), ordered=ordered)
            async for k, v in forwards.items():
                await self.create_route(k, v)

    def setup_mail(self):
        self.create_dns_records()
        if not (Path("mail.yml").exists()):
            logger.info("No mail routes to configre - mail.yml not found.")
            return False
        self.delete_routes(delete_all=False)
        self.create_routes()


mailgun = Mailgun()

# if __name__ == "__main__":
#     ac.mail.mailgun.setup_mail()

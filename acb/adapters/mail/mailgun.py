import asyncio
import sys
import typing as t
from pprint import pformat
from pprint import pprint
from re import search

from acb.actions import load
from acb.adapters import dns
from acb.adapters.dns import DnsRecord
from acb.adapters import request
from acb.config import ac
from aiopath import AsyncPath
from httpx import Response as HttpxResponse
from loguru import logger
from pydantic import EmailStr
from . import MailBaseSettings


class MailSettings(MailBaseSettings):
    server: str = "smtp.mailgun.com"
    api_url: str = "https://api.mailgun.net/v3/domains"
    test_receiver: t.Optional[EmailStr] = None
    tls: bool = True
    ssl: bool = False
    template_folder: t.Optional[AsyncPath] = None

    def model_post_init(self, __context: t.Any) -> None:
        self.api_key = ac.secrets.mailgun_api_key
        self.password = ac.secrets.mailgun_password


class Mail:
    async def get_response(
        self,
        req_type: str,
        domain: t.Optional[str] = None,
        data: t.Optional[dict] = None,
        params: t.Optional[dict] = None,
    ) -> dict:
        domain = domain or ac.app.domain
        caller: str = sys._getframe().f_back.f_code.co_name
        caller = "domain" if search(caller, "domain") else "route"
        url = "/".join([ac.mail.api_url, caller, domain])
        data = dict(
            auth=("api", ac.mail.api_key.get_secret_value()), params=params, data=data
        )
        resp = None
        match req_type:
            case "get":
                resp = await request.get(url)  # type: ignore
            case "put":
                url = "".join([url, "/connection"])
                resp = await request.put(url, data=data)  # type: ignore
            case "post":
                url = "".join([url, "/connection"])
                resp = await request.post(url, data=data)  # type: ignore
            case "delete":
                resp = await request.delete(url)  # type: ignore
        if ac.debug.mail:
            print(resp)
        return await load.json(resp.json())

    async def list_domains(self) -> list:
        resp = await self.get_response("get", params={"skip": 0, "limit": 1000})
        domains = [d["name"] for d in resp["items"]]
        return domains

    async def get_domain(self, domain: str) -> dict:
        return await self.get_response("get", domain=domain)

    async def create_domain(self, domain: str) -> dict:
        resp = await self.get_response(
            "post",
            data={
                "name": domain,
                "smtp_password": ac.mail.password.get_secret_value(),
                "web_scheme": "https",
            },
        )
        if ac.debug.mail:
            logger.debug(resp)
        resp = await self.get_response(
            "put", data={"require_tls": True, "skip_verification": True}
        )
        return resp

    async def delete_domain(self, domain: str) -> dict:
        return await self.get_response("delete", domain=domain)

    async def create_domain_credentials(self, domain: str) -> dict:
        return await self.get_response(
            "post",
            domain=domain,
            data={
                "login": f"postmaster@{domain}",
                "password": ac.mail.password.get_secret_value(),
            },
        )

    async def update_domain_credentials(self, domain: str) -> dict:
        # this is prob not necessary
        return await self.get_response(
            "put",
            domain=domain,
            data={"password": ac.mail.mailgun.password.get_secret_value()},
        )

    async def get_dns_records(self, domain: str) -> list:
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

    async def create_dns_records(self) -> None:
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
        if ac.debug.mail:
            pprint(records)
            await dns.create_records(records)  # type: ignore

    async def list_routes(self) -> list:
        resp = await self.get_response("get", params={"skip": 0, "limit": 1000})
        domain_routes = [
            r for r in resp["items"] if ac.mail.mailgun.domain in r["expression"]
        ]
        if ac.debug.mail:
            logger.debug(pformat(resp["items"]))
            logger.debug(len(resp["items"]))
            logger.debug(pformat(domain_routes))
            logger.debug(len(domain_routes))
        return domain_routes

    async def delete_route(self, route: dict) -> HttpxResponse:
        resp = await request.delete("delete", domain={route["id"]})  # type: ignore
        logger.info(f"Deleted route for {route['description']}")
        return resp

    @staticmethod
    def get_name(address: str) -> str:
        name = search("'(.+)@.+", address)
        return name.group(1) if name else ""

    async def delete_routes(self, delete_all: bool = False) -> None:
        forwards = ac.mail.forwards.keys()
        routes = await self.list_routes()
        deletes = []
        deletes.extend(
            [r for r in routes if self.get_name(r["expression"]) not in forwards]
        )
        if ac.debug.mail:
            pprint(deletes)
        for f in forwards:
            fs = [r for r in routes if self.get_name(r["expression"]) == f]
            deletes.extend(fs[1:])
        if delete_all or ac.mail.mailgun.gmail.enabled:
            deletes = [r for r in routes if len(self.get_name(r["expression"]))]
        if ac.debug.mail:
            pprint(deletes)
            print(len(deletes))
        else:
            for d in deletes:
                await self.delete_route(d)

    async def create_route(self, domain_address, forwarding_addresses) -> dict | None:
        domain_address = f"{domain_address}@{ac.mail.domain}"
        if not isinstance(forwarding_addresses, list):
            forwarding_addresses = [forwarding_addresses]
        actions = ["stop(self)"]
        for addr in forwarding_addresses:
            actions.insert(0, f"forward('{addr}')")
        if ac.debug.mail:
            print(actions)
        route = {
            "priority": 0,
            "description": domain_address,
            "expression": f"match_recipient('{domain_address}')",
            "action": actions,
        }
        routes = await self.list_routes()
        await asyncio.gather(*routes)
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

    async def create_routes(self) -> None:
        async for k, v in ac.mail.forwards.items():
            await self.create_route(k, v)

    async def init(self) -> None:
        await self.create_dns_records()
        await self.delete_routes()
        await self.create_routes()


mail = Mail()

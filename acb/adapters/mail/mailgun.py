import asyncio
import sys
import typing as t
from pprint import pformat
from pprint import pprint
from re import search

from acb.actions import load
from acb.adapters.dns import dns
from acb.adapters.dns import DnsRecord
from acb.adapters.requests import requests
from acb.config import ac
from aiopath import AsyncPath
from httpx import Response as HttpxResponse
from loguru import logger
from pydantic import AnyUrl
from pydantic import EmailStr
from pydantic import SecretStr
from . import MailBaseSettings


class MailSettings(MailBaseSettings):
    password: SecretStr
    api_key: SecretStr
    server: SecretStr = "smtp.mailgun.com"
    api_url = "https://api.mailgun.net/v3/domains"
    default_from: EmailStr = f"info@{ac.app.domain}"
    default_from_name = ac.app.title
    test_receiver: EmailStr = None
    tls = True
    ssl = False
    template_folder: t.Optional[AsyncPath]


class Mail:
    async def get_response(
        self,
        req_type: str,
        domain: AnyUrl = None,
        data: dict = None,
        params: dict = None,
    ) -> dict:
        caller: str = sys._getframe().f_back.f_code.co_name
        match caller:
            case search(caller, "domain"):
                caller = "domain"
            case search(caller, "route"):
                caller = "route"
        url = "/".join([ac.mailgun.api_url, caller, domain])
        data = dict(auth=("api", ac.mailgun.api_key), params=params, data=data)
        resp = None
        match req_type:
            case "get":
                resp = await requests.get(url)
            case "put":
                url = "".join([url, "/connection"])
                resp = await requests.put(url, data=data)
            case "post":
                url = "".join([url, "/connection"])
                resp = await requests.post(url, data=data)
            case "delete":
                resp = await requests.delete(url)
        if ac.debug.mail:
            print(resp)
        return await load.json(resp.json())

    async def list_domains(self) -> list:
        resp = await self.get_response("get", params={"skip": 0, "limit": 1000})
        domains = [d["name"] for d in resp["items"]]
        return domains

    async def get_domain(self, domain: AnyUrl) -> dict:
        return await self.get_response("get", domain=domain)

    async def create_domain(self, domain: AnyUrl) -> dict:
        resp = await self.get_response(
            "post",
            data={
                "name": domain,
                "smtp_password": ac.mail.password,
                "web_scheme": "https",
            },
        )
        if ac.debug.mail:
            logger.debug(resp)
        resp = await self.get_response(
            "put", data={"require_tls": True, "skip_verification": True}
        )
        return resp

    async def delete_domain(self, domain: AnyUrl) -> dict:
        return await self.get_response("delete", domain=domain)

    async def create_domain_credentials(self, domain: AnyUrl) -> dict:
        return await self.get_response(
            "post",
            domain=domain,
            data={"login": f"postmaster@{domain}", "password": ac.mail.password},
        )

    async def update_domain_credentials(self, domain: AnyUrl) -> dict:
        # this is prob not necessary
        return await self.get_response(
            "put", domain=domain, data={"password": ac.mail.mailgun.password}
        )

    async def get_dns_records(self, domain: AnyUrl) -> list:
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
            await dns.create_dns_records(records)

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
        resp = await requests.delete("delete", domain={route["id"]})
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
        domain_address = f"{domain_address}@{ac.mail.mailgun.domain}"
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

    async def create_routes(self, ordered: bool = True) -> None:
        if ac.mail.mailgun.gmail.enabled:
            logger.info("Using gmail mx servers. No routes created.")
            return
        else:
            forwards = await load.yaml(AsyncPath("mail.yml"), ordered=ordered)
            async for k, v in forwards.items():
                await self.create_route(k, v)

    async def setup_mail(self) -> None:
        await self.create_dns_records()
        await self.delete_routes()
        await self.create_routes()

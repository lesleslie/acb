import os
import sys
import typing as t
from pprint import pformat
from re import search
from uuid import UUID

from httpx import Response as HttpxResponse
from pydantic import SecretStr
from acb.actions.encode import load
from acb.adapters import AdapterStatus, adapter_registry, import_adapter
from acb.adapters.dns._base import DnsProtocol, DnsRecord
from acb.config import Config
from acb.debug import debug
from acb.depends import depends

from ._base import SmtpBase, SmtpBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b887b20a943f")
MODULE_STATUS = AdapterStatus.STABLE

Dns, Requests = import_adapter()


class SmtpSettings(SmtpBaseSettings):
    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.api_url = "https://api.mailgun.net/v3/domains"
        self.mx_servers = ["smtp.mailgun.com"]
        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            self.api_key = values.get("api_key", SecretStr("test-api-key"))
            self.password = values.get("password", SecretStr("test-password"))
        else:
            try:
                self.api_key = config.smtp.api_key
                self.password = config.smtp.password
            except AttributeError:
                self.api_key = values.get("api_key", SecretStr("test-api-key"))
                self.password = values.get("password", SecretStr("test-password"))


class Smtp(SmtpBase):
    requests: Requests = depends()

    async def get_response(
        self,
        req_type: str,
        domain: str | None = None,
        data: dict[str, t.Any] | None = None,
        params: dict[str, int] | None = None,
    ) -> dict[str, t.Any]:
        calling_frame = sys._getframe().f_back.f_code.co_name
        caller = "domain" if search(calling_frame, "domain") else "route"
        url = "/".join(
            [self.config.smtp.api_url, caller, domain or self.config.app.domain or ""],
        )
        data = {
            "auth": ("api", self.config.smtp.api_key.get_secret_value()),
            "params": params,
            "data": data,
        }
        match req_type:
            case "get":
                resp = await self.requests.get(url)
            case "put":
                url = f"{url}/connection"
                resp = await self.requests.put(url, data=data)
            case "post":
                url = f"{url}/connection"
                resp = await self.requests.post(url, data=data)
            case "delete":
                resp = await self.requests.delete(url)
            case _:
                raise ValueError
        return await load.json(resp.json())

    async def list_domains(self) -> list[str]:
        resp = await self.get_response("get", params={"skip": 0, "limit": 1000})
        return [d.get("name") for d in resp.get("items", {})]

    async def get_domain(self, domain: str) -> dict[str, t.Any]:
        return await self.get_response("get", domain=domain)

    async def create_domain(self, domain: str) -> dict[str, t.Any]:
        resp = await self.get_response(
            "post",
            data={
                "name": domain,
                "smtp_password": self.config.smtp.password.get_secret_value(),
                "web_scheme": "https",
            },
        )
        self.logger.debug(resp)
        return await self.get_response(
            "put",
            data={"require_tls": True, "skip_verification": True},
        )

    async def delete_domain(self, domain: str) -> dict[str, str]:
        return await self.get_response("delete", domain=domain)

    async def create_domain_credentials(self, domain: str) -> dict[str, str]:
        return await self.get_response(
            "post",
            domain=domain,
            data={
                "login": f"postmaster@{domain}",
                "password": self.config.smtp.password.get_secret_value(),
            },
        )

    async def update_domain_credentials(self, domain: str) -> dict[str, str]:
        return await self.get_response(
            "put",
            domain=domain,
            data={"password": self.config.mail.mailgun.password.get_secret_value()},
        )

    async def get_dns_records(self, domain: str) -> list[DnsRecord]:
        records = await self.get_domain(domain)
        mx_records = records["receiving_dns_records"]
        sending_records = records["sending_dns_records"]
        records = []
        rrdata = []
        for r in mx_records:
            mx_host = f"{r['priority']} {r['value']}."
            rrdata.append(mx_host)
        record = DnsRecord.model_validate(
            {"name": domain, "type": "MX", "rrdata": rrdata}
        )
        records.append(record)
        for r in sending_records:
            record = DnsRecord.model_validate(
                {"name": r["name"], "type": r["record_type"], "rrdata": r["value"]},
            )
            records.append(record)
        debug(records)
        return records

    @depends.inject
    async def create_dns_records(self, dns: DnsProtocol = depends()) -> None:
        await self.create_domain(self.config.smtp.domain)
        await self.create_domain_credentials(self.config.smtp.domain)
        records = await self.get_dns_records(self.config.smtp.domain)
        if self.config.mail.mailgun.gmail.enabled:
            await self.delete_domain(self.config.smtp.domain)
            rrdata = self.config.smtp.mx_servers
            record = DnsRecord.model_validate(
                {"name": self.config.smtp.domain, "type": "MX", "rrdata": rrdata},
            )
            records.append(record)
        else:
            await self.delete_domain(self.config.smtp.domain)
        await dns.create_records(records)

    async def list_routes(self) -> list[t.Any]:
        resp = await self.get_response("get", params={"skip": 0, "limit": 1000})
        domain_routes = [
            r for r in resp["items"] if self.config.smtp.domain in r["expression"]
        ]
        self.logger.debug(pformat(resp["items"]))
        self.logger.debug(len(resp["items"]))
        self.logger.debug(pformat(domain_routes))
        self.logger.debug(len(domain_routes))
        return domain_routes

    async def delete_route(self, route: dict[str, str]) -> HttpxResponse:
        resp = await self.requests.delete("delete", domain={route["id"]})
        self.logger.info(f"Deleted route for {route['description']}")
        return resp

    @staticmethod
    def get_name(address: str) -> str:
        pattern = "'(.+)@.+"
        name = search(pattern, address)
        return name.group(1) if name else ""

    async def delete_routes(self, delete_all: bool = False) -> None:
        forwards = self.config.smtp.forwards.keys()
        routes = await self.list_routes()
        deletes = []
        deletes.extend(
            [r for r in routes if self.get_name(r["expression"]) not in forwards],
        )
        debug(deletes)
        for f in forwards:
            fs = [r for r in routes if self.get_name(r["expression"]) == f]
            deletes.extend(fs[1:])
        adapter = next(
            a for a in adapter_registry.get() if a.category == "email" and a.enabled
        )
        if delete_all or adapter.name == "gmail":
            deletes = [r for r in routes if len(self.get_name(r["expression"]))]
            debug(deletes)
            debug(len(deletes))
        else:
            for d in deletes:
                await self.delete_route(d)

    async def create_route(
        self,
        domain_address: str,
        forwarding_addresses: list[str] | str,
    ) -> dict[str, str]:
        domain_address = f"{domain_address}@{self.config.smtp.domain}"
        if not isinstance(forwarding_addresses, list):
            forwarding_addresses = [forwarding_addresses]
        actions = ["stop(self)"]
        for addr in forwarding_addresses:
            actions.insert(0, f"forward('{addr}')")
        debug(actions)
        route = {
            "priority": 0,
            "description": domain_address,
            "expression": f"match_recipient('{domain_address}')",
            "action": actions,
        }
        routes = await self.list_routes()
        for r in routes:
            if (
                r["expression"] == route["expression"]
                and r["actions"] == route["action"]
            ):
                self.logger.debug(
                    f"Route for {domain_address}  ==> {', '.join(forwarding_addresses)} exists",
                )
            elif r["expression"] == route["expression"]:
                await self.delete_route(r)
        resp = await self.get_response("post", data=route)
        self.logger.info(
            f"Created route for {domain_address}  ==>  {', '.join(forwarding_addresses)}",
        )
        return resp

    async def create_routes(self) -> None:
        async for name, forward in self.config.smtp.forwards.items():
            await self.create_route(name, forward)

    async def init(self) -> None:
        await self.create_dns_records()
        await self.delete_routes()
        await self.create_routes()


depends.set(Smtp)

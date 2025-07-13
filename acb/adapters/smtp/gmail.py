import base64
import os
import sys
import typing as t
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from re import search
from uuid import UUID

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httpx import Response as HttpxResponse
from pydantic import SecretStr
from acb.adapters import AdapterStatus, import_adapter
from acb.adapters.dns._base import DnsProtocol, DnsRecord
from acb.config import Config
from acb.debug import debug
from acb.depends import depends

from ._base import SmtpBase, SmtpBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b8782cb6e8db")
MODULE_STATUS = AdapterStatus.STABLE

Dns, Requests = import_adapter()


class SmtpSettings(SmtpBaseSettings):
    client_id: str | None = None
    client_secret: SecretStr | None = None
    refresh_token: SecretStr | None = None
    token_uri: str = "https://oauth2.googleapis.com/token"
    scopes: list[str] = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.settings.basic",
        "https://www.googleapis.com/auth/gmail.settings.sharing",
    ]

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.mx_servers = [
            "1 aspmx.l.google.com.",
            "2 alt1.aspmx.l.google.com.",
            "3 alt2.aspmx.l.google.com.",
            "4 alt3.aspmx.l.google.com.",
            "5 alt4.aspmx.l.google.com.",
        ]
        if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
            self.client_id = values.get("client_id", "test-client-id")
            self.client_secret = values.get(
                "client_secret",
                SecretStr("test-client-secret"),
            )
            self.refresh_token = values.get(
                "refresh_token",
                SecretStr("test-refresh-token"),
            )


class Smtp(SmtpBase):
    requests: Requests = depends()

    def _get_gmail_service(self) -> t.Any:
        credentials = Credentials(
            None,
            refresh_token=self.config.smtp.refresh_token.get_secret_value(),
            token_uri=self.config.smtp.token_uri,
            client_id=self.config.smtp.client_id,
            client_secret=self.config.smtp.client_secret.get_secret_value(),
            scopes=self.config.smtp.scopes,
        )
        return build("gmail", "v1", credentials=credentials)

    async def get_response(
        self,
        req_type: str,
        domain: str | None = None,
        data: dict[str, t.Any] | None = None,
        params: dict[str, int] | None = None,
    ) -> dict[str, t.Any]:
        self.logger.debug(f"Gmail adapter: {req_type} request for {domain}")
        return {"message": "success", "status": "ok"}

    async def list_domains(self) -> list[str]:
        return [self.config.smtp.domain] if self.config.smtp.domain else []

    async def get_domain(self, domain: str) -> dict[str, t.Any]:
        return {
            "domain": domain,
            "receiving_dns_records": [
                {"priority": p.split()[0], "value": p.split()[1]}
                for p in self.config.smtp.mx_servers
            ],
            "sending_dns_records": [
                {
                    "name": domain,
                    "record_type": "TXT",
                    "value": "v=spf1 include:_spf.google.com ~all",
                },
                {
                    "name": f"_dmarc.{domain}",
                    "record_type": "TXT",
                    "value": f"v=DMARC1; p=none; rua=mailto:postmaster@{domain}",
                },
            ],
        }

    async def create_domain(self, domain: str) -> dict[str, t.Any]:
        self.logger.info(f"Gmail adapter: Domain {domain} configuration simulated")
        return {"message": "Domain configured for Gmail", "domain": domain}

    async def delete_domain(self, domain: str) -> dict[str, str]:
        self.logger.info(f"Gmail adapter: Domain {domain} deletion simulated")
        return {"message": "Domain deletion simulated", "domain": domain}

    async def create_domain_credentials(self, domain: str) -> dict[str, str]:
        return {"message": "Gmail uses OAuth authentication"}

    async def update_domain_credentials(self, domain: str) -> dict[str, str]:
        return {"message": "Gmail uses OAuth authentication"}

    async def get_dns_records(self, domain: str) -> list[DnsRecord]:
        records = []
        rrdata = self.config.smtp.mx_servers
        record = DnsRecord.model_validate(
            {"name": domain, "type": "MX", "rrdata": rrdata}
        )
        records.append(record)
        spf_record = DnsRecord.model_validate(
            {
                "name": domain,
                "type": "TXT",
                "rrdata": ["v=spf1 include:_spf.google.com ~all"],
            },
        )
        records.append(spf_record)
        dmarc_record = DnsRecord.model_validate(
            {
                "name": f"_dmarc.{domain}",
                "type": "TXT",
                "rrdata": [f"v=DMARC1; p=none; rua=mailto:postmaster@{domain}"],
            },
        )
        records.append(dmarc_record)
        debug(records)
        return records

    @depends.inject
    async def create_dns_records(self, dns: DnsProtocol = depends()) -> None:
        records = await self.get_dns_records(self.config.smtp.domain)
        await dns.create_records(records)
        self.logger.info("Created DNS records for Gmail configuration")

    async def list_routes(self) -> list[t.Any]:
        try:
            service = self._get_gmail_service()
            result = (
                service.users()
                .settings()
                .forwardingAddresses()
                .list(userId="me")
                .execute()
            )
            forwards = result.get("forwardingAddresses", [])
            return [
                {
                    "id": forward.get("forwardingEmail"),
                    "expression": f"match_recipient('{forward.get('forwardingEmail')}@{self.config.smtp.domain}')",
                    "description": forward.get("forwardingEmail"),
                    "actions": [
                        f"forward('{forward.get('forwardingEmail')}')",
                        "stop()",
                    ],
                }
                for forward in forwards
            ]
        except HttpError as error:
            self.logger.exception(f"Error listing Gmail forwarding addresses: {error}")
            return []

    async def delete_route(self, route: dict[str, str]) -> HttpxResponse:
        try:
            service = self._get_gmail_service()
            email = route.get("id")
            if email:
                service.users().settings().forwardingAddresses().delete(
                    userId="me",
                    forwardingEmail=email,
                ).execute()
                self.logger.info(f"Deleted forwarding address {email}")

                class DeleteRouteResponse(HttpxResponse):
                    def __init__(self) -> None:
                        super().__init__(200)
                        self._json = {"message": f"Forwarding address {email} deleted"}

                    def json(self, **kwargs: t.Any) -> dict[str, str]:
                        return self._json

                return DeleteRouteResponse()
            self.logger.error("No email found in route")

            class DeleteRouteError(HttpxResponse):
                def __init__(self) -> None:
                    super().__init__(400)
                    self._json = {"message": "No email found in route"}

                def json(self, **kwargs: t.Any) -> dict[str, str]:
                    return self._json

            return DeleteRouteError()
        except HttpError as error:
            self.logger.exception(f"Error deleting Gmail forwarding address: {error}")

            class DeleteRouteErrorResponse(HttpxResponse):
                def __init__(self) -> None:
                    super().__init__(500)
                    self._json = {"message": str(error)}

                def json(self, **kwargs: t.Any) -> dict[str, str]:
                    return self._json

            return DeleteRouteErrorResponse()

    @staticmethod
    def get_name(address: str) -> str:
        pattern = "'(.+)@.+"
        name = search(pattern, address)
        return name.group(1) if name else ""

    async def delete_routes(self, delete_all: bool = False) -> None:
        forwards = self.config.smtp.forwards.keys()
        routes = await self.list_routes()
        deletes = []
        if delete_all:
            deletes = routes
        else:
            deletes.extend(
                [r for r in routes if self.get_name(r["expression"]) not in forwards],
            )
            for f in forwards:
                fs = [r for r in routes if self.get_name(r["expression"]) == f]
                deletes.extend(fs[1:])
        for d in deletes:
            await self.delete_route(d)

    async def create_route(
        self,
        domain_address: str,
        forwarding_addresses: list[str] | str,
    ) -> dict[str, t.Any]:
        try:
            service = self._get_gmail_service()
            if not isinstance(forwarding_addresses, list):
                forwarding_addresses = [forwarding_addresses]
            results = []
            for forward_address in forwarding_addresses:
                try:
                    service.users().settings().forwardingAddresses().create(
                        userId="me",
                        body={"forwardingEmail": forward_address},
                    ).execute()
                    self.logger.info(f"Created forwarding address {forward_address}")
                except HttpError as error:
                    if error.resp.status == 409:
                        self.logger.debug(
                            f"Forwarding address {forward_address} already exists",
                        )
                    else:
                        raise
                result = (
                    service.users()
                    .settings()
                    .updateAutoForwarding(
                        userId="me",
                        body={
                            "enabled": True,
                            "emailAddress": forward_address,
                            "disposition": "leaveInInbox",
                        },
                    )
                    .execute()
                )
                results.append(result)
                self.logger.info(
                    f"Created forwarding from {domain_address}@{self.config.smtp.domain} to {forward_address}",
                )
            return {"message": "Forwarding created", "results": results}
        except HttpError as error:
            self.logger.exception(f"Error creating Gmail forwarding: {error}")
            return {"error": str(error)}

    async def create_routes(self) -> None:
        for name, forward in self.config.smtp.forwards.items():
            await self.create_route(name, forward)

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
    ) -> dict[str, t.Any]:
        try:
            service = self._get_gmail_service()
            message = MIMEMultipart("alternative")
            message["to"] = to
            message["from"] = (
                f"{self.config.smtp.default_from_name} <{self.config.smtp.default_from}>"
            )
            message["subject"] = subject
            if html:
                message.attach(MIMEText(body, "html"))
            else:
                message.attach(MIMEText(body, "plain"))
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            result = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": encoded_message})
                .execute()
            )
            self.logger.info(f"Email sent to {to}, message ID: {result['id']}")
            return {"id": result["id"], "status": "sent"}
        except HttpError as error:
            self.logger.exception(f"Error sending email: {error}")
            return {"error": str(error), "status": "failed"}

    async def init(self) -> None:
        await self.create_dns_records()
        await self.delete_routes()
        await self.create_routes()


depends.set(Smtp)

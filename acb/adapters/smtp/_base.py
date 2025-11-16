import typing as t
from anyio import Path as AsyncPath
from pydantic import EmailStr, SecretStr

from acb.config import AdapterBase, Config, Settings, gen_password
from acb.depends import Inject, depends


class SmtpBaseSettings(Settings):
    api_key: SecretStr | None = None
    mx_servers: list[str] | None = []
    password: SecretStr = SecretStr(gen_password())
    domain: str | None = None
    port: int = 587
    api_url: str | None = ""
    default_from: EmailStr | None = None
    default_from_name: str | None = None
    test_receiver: EmailStr | None = None
    tls: bool = True
    ssl: bool = False
    template_folder: AsyncPath | None = None
    forwards: dict[str, EmailStr] = {
        "admin": "pat@example.com",
        "info": "terry@example.com",
    }

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)
        if "domain" not in values and config.app:
            self.domain = f"mail.{config.app.domain}"
        if "default_from" not in values and config.app:
            self.default_from = f"info@{config.app.domain}"
        if "default_from_name" not in values and config.app:
            self.default_from_name = config.app.title


class SmtpBase(AdapterBase): ...

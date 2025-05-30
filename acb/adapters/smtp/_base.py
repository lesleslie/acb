import typing as t

from anyio import Path as AsyncPath
from pydantic import EmailStr, SecretStr
from acb.config import AdapterBase, Config, Settings, gen_password
from acb.depends import depends


class SmtpBaseSettings(Settings):
    api_key: t.Optional[SecretStr] = None
    mx_servers: t.Optional[list[str]] = []
    password: SecretStr = SecretStr(gen_password())
    domain: t.Optional[str] = None
    port: int = 587
    api_url: t.Optional[str] = ""
    default_from: t.Optional[EmailStr] = None
    default_from_name: t.Optional[str] = None
    test_receiver: t.Optional[EmailStr] = None
    tls: bool = True
    ssl: bool = False
    template_folder: t.Optional[AsyncPath] = None
    forwards: dict[str, EmailStr] = dict(
        admin="pat@example.com",
        info="terry@example.com",
    )

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        if "domain" not in values:
            self.domain = f"mail.{config.app.domain}"
        if "default_from" not in values:
            self.default_from = f"info@{config.app.domain}"
        if "default_from_name" not in values:
            self.default_from_name = config.app.title


class SmtpBase(AdapterBase): ...

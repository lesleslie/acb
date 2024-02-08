import typing as t

from acb.adapters import AdapterBase
from acb.config import Config
from acb.config import gen_password
from acb.config import Settings
from acb.depends import depends
from aiopath import AsyncPath
from pydantic import EmailStr
from pydantic import SecretStr


class EmailBaseSettings(Settings):
    requires: t.Optional[list[str]] = ["requests"]
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
        self.domain = f"mail.{config.app.domain}"
        self.default_from = f"info@{config.app.domain}"
        self.default_from_name = config.app.title


class EmailBase(AdapterBase): ...

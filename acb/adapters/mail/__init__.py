import typing as t

from acb.config import ac
from acb.config import Settings
from acb.config import gen_password
from aiopath import AsyncPath
from pydantic import EmailStr
from pydantic import SecretStr
from pydantic import HttpUrl


class MailBaseSettings(Settings):
    api_key: t.Optional[SecretStr] = None
    server: t.Optional[SecretStr | str] = None
    password: SecretStr = SecretStr(gen_password(10))
    domain: t.Optional[str] = None
    port: int = 587
    api_url: t.Optional[HttpUrl] = None
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

    def model_post_init(self, __context: t.Any) -> None:
        self.domain = f"mail.{ac.app.domain}"
        self.default_from = f"info@{ac.app.domain}"
        self.default_from_name = ac.app.title


class MailBase:
    ...

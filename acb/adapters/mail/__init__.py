import typing as t

from acb.config import ac
from acb.config import AppSettings
from acb.config import gen_password
from acb.config import load_adapter
from aiopath import AsyncPath
from pydantic import EmailStr
from pydantic import SecretStr
from pydantic import AnyUrl


class MailBaseSettings(AppSettings):
    api_key: SecretStr
    server: SecretStr
    password: SecretStr = gen_password(10)
    domain: EmailStr = f"mail@{ac.app.domain}"
    port: int = 587
    api_url: AnyUrl = None
    default_from: EmailStr = f"info@{ac.app.domain}"
    default_from_name = ac.app.title
    test_receiver: EmailStr = None
    tls = True
    ssl = False
    template_folder: t.Optional[AsyncPath]


mail = load_adapter("mail")

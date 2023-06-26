import typing as t
from importlib import import_module

from acb.config import ac
from acb.config import AppSettings
from acb.config import gen_password
from aiopath import AsyncPath
from pydantic import EmailStr
from pydantic import SecretStr


class MailBaseSettings(AppSettings):
    api_key: SecretStr
    server: SecretStr
    password: SecretStr = gen_password(10)
    domain: EmailStr = f"mail@{ac.app.domain}"
    port: int = 587
    api_url = "https://api.mailgun.net/v3/domains"
    default_from: EmailStr = f"info@{ac.app.domain}"
    default_from_name = ac.app.title
    test_receiver: EmailStr = None
    tls = True
    ssl = False
    template_folder: t.Optional[AsyncPath]


mail = import_module(ac.adapters.mail).mail

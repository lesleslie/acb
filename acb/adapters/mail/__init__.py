from acb.config import ac
from acb.config import AppSettings
from acb.config import AppSecrets
from importlib import import_module
from pydantic import EmailStr
from pydantic import AnyUrl
from aiopath import AsyncPath
import typing as t
from acb.config import gen_password

class MailBaseSecrets(AppSecrets):
    api_key: t.Optional[str] = None
    server: t.Optional[AnyUrl] = None
    password: str = gen_password(10)


class MailBaseSettings(AppSettings):
    domain: EmailStr = f"mail@{ac.app.domain}"
    port: int = 587
    username: str = f"postmaster@{ac.app.domain}"
    password: str = ac.secrets.app_mail_password
    api_url = "https://api.mailgun.net/v3/domains"
    api_key = ac.secrets.mailgun_api_key
    default_from: EmailStr = f"info@{ac.app.domain}"
    default_from_name = ac.app.title
    test_receiver: EmailStr = None
    tls = True
    ssl = False
    template_folder: t.Optional[AsyncPath]


mail = import_module(ac.adapters.mail).mail

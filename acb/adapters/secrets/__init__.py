import typing as t
from importlib import import_module

from acb.config import ac
from acb.config import AppSettings


# class BaseSecretsSettings(AppSettings):
#     project: t.Optional[str] = ac.app.project
#     domain: t.Optional[str] = ac.domain
#     prefix: t.Optional[str] = ac.app.name
#     parent: t.Optional[str] = f"projects/{ac.app.project}"


secrets = import_module(ac.adapters.secrets).secrets

from acb.config import ac
from acb.config import AppSettings
from importlib import import_module
import typing as t
from pydantic_settings import BaseSettings


class DatabaseSecrets(BaseSettings, extra="forbid"):
    host: t.Optional[str]
    user: t.Optional[str]
    password: t.Optional[str]
    connection: t.Optional[str]


class BaseDatabaseSettings(AppSettings):
    ...


db = database = import_module(ac.adapters.database).database
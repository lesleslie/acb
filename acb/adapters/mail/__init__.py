from acb.config import ac
from acb.config import AppSettings
from importlib import import_module


class BaseMailSettings(AppSettings):
    ...


mail = import_module(ac.adapters.mail).mail

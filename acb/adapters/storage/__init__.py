from acb.config import ac
from acb.config import AppSettings
from importlib import import_module


class BaseStorageSettings(AppSettings):
    ...


stor = storage = import_module(ac.adapters.storage)
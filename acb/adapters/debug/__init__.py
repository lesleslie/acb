from acb.config import ac
from acb.config import AppSettings
from importlib import import_module


class BaseDebugSettings(AppSettings):
    ...


debug = import_module(ac.adapters.debug)
from acb.config import ac
from acb.config import AppSettings
from importlib import import_module


class BaseSftpSettings(AppSettings):
    ...


sftp = import_module(ac.adapters.storage)

from importlib import import_module

from acb.config import ac
from acb.config import Settings


class SecretsSettings(Settings):
    ...


secrets = import_module(f"acb.adapters.secrets.{ac.app.adapters['secrets']}").secrets

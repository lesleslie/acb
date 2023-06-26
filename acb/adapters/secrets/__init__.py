from importlib import import_module

from acb.config import ac
from acb.config import Settings


class SecretsBaseSettings(Settings):
    ...


secrets = import_module(f"acb.adapters.secrets.{ac.adapters['secrets']}").secrets

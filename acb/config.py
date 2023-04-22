import typing as t
from pathlib import Path
from pprint import pprint

from aiopath import AsyncPath
from pydantic import BaseSettings
from .actions import dump
from .actions import hash
from .actions import load
from .adapters import SecretManager


class AppConfig(BaseSettings):
    deployed = False
    basedir = Path().cwd()
    tmp = basedir / "tmp"
    config_path = basedir / "config.py"
    settings: list = None
    secrets: dict = None
    debug: bool = True
    deployed: bool = True if basedir.name == "app" else False

    async def init(self, deployed: bool = False):
        self.deployed = True if self.basedir.name == "app" else False
        # deployed = True if basedir.name == "srv" else False
        self.secrets = await SecretManager().init()
        print(f"{str(self.config_path.resolve())}")
        self.deployed = deployed
        self.debug = False if deployed else True
        pprint(self.settings)
        pprint(self.secrets)
        classes = dict()
        for s in [s for s in self.settings if "Settings" in s.__class__.__name__]:
            print(s, type(s))
            settings_module = s.__class__.__name__.replace("Settings", "").lower()
            print(settings_module)
            classes["settings_module"] = s()
        self.__init__(**classes)
        print("done")
        return self

    class Config:
        extra = "allow"


class AppSettings(BaseSettings):
    formatted: bool = False
    yml_settings: t.Any = None
    values: dict = None
    cls_name: str = None

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
        json_loads = load.json
        json_dumps = dump.json

    def __init__(self, **values: t.Any):
        super().__init__(**values)
        # name = self.__class__.__name__.replace("Settings", "").lower()
        # settings = ac.basedir / "settings"
        # for path in [
        #     p for p in settings.iterdir() if p.suffix == ".yml" and p.stem == name
        # ]:
        #     self.yml_settings = path.read_text()
        #     self.values = load.yml(self.yml_settings)
        #     current_hash = hash.crc32c(self.yml_settings)
        #     new_settings = dump.yml(values)
        #     new_hash = hash.crc32c(new_settings)
        #     if not ac.deployed and not self.formatted and current_hash != new_hash:
        #         print(f"Changes detected in {path} - formatting...")
        #         path.write_text(new_settings)
        #         self.formatted = True
        #     super().__init__(**values)

    # @classmethod
    # async def add_settings(self):
    #     setattr(ac, self.cls_name, self)

    async def __call__(self, ac):
        print("call")
        self.cls_name = self.__class__.__name__.replace("Settings", "").lower()
        settings = ac.basedir / "settings"
        for path in [
            AsyncPath(p)
            for p in settings.iterdir()
            if p.suffix == ".yml" and p.stem == self.cls_name
        ]:
            self.yml_settings = await path.read_text()
            self.values = await load.yml(self.yml_settings)
            current_hash = hash.crc32c(self.yml_settings)
            new_settings = await dump.yml(self.values)
            new_hash = await hash.acrc32c(new_settings)
            if not ac.deployed and not self.formatted and current_hash != new_hash:
                print(f"Changes detected in {path} - formatting...")
                await path.write_text(new_settings)
                self.formatted = True
                # pprint(self.values)
            super().__init__(**self.values)
        # setattr(ac, self.cls_name, self)

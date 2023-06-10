import sys
import typing as t
from importlib import import_module
from inspect import getsource
from pprint import pprint

from aiopath import AsyncPath
from inflection import camelize
from inflection import titleize
from inflection import underscore
from pydantic import BaseSettings
from pydantic import Extra
from .actions import dump
from .actions import load


class AppSettings(BaseSettings):
    class Config:
        extra = Extra.allow
        arbitrary_types_allowed = True

    async def __call__(self) -> "AppSettings":
        adapter_name = underscore(self.__class__.__name__.replace("Settings", ""))
        yml_path = ac.settings_path / adapter_name
        if not await yml_path.exists() and not ac.deployed:
            await dump.yaml(self.dict(), yml_path)
        yml_settings = await load.yaml(yml_path)
        if adapter_name == "debug":
            for adptr in [
                adptr
                for adptr in ac.enabled_adapters
                if adptr not in yml_settings.keys()
            ]:
                yml_settings[adptr] = False
        super().__init__(**yml_settings)
        print(1, yml_settings)
        setattr(ac, adapter_name, self)
        if not ac.deployed:
            await dump.yaml(yml_settings, yml_path)
        return self


class Debug(AppSettings):
    production = False
    main = False
    logger = False
    database = False
    cache = False
    mail = False


class App(AppSettings):
    project = "acb-project"
    name = "acb-app"
    title: t.Optional[str]
    adapters = {}

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.title = self.title or titleize(self.name)


class AppConfig(BaseSettings):
    pkgdir = AsyncPath(__file__).parent
    deployed: bool = False
    basedir: t.Optional[AsyncPath]
    tmp: t.Optional[AsyncPath]
    config_path: t.Optional[AsyncPath]
    settings_path: t.Optional[AsyncPath]
    adapter_categories = []
    enabled_adapters = []

    async def __call__(self, deployed: bool = False) -> None:
        self.basedir = AsyncPath().cwd()
        self.tmp = self.basedir / "tmp"
        self.config_path = self.basedir / "config.py"
        self.settings_path = self.basedir / "settings"
        await self.settings_path.mkdir(exist_ok=True)
        await self.tmp.mkdir(exist_ok=True)
        self.deployed = True if self.basedir.name == "app" else deployed
        # deployed = True if basedir.name == "srv" else False
        # self.debug = False if deployed else True
        # self.secrets = await SecretManager().init()
        mod_dir = self.basedir / "__pypackages__"
        sys.path.append(str(mod_dir))
        if not await self.config_path.exists():
            await self.config_path.write_text(
                f"import typing as t\n"
                f"from inflection import titleize\n"
                f"from acb.config import AppSettings\n"
                f"from acb.config import ac\n\n"
                f"{getsource(App)}"
            )
        # configs = dict()
        self.app = await App()()
        print(2, type(self.app), self.app)
        if self.basedir.name != "acb":
            app_settings = import_module("config")
            self.app = await app_settings.App()()
            self.debug = await Debug()()
            self.adapter_categories = [
                path.stem
                async for path in (ac.pkgdir / "adapters").iterdir()
                if path.is_dir and not path.name.startswith("__")
            ]
            print(3, self.adapter_categories)
            # all_mods = app_mods + list(ac.app.adapters)
            self.enabled_adapters = [
                adptr
                for adptr in self.app.adapters.items()
                if adptr in self.adapter_categories
            ]
            print(4, self.enabled_adapters)
        for category, adapter in self.app.adapters.items():
            module = import_module(".".join(["acb", "adapters", category, adapter]))
            adapter_settings = getattr(module, f"{camelize(adapter)}Settings")
            await adapter_settings()()
        pprint(self.dict())
        # super().__init__(**configs)

    class Config:
        extra = "allow"
        arbitrary_types_allowed = False


ac = AppConfig()

# asyncio.run(ac())


# class InspectStack(BaseModel):
#     @staticmethod
#     def calling_function():
#         frm = stack()[2]
#         return AsyncPath(getmodule(frm[0]).__file__).stem
#
#     @staticmethod
#     def calling_page(calling_frame):
#         calling_stack = getouterframes(calling_frame)
#         page = ""
#         for f in calling_stack:
#             if f[3] == "render_template_string":
#                 page = getargvalues(f[0]).locals["context"]["page"]
#         return page
#
#
# inspect_ = InspectStack()

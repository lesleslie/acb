import sys
import typing as t
from importlib import import_module
from inspect import currentframe
from inspect import getouterframes
from pprint import pprint
from random import choice
from re import search
from secrets import token_bytes
from secrets import token_urlsafe
from string import ascii_letters
from string import digits
from string import punctuation

from acb.actions import dump
from acb.actions import load
from aiopath import AsyncPath
from inflection import camelize
from inflection import titleize
from inflection import underscore
from pydantic_settings import BaseSettings


def gen_password(size: int) -> str:
    chars = ascii_letters + digits + punctuation
    return "".join(choice(chars) for _ in range(size))


def secret_alias(raw_name: str) -> str:
    calling_class = getouterframes(currentframe())
    for frame in [f for f in calling_class if f]:
        if frame.code_context[0].startswith("class"):
            secret_class = search("class\s(\w+)Se\w+\(", frame.code_context[0]).group(1)
            return f"{secret_class.lower()}_{raw_name}"


class BaseSecrets(BaseSettings, extra="allow", alias_generator=secret_alias):
    async def load_all(self, cls_dict) -> dict:
        secrets = await self.list()
        data = {}
        await self.secrets_dir.mkdir(exist_ok=True)
        for name in cls_dict.keys():
            secret = await self.load(name, secrets, cls_dict)
            data[name] = secret
            secret_path = self.secrets_dir / name
            await secret_path.write_text(secret)
        return data

    async def __call__(self) -> BaseSettings | dict:
        secrets_path: AsyncPath = ac.tmp / "secrets"
        if ac.debug.secrets:
            await secrets_path.rmdir()
        if not await self.secrets_path.exists():
            return await self.load_all(AppSecrets().model_dump())
        return AppSecrets(_secrets_dir=secrets_path)


class AppSecrets(BaseSecrets):
    # mailgun_api_key: t.Optional[str]
    # facebook_app_id: t.Optional[str]
    # facebook_app_secret: t.Optional[str]
    # firebase_api_key: t.Optional[str]
    # slack_api_key: t.Optional[str]
    # google_service_account: t.Optional[t.Any]
    # google_service_account_json: t.Optional[str]
    # google_maps_api_key: t.Optional[str]
    # google_maps_dev_api_key: t.Optional[str]
    # google_upload_json: t.Optional[str]
    # recaptcha_dev_key: t.Optional[str]
    # recaptcha_production_key: t.Optional[str]
    secret_key: str = token_urlsafe(32)
    secure_salt: str = str(token_bytes(32))
    mail_password: str = gen_password(10)

    # def __init__(self, **data: t.Any) -> None:
    #     super().__init__(**data)


pprint(AppSecrets().model_dump(by_alias=True))


class AppSettings(BaseSettings, extra="allow", arbitrary_types_allowed=True):
    async def __call__(self) -> "AppSettings":
        adapter_name = underscore(self.__class__.__name__.replace("Settings", ""))
        yml_path = ac.app_settings_path / f"{adapter_name}.yml"
        if not await yml_path.exists() and not ac.deployed:
            await dump.yaml(self.model_dump(), yml_path)
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
    production: bool = False
    main: bool = False
    # logger: bool = False
    # database: bool = False
    # cache: bool = False
    # mail: bool = False


class App(AppSettings):
    project: str = "acb-project"
    name: str = "acb-app"
    title: t.Optional[str] = None
    adapters: dict = {}

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.title = self.title or titleize(self.name)


class AppConfig(BaseSettings, extra="allow"):
    pkgdir: AsyncPath = AsyncPath(__file__).parent
    deployed: bool = False
    basedir: t.Optional[AsyncPath] = None
    tmp: t.Optional[AsyncPath] = None
    # app_config_path: t.Optional[AsyncPath]
    app_settings_path: t.Optional[AsyncPath] = None
    adapter_categories: list = []
    enabled_adapters: list = []
    secrets: t.Optional[BaseSettings] = None

    async def __call__(self, deployed: bool = False) -> None:
        self.basedir = AsyncPath().cwd()
        self.tmp = self.basedir / "tmp"
        # self.app_config_path = self.basedir / "config.py"
        self.app_settings_path = self.basedir / "settings"
        await self.app_settings_path.mkdir(exist_ok=True)
        await self.tmp.mkdir(exist_ok=True)
        self.deployed = True if self.basedir.name == "app" else deployed
        # deployed = True if basedir.name == "srv" else False
        # self.debug = False if deployed else True
        # self.secrets = await SecretManager().init()
        mod_dir = self.basedir / "__pypackages__"
        sys.path.append(str(mod_dir))
        self.app = await App()()
        print(2, type(self.app), self.app)
        if self.basedir.name != "acb":
            # app_settings = import_module("config")
            self.app = await AppSettings()()
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
            getattr(module, f"{camelize(adapter)}Secrets")

        pprint(self.model_dump())
        # super().__init__(**configs)


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

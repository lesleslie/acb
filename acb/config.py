import sys
import typing as t
from functools import lru_cache
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
from warnings import warn

from acb.actions import dump
from acb.actions import load
from aiopath import AsyncPath
from inflection import camelize
from inflection import titleize
from inflection import underscore
from pydantic import AnyUrl
from pydantic import SecretStr
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings
from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings.sources import PydanticBaseEnvSettingsSource
from pydantic_settings.sources import SettingsError
from pydantic_settings.utils import path_type_label
from pydantic_settings.utils import path_type_labels


def gen_password(size: int) -> str:
    chars = ascii_letters + digits + punctuation
    return "".join(choice(chars) for _ in range(size))


def secret_alias(raw_name: str) -> str:
    calling_class = getouterframes(currentframe())
    for frame in [f for f in calling_class if f]:
        if frame.code_context[0].startswith("class"):
            secret_class = search("class\s(\w+)Se\w+\(", frame.code_context[0]).group(1)
            return f"{secret_class.lower()}_{raw_name}"


class SecretsFileSource(PydanticBaseEnvSettingsSource):
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        secrets_dir: str | AsyncPath | None = None,
        case_sensitive: bool | None = None,
        env_prefix: str | None = None,
    ) -> None:
        super().__init__(settings_cls, case_sensitive, env_prefix)
        self.secrets_dir = (
            secrets_dir if secrets_dir is not None else self.config.get("secrets_dir")
        )

    async def path_type_label(p: AsyncPath) -> str:
        assert await p.exists(), "path does not exist"
        for method, name in path_type_labels.items():
            if getattr(p, method)():
                return name
        return "unknown"

    async def __call__(self) -> dict[str, t.Any]:
        secrets: dict[str, str | None] = {}

        if self.secrets_dir is None:
            return secrets

        self.secrets_path = await AsyncPath(self.secrets_dir).expanduser()

        if not self.secrets_path.exists():
            warn(f'directory "{self.secrets_path}" does not exist')
            return secrets

        if not self.secrets_path.is_dir():
            raise SettingsError(
                f"secrets_dir must reference a directory, not a "
                f"{path_type_label(self.secrets_path)}"
            )

        return super().__call__()

    @classmethod
    async def find_case_path(
        cls, dir_path: AsyncPath, file_name: str, case_sensitive: bool
    ) -> AsyncPath | None:
        async for f in dir_path.iterdir():
            if f.name == file_name:
                return f
            elif not case_sensitive and f.name.lower() == file_name.lower():
                return f
        return None

    async def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[t.Any, str, bool]:
        for field_key, env_name, value_is_complex in self._extract_field_info(
            field, field_name
        ):
            path = self.find_case_path(self.secrets_path, env_name, self.case_sensitive)
            if not path:
                # path does not exist, we curently don't return a warning for this
                continue

            if await path.is_file():
                return (await path.read_text()).strip(), field_key, value_is_complex
            else:
                warn(
                    f'attempted to load secret file "{path}" but found a {path_type_label(path)} instead.',
                    stacklevel=4,
                )

        return None, field_key, value_is_complex

    def __repr__(self) -> str:
        return f"FileSecretsSource(secrets_dir={self.secrets_dir!r})"


class SettingsSource(PydanticBaseSettingsSource):
    adapter_name: t.Optional[...]

    async def __call__(self) -> t.Dict[str, t.Any]:
        self.adapter_name: str = underscore(
            self.settings_cls.__name__.replace("Settings", "")
        )
        d: t.Dict[str, t.Any] = {}
        for field_name, field in dict(self.settings_cls.model_fields).items():
            field_value, field_key, value_is_complex = self.get_field_value(
                field, field_name
            )
            field_value = self.prepare_field_value(
                field_name, field, field_value, value_is_complex
            )
            if field_value is not None:
                d[field_key] = field_value
        setattr(ac, self.adapter_name, self)
        return d


class SecretsManagerSource(SettingsSource):
    @lru_cache
    async def load_secrets(self) -> dict:
        path: AsyncPath = ac.tmp / "secrets"
        if ac.debug.secrets:
            await path.rmdir()
        await path.mkdir(exist_ok=True)
        manager = import_module("acb.adapters.secrets").secrets
        manager_secrets = await manager.list()
        pprint(manager_secrets)
        for name, value in dict(self.settings_cls):
            print(name)
            secret_path = path / name
            if not await secret_path.exists():
                if name not in manager_secrets:
                    await manager.create(name, value)
                secret = await manager.load(name)
                await secret_path.write_text(secret)
        return manager_secrets

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> t.Tuple[t.Any, str, bool]:
        secrets_settings = await self.load_secrets()
        return secrets_settings[field_name], field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: t.Any, value_is_complex: bool
    ) -> str:
        return value.removeprefix(f"{self.adapter_name}_")


class YamlSettingsSource(PydanticBaseSettingsSource):
    adapter_name: t.Optional[...]

    @lru_cache
    async def load_yml_settings(self) -> dict:
        yml_path = ac.app_settings_path / f"{self.adapter_name}.yml"
        if not await yml_path.exists() and not ac.deployed:
            await dump.yaml(dict(self.settings_cls), yml_path)
        yml_settings = await load.yaml(yml_path)
        if self.adapter_name == "debug":
            for adptr in [
                adptr
                for adptr in ac.enabled_adapters
                if adptr not in yml_settings.keys()
            ]:
                yml_settings[adptr] = False
        if not ac.deployed:
            await dump.yaml(yml_settings, yml_path)
        return yml_settings

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> t.Tuple[t.Any, str, bool]:
        yml_settings = await self.load_yml_settings()
        return yml_settings, field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: t.Any, value_is_complex: bool
    ) -> t.Any:
        return value


# class Settings(BaseSettings, extra="allow", arbitrary_types_allowed=True):
class Settings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: t.Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> t.Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            YamlSettingsSource(settings_cls),
            SecretsManagerSource(settings_cls),
            SecretsFileSource(settings_cls),
        )


class DebugSettings(Settings):
    production: bool = False
    main: bool = False
    secrets: bool = False
    logger: bool = False


class AppSettings(Settings):
    project: str = "myproject"
    name: str = "myapp"
    title: t.Optional[str] = None
    domain: t.Optional[AnyUrl] = None
    adapters: dict = {}
    secret_key: SecretStr = token_urlsafe(32)
    secure_salt: SecretStr = str(token_bytes(32))

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.title = self.title or titleize(self.name)


class AppConfig(BaseSettings, extra="allow"):
    pkgdir: AsyncPath = AsyncPath(__file__).parent
    deployed: bool = False
    basedir: t.Optional[AsyncPath] = None
    tmp: t.Optional[AsyncPath] = None
    app_settings_path: t.Optional[AsyncPath] = None
    adapter_categories: list = []
    enabled_adapters: list = []
    secrets: t.Optional[BaseSettings] = None

    async def __call__(self, deployed: bool = False) -> None:
        self.basedir = AsyncPath().cwd()
        self.tmp = self.basedir / "tmp"
        self.app_settings_path = self.basedir / "settings"
        await self.app_settings_path.mkdir(exist_ok=True)
        await self.tmp.mkdir(exist_ok=True)
        self.deployed = True if self.basedir.name == "app" else deployed
        # deployed = True if basedir.name == "srv" else False
        # self.debug = False if deployed else True
        mod_dir = self.basedir / "__pypackages__"
        sys.path.append(str(mod_dir))
        if self.basedir.name != "acb":
            self.adapter_categories = [
                path.stem
                async for path in (ac.pkgdir / "adapters").iterdir()
                if path.is_dir and not path.name.startswith("__")
            ]
            self.enabled_adapters = [
                adptr
                for adptr in self.app.adapters.keys()
                if adptr in self.adapter_categories
            ]
            self.app = await AppSettings()
            self.debug = await DebugSettings()
            for category, adapter in self.app.adapters.items():
                module = import_module(".".join(["acb", "adapters", category, adapter]))
                adapter_settings = getattr(module, f"{camelize(adapter)}Settings")
                await adapter_settings()


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

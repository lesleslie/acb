import asyncio
import sys
import typing as t
from abc import ABC
from abc import abstractmethod
from importlib import import_module
from pathlib import Path
from random import choice
from secrets import token_bytes
from secrets import token_urlsafe
from string import ascii_letters
from string import digits
from string import punctuation
from warnings import warn

import nest_asyncio
from acb.actions import dump
from acb.actions import load
from aiopath import AsyncPath
from async_lru import alru_cache
from icecream import ic
from inflection import camelize
from inflection import titleize
from inflection import underscore
from pydantic import AliasChoices
from pydantic import AliasPath
from pydantic import AnyUrl
from pydantic import BaseModel
from pydantic import SecretStr
from pydantic._internal._utils import deep_update
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from pydantic_settings.sources import _annotation_is_complex
from pydantic_settings.sources import SettingsError
from pydantic_settings.utils import path_type_label
from pydantic_settings.utils import path_type_labels

# deployed = True if basedir.name == "srv" else False
deployed = True if Path.cwd().name == "app" else False

project: str = ""
app_name: str = ""
app_secrets: set = set()


def gen_password(size: int) -> str:
    chars = ascii_letters + digits + punctuation
    return "".join(choice(chars) for _ in range(size))


# def secret_alias(raw_name: str) -> str:
#     calling_class = getouterframes(currentframe())
#     for frame in [f for f in calling_class if f]:
#         if frame.code_context[0].startswith("class"):
#             secret_class = (search("class\s(\w+)Se\w+\(", frame.code_context[
#             0]).group(1)
#               )
#             return f"{secret_class.lower()}_{raw_name}"


def load_adapter(adapter) -> t.Any:
    adapter_module = import_module(
        f"acb.adapters.{adapter}.{ac.enabled_adapters[adapter]}"
    )
    return getattr(adapter_module, adapter)


class PydanticBaseSettingsSource(ABC):
    def __init__(self, settings_cls: type["Settings"]) -> None:
        self.settings_cls = settings_cls
        self.config = settings_cls.model_config

    @abstractmethod
    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[t.Any, str, bool]:
        pass

    @staticmethod
    def field_is_complex(field: FieldInfo) -> bool:
        return _annotation_is_complex(field.annotation, field.metadata)

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: t.Any, value_is_complex: bool
    ) -> t.Any:
        if self.field_is_complex(field) or value_is_complex:
            return load.json(value)
        return value

    @abstractmethod
    async def __call__(self) -> dict[str, t.Any]:
        pass


class InitSettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self, settings_cls: type["Settings"], init_kwargs: dict[str, t.Any]
    ) -> None:
        self.init_kwargs = init_kwargs
        super().__init__(settings_cls)

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[t.Any, str, bool]:
        return None, "", False

    async def __call__(self) -> dict[str, t.Any]:
        return self.init_kwargs

    def __repr__(self) -> str:
        return f"InitSettingsSource(init_kwargs={self.init_kwargs!r})"


class FileSecretsSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: type["Settings"],
        secrets_dir: str | AsyncPath | None = None,
    ) -> None:
        super().__init__(settings_cls)
        self.secrets_dir = (
            secrets_dir if secrets_dir is not None else self.config.get("secrets_dir")
        )

    @staticmethod
    async def path_type_label(p: AsyncPath) -> str:
        if await p.exists():
            for method, name in path_type_labels.items():
                if getattr(p, method)():
                    return name
            return "unknown"

    @classmethod
    async def find_case_path(
        cls,
        dir_path: AsyncPath,
        file_name: str,
    ) -> AsyncPath | None:
        async for f in dir_path.iterdir():
            if f.name == file_name:
                return f
            elif f.name.lower() == file_name.lower():
                return f
        return None

    def _extract_field_info(
        self, field: FieldInfo, field_name: str
    ) -> list[tuple[str, str, bool]]:
        field_info: list[tuple[str, str, bool]] = []
        if isinstance(field.validation_alias, (AliasChoices, AliasPath)):
            v_alias: str | list[str | int] | list[
                list[str | int]
            ] | None = field.validation_alias.convert_to_aliases()
        else:
            v_alias = field.validation_alias

        if v_alias:
            if isinstance(v_alias, list):  # AliasChoices, AliasPath
                for alias in v_alias:
                    if isinstance(alias, str):  # AliasPath
                        field_info.append(
                            (
                                alias,
                                alias,
                                True if len(alias) > 1 else False,
                            )
                        )
                    elif isinstance(alias, list):  # AliasChoices
                        first_arg = t.cast(
                            str, alias[0]
                        )  # first item of an AliasChoices must be a str
                        field_info.append(
                            (
                                first_arg,
                                first_arg,
                                True if len(alias) > 1 else False,
                            )
                        )
            else:  # string validation alias
                field_info.append((v_alias, v_alias, False))
        else:
            field_info.append(
                (
                    field_name,
                    field_name,
                    False,
                )
            )
        return field_info

    async def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[t.Any, str, bool]:
        for field_key, env_name, value_is_complex in self._extract_field_info(
            field, field_name
        ):
            path = await self.find_case_path(self.secrets_path, env_name)
            if not path:
                continue
            if await path.is_file():
                return (
                    SecretStr((await path.read_text()).strip()),
                    field_key,
                    value_is_complex,
                )
            else:
                warn(
                    f'attempted to load secret file "{path}" but found a '
                    f"{await self.path_type_label(path)} instead",
                    stacklevel=4,
                )
        return None, field_key, value_is_complex

    async def __call__(self) -> dict[str, t.Any]:
        global app_name, app_secrets
        data: dict[str, t.Any] = {}
        self.adapter_name: str = underscore(
            self.settings_cls.__name__.replace("Settings", "")
        )
        if self.adapter_name == "debug":
            return data
        if self.secrets_dir is None:
            return data
        self.secrets_path = await AsyncPath(self.secrets_dir).expanduser()
        if not await self.secrets_path.exists():
            warn(f'directory "{self.secrets_path}" does not exist')
            return data
        if not await self.secrets_path.is_dir():
            raise SettingsError(
                f"secrets_dir must reference a directory, not a "
                f"{path_type_label(self.secrets_path)}"
            )
        for field_name, field in self.settings_cls.model_fields.items():
            try:
                field_value, field_key, value_is_complex = await self.get_field_value(
                    field, "_".join([self.adapter_name, field_name])
                )
            except Exception as e:
                raise SettingsError(
                    f'error getting value for field "{field_name}" from '
                    f'source "{self.__class__.__name__}"'
                ) from e
            try:
                field_value = self.prepare_field_value(
                    field_name, field, field_value, value_is_complex
                )
            except ValueError:
                raise SettingsError(
                    f'error parsing value for field "{field_name}" from'
                    f' source "{self.__class__.__name__}"'
                )
            if field_value is not None:
                app_secrets.add(field_key)
                data[field_name] = field_value
        return data

    def __repr__(self) -> str:
        return f"FileSecretsSource(secrets_dir={self.secrets_dir!r})"


class ManagerSecretsSource(FileSecretsSource):
    adapter_name: t.Optional[str] = None

    @alru_cache
    async def get_manager(self):
        global project, app_name
        manager = load_adapter("secrets")
        await manager.init(project=project, app_name=app_name)
        return manager

    async def load_secrets(self) -> t.NoReturn:
        global project, app_name, app_secrets
        data: dict[str, t.Any] = {}
        model_secrets = {
            "_".join((self.adapter_name, n)): v
            for n, v in self.settings_cls.model_fields.items()
            if v.annotation is SecretStr
        }
        unfetched_secrets = {
            n: v for n, v in model_secrets.items() if n not in app_secrets
        }
        if unfetched_secrets:
            manager = await self.get_manager()
            manager_secrets = await manager.list(self.adapter_name)
            for field_key, field_value in unfetched_secrets.items():
                field_name = field_key.removeprefix(f"{self.adapter_name}_")
                stored_field_key = "_".join((app_name, field_key))
                secret_path = ac.secrets_path / field_key
                if not await secret_path.exists():
                    if field_key not in manager_secrets:
                        await manager.create(
                            stored_field_key, field_value.default.get_secret_value()
                        )
                    secret = await manager.get(stored_field_key)
                    await secret_path.write_text(secret)
                    data[field_name] = secret
                app_secrets.add(field_key)
        return data

    async def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> t.Tuple[t.Any, str, bool]:
        return field, field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: t.Any, value_is_complex: bool
    ) -> str:
        return value

    async def __call__(self) -> dict[str, t.Any]:
        data: dict[str, t.Any] = {}
        self.adapter_name: str = underscore(
            self.settings_cls.__name__.replace("Settings", "")
        )
        if self.adapter_name == "debug":
            return data
        return await self.load_secrets()
        # return await super().__call__()


class YamlSettingsSource(PydanticBaseSettingsSource):
    adapter_name: t.Optional[str] = None

    @alru_cache
    async def load_yml_settings(self) -> dict:
        global project, app_name
        if self.adapter_name == "secrets":
            return {}
        yml_path = AsyncPath.cwd() / "settings" / f"{self.adapter_name}.yml"
        if not await yml_path.exists() and not deployed:
            await yml_path.touch(exist_ok=True)
            dump_settings = {
                k: v.default
                for k, v in self.settings_cls.model_fields.items()
                if v.annotation is not SecretStr
            }
            await dump.yaml(dump_settings, yml_path)
        yml_settings = await load.yaml(yml_path)
        if self.adapter_name == "debug":
            for adptr in [
                adptr
                for adptr in ac.enabled_adapters
                if adptr not in yml_settings.keys()
            ]:
                yml_settings[adptr] = False
        if not deployed:
            await dump.yaml(yml_settings, yml_path)
        if self.adapter_name == "app":
            project = yml_settings["project"]
            app_name = yml_settings["name"]
        return yml_settings

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> t.Tuple[t.Any, str, bool]:
        return field, field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: t.Any, value_is_complex: bool
    ) -> t.Any:
        return value

    async def __call__(self) -> t.Dict[str, t.Any]:
        self.adapter_name: str = underscore(
            self.settings_cls.__name__.replace("Settings", "")
        )
        data: t.Dict[str, t.Any] = {}
        for field_name, field in (await self.load_yml_settings()).items():
            field_value, field_key, value_is_complex = self.get_field_value(
                field, field_name
            )
            field_value = self.prepare_field_value(
                field_name, field, field_value, value_is_complex
            )
            if field_value is not None:
                data[field_key] = field_value
        return data


class Settings(BaseModel):
    model_config = SettingsConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,
        validate_default=True,
        secrets_dir=None,
        protected_namespaces=("model_", "settings_"),
        # alias_generator=secret_alias,
    )

    def __init__(
        __pydantic_self__,
        _secrets_dir: str | Path | None = None,
        **values: t.Any,
    ) -> None:
        nest_asyncio.apply()
        build_settings = __pydantic_self__._settings_build_values(
            values,
            _secrets_dir=_secrets_dir,
        )
        build_settings = asyncio.run(build_settings)
        super().__init__(**build_settings)

    async def _settings_build_values(
        self,
        init_kwargs: dict[str, t.Any],
        _secrets_dir: str | AsyncPath | None = None,
    ) -> dict[str, t.Any]:
        secrets_dir = (
            _secrets_dir
            if _secrets_dir is not None
            else self.model_config.get("secrets_dir")
        )
        init_settings = InitSettingsSource(self.__class__, init_kwargs=init_kwargs)
        file_secrets_settings = FileSecretsSource(
            self.__class__,
            secrets_dir=secrets_dir,
        )
        sources = self.settings_customise_sources(
            self.__class__,
            init_settings=init_settings,
            file_secrets_settings=file_secrets_settings,
        )
        if sources:
            return deep_update(*reversed([await source() for source in sources]))
        return {}

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: t.Type["Settings"],
        init_settings: PydanticBaseSettingsSource,
        file_secrets_settings: PydanticBaseSettingsSource,
    ) -> tuple[
        PydanticBaseSettingsSource, YamlSettingsSource, ..., ManagerSecretsSource
    ]:
        return (
            init_settings,
            YamlSettingsSource(settings_cls),
            file_secrets_settings,
            ManagerSecretsSource(settings_cls),
        )


class DebugSettings(Settings):
    production: bool = False
    main: bool = False
    secrets: bool = False
    logger: bool = False
    config: bool = False


class AppSettings(Settings):
    project: str = "myproject"
    name: str = "myapp"
    title: t.Optional[str] = None
    domain: t.Optional[AnyUrl] = None
    secret_key: SecretStr = SecretStr(token_urlsafe(32))
    secure_salt: SecretStr = SecretStr(str(token_bytes(32)))

    def model_post_init(self, __context: t.Any) -> None:
        self.title = self.title or titleize(self.name)


class AppConfig(BaseSettings, extra="allow"):
    pkgdir: AsyncPath = AsyncPath(__file__).parent
    basedir: AsyncPath = AsyncPath.cwd()
    deployed: bool = deployed
    tmp: t.Optional[AsyncPath] = None
    app_settings_path: t.Optional[AsyncPath] = None
    adapter_settings_path: t.Optional[AsyncPath] = None
    available_adapters: dict[str, t.Any] = {}
    adapter_categories: list = []
    enabled_adapters: dict[str, t.Any] = {}
    app: t.Optional[Settings] = None
    debug: t.Optional[Settings] = None

    def model_post_init(self, __context: t.Any) -> None:
        self.tmp = self.basedir / "tmp"
        self.app_settings_path = self.basedir / "settings"
        self.adapter_settings_path = self.app_settings_path / "adapters.yml"
        self.secrets_path = self.basedir / "tmp" / "secrets"
        self.deployed = True if self.basedir.name == "app" else deployed

    async def init(self, deployed: bool = False) -> None:
        global enabled_adapters
        self.deployed = deployed
        for path in (
            self.app_settings_path,
            self.tmp,
            self.app_settings_path,
            self.secrets_path,
        ):
            await path.mkdir(exist_ok=True)
        mod_dir = self.basedir / "__pypackages__"
        sys.path.append(str(mod_dir))
        initialized_adapter_settings = {}
        if self.basedir.name != "acb":
            self.adapter_categories = [
                path.stem
                async for path in (self.pkgdir / "adapters").iterdir()
                if path.is_dir and not path.name.startswith("__")
            ]
            initialized_adapter_settings["adapter_categories"] = self.adapter_categories
            if not await self.adapter_settings_path.exists() and not self.deployed:
                await dump.yaml(
                    {cat: None for cat in self.adapter_categories},
                    self.adapter_settings_path,
                )
            self.available_adapters = await load.yaml(self.adapter_settings_path)
            initialized_adapter_settings["available_adapters"] = self.available_adapters
            self.enabled_adapters = {
                c: a
                for c, a in self.available_adapters.items()
                if c in self.adapter_categories and a
            }
            initialized_adapter_settings["enabled_adapters"] = self.enabled_adapters
            self.debug = DebugSettings()
            initialized_adapter_settings["debug"] = self.debug
            ic(self.debug.model_dump())
            try:
                self.app = AppSettings(_secrets_dir=self.secrets_path)
                initialized_adapter_settings["app"] = self.app
                ic(self.app.model_dump())
            except ModuleNotFoundError:
                warn("no secrets adapter configured")
                sys.exit()
            for adapter, module in self.enabled_adapters.items():
                if adapter == "secrets":
                    continue
                module = import_module(".".join(["acb", "adapters", adapter, module]))
                adapter_settings = getattr(module, f"{camelize(adapter)}Settings")
                initialized_settings = adapter_settings(_secrets_dir=self.secrets_path)
                ic(adapter)
                ic(initialized_settings.model_dump())
                initialized_adapter_settings[adapter] = initialized_settings
            super().__init__(**initialized_adapter_settings)
            for adapter in [a for a in self.enabled_adapters if a != "secrets"]:
                await load_adapter(adapter).init()


ac = AppConfig()

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

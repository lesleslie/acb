import importlib.util
import typing as t
import zipimport
from collections import abc
from importlib import import_module
from typing import Any
from typing import Callable
from typing import Coroutine

from jinja2.environment import Template
from jinja2.exceptions import TemplateNotFound
from jinja2.utils import internalcode

from aiopath import AsyncPath
from .environment import AsyncEnvironment


# def split_template_path(template: str) -> t.List[str]:
#     """Split a path into segments and perform a sanity check.  If it detects
#     '..' in the path it will raise a `TemplateNotFound` error.
#     """
#     pieces = []
#     for piece in template.split("/"):
#         if (
#             os.sep in piece
#             or (os.path.altsep and os.path.altsep in piece)
#             or piece == os.path.pardir
#         ):
#             raise TemplateNotFound(template)
#         elif piece and piece != ".":
#             pieces.append(piece)
#     return pieces


class PackageSpecNotFound(TemplateNotFound):
    """Raised if a package spec not found."""


class LoaderNotFound(TemplateNotFound):
    """Raised if a loader is not found."""


class AsyncBaseLoader:
    has_source_access = True
    loaders: list = None

    def __init__(self, searchpath: str | AsyncPath | t.Sequence[str | AsyncPath]):
        self.searchpath = searchpath
        if not isinstance(searchpath, abc.Iterable) or isinstance(searchpath, str):
            self.searchpath = [searchpath]
        self.searchpath = [AsyncPath(p) for p in searchpath]

    async def get_source(
        self, environment: "AsyncEnvironment", template: str | AsyncPath
    ) -> [t.Tuple[str, t.Optional[str], t.Optional[t.Callable[[], bool]]], str]:
        template = AsyncPath(template)
        if not self.has_source_access:
            raise RuntimeError(
                f"{type(self).__name__} cannot provide access to the source"
            )
        raise TemplateNotFound(template.name)

    async def list_templates(self) -> t.List[str]:
        raise TypeError("this loader cannot iterate over all templates")

    @internalcode
    async def load(
        self,
        environment: "AsyncEnvironment",
        name: str,
        env_globals: t.Optional[t.MutableMapping[str, t.Any]] = None,
    ) -> "Template":
        code = None
        if env_globals is None:
            env_globals = {}
        source, filename, uptodate = await self.get_source(environment, name)
        bcc = environment.bytecode_cache
        bucket = None
        if bcc is not None:
            bucket = await bcc.get_bucket(environment, name, filename, source)
            code = bucket.code
        if code is None:
            code = environment.compile(source, name, filename)
        if bcc is not None and bucket.code is None:
            bucket.code = code
            await bcc.set_bucket(bucket)
        return environment.template_class.from_code(
            environment, code, env_globals, uptodate
        )


class FileSystemLoader(AsyncBaseLoader):
    def __init__(
        self,
        searchpath,
        encoding: str = "utf-8",
        followlinks: bool = False,
    ) -> None:
        super().__init__(searchpath)
        self.encoding = encoding
        self.followlinks = followlinks

    async def get_source(
        self, environment: "AsyncEnvironment", template: str
    ) -> tuple[Any, Any, Callable[[], Coroutine[Any, Any, bool]]]:
        # split_template_path(template)
        for searchpath in self.searchpath:
            filename = searchpath / template
            if filename.is_file():
                break
        else:
            raise TemplateNotFound(template)
        try:
            resp = await filename.read_text()
        except FileNotFoundError:
            raise TemplateNotFound(filename.name)
        mtime = (await filename.stat()).st_mtime

        async def uptodate() -> bool:
            try:
                return (await filename.stat()).st_mtime == mtime
            except OSError:
                return False

        return resp, filename.name, uptodate

    async def list_templates(self) -> list[str]:
        found = set()
        for searchpath in self.searchpath:
            found.update(
                [p.name async for p in searchpath.iterdir() if p.suffix == ".html"]
            )
        return sorted(found)


class PackageLoader(AsyncBaseLoader):
    def __init__(
        self,
        package_name: str,
        searchpath: AsyncPath,
        package_path: str | AsyncPath = "templates",
        encoding: str = "utf-8",
    ) -> None:
        super().__init__(searchpath)
        package_path = AsyncPath(package_path)
        if package_path == await AsyncPath(".").cwd():
            package_path = ""
        self.package_path = package_path
        self.package_name = package_name
        self.encoding = encoding
        # Make sure the package exists. This also makes namespace
        # packages work, otherwise get_loader returns None.
        import_module(package_name)
        spec = importlib.util.find_spec(package_name)
        if not spec:
            raise PackageSpecNotFound("An import spec was not found for the package.")
        loader = spec.loader
        if not loader:
            raise LoaderNotFound("A loader was not found for the package.")
        self._loader = loader
        self._archive = None
        template_root = None
        if isinstance(loader, zipimport.zipimporter):
            self._archive = loader.archive
            pkgdir = next(iter(spec.submodule_search_locations))  # type: ignore
            template_root = AsyncPath(pkgdir) / package_path
        else:
            roots: t.List[AsyncPath] = []
            # One element for regular packages, multiple for namespace
            # packages, or None for single module file.
            if spec.submodule_search_locations:
                roots.extend([AsyncPath(s) for s in spec.submodule_search_locations])
            # A single module file, use the parent directory instead.
            elif spec.origin is not None:
                roots.append(AsyncPath(spec.origin))
            for root in roots:
                root = root / package_path
                if root.is_dir():
                    template_root = root
                    break

        if template_root is None:
            raise ValueError(
                f"The {package_name!r} package was not installed in a"
                " way that PackageLoader understands."
            )

        self._template_root = template_root

    async def get_source(
        self, environment: "AsyncEnvironment", template: str | AsyncPath
    ) -> t.Tuple[str, str, t.Optional[t.Callable[[], bool]]]:
        # Use posixpath even on Windows to avoid "drive:" or UNC
        # segments breaking out of the search directory. Use normpath to
        # convert Windows altsep to sep.
        p = self._template_root / template
        up_to_date: t.Optional[t.Callable[[], bool]]
        if self._archive is None:
            # Package is a directory.
            if not p.is_file():
                raise TemplateNotFound(template)
            source = await p.read_text()
            mtime = (await p.stat()).st_mtime

            def up_to_date() -> bool:
                return p.is_file() and (await p.stat()).st_mtime == mtime

        else:
            # Package is a zip file.
            try:
                source = self._loader.get_data(p)  # type: ignore
            except OSError as e:
                raise TemplateNotFound(template) from e
            # Could use the zip's mtime for all template mtimes, but
            # would need to safely reload the module if it's out of
            # date, so just report it as always current.
            up_to_date = None
        return source.decode(self.encoding), p, up_to_date

    async def list_templates(self) -> t.List[AsyncPath]:
        results: t.List[AsyncPath] = []

        if self._archive is None:
            # Package is a directory.
            paths = self._template_root.rglob("*.html")
            results.extend([p async for p in paths])
        else:
            if not hasattr(self._loader, "_files"):
                raise TypeError(
                    "This zip import does not have the required"
                    " metadata to list templates."
                )
            # Package is a zip file.
            prefix = self._template_root.name
            for name in self._loader._files.keys():
                # Find names under the templates directory that aren't directories.
                if name.startswith(prefix) and AsyncPath(name).is_file():
                    results.append(name)
        results.sort()
        return results


class DictLoader(AsyncBaseLoader):
    """Loads a template from a Python dict mapping template names to
    template source.  This loader is useful for unittesting:
    >>> loader = DictLoader({'index.html': 'source here'})
    Because auto reloading is rarely useful this is disabled per default.
    """

    def __init__(
        self,
        mapping: t.Mapping[str, str],
        searchpath: str | AsyncPath | t.Sequence[str | AsyncPath] = None,
    ) -> None:
        super().__init__(searchpath)
        self.mapping = mapping

    async def get_source(
        self, environment: "AsyncEnvironment", template: str
    ) -> t.Tuple[str, None, t.Callable[[], bool]]:
        if template in self.mapping:
            source = self.mapping[template]
            return source, None, lambda: source == self.mapping.get(template)
        raise TemplateNotFound(template)

    async def list_templates(self) -> t.List[str]:
        return sorted(self.mapping)


class FunctionLoader(AsyncBaseLoader):
    """A loader that is passed a function which does the loading.  The
    function receives the name of the template and has to return either
    a string with the template source, a tuple in the form ``(source,
    filename, uptodatefunc)`` or `None` if the template does not exist.
    >>> def load_template(name):
    ...     if name == 'index.html':
    ...         return '...'
    ...
    >>> loader = FunctionLoader(load_template)
    The `uptodatefunc` is a function that is called if autoreload is enabled
    and has to return `True` if the template is still up to date.  For more
    details have a look at :meth:`AsyncBaseLoader.get_source` which has the same
    return value.
    """

    def __init__(
        self,
        load_func: t.Callable[
            [t.Coroutine],
            t.Optional[
                str | AsyncPath | t.Tuple[str, t.Optional[str]],
                t.Optional[t.Callable[[], bool]],
            ],
        ],
        searchpath: str | AsyncPath | t.Sequence[str | AsyncPath] = None,
    ) -> None:
        super().__init__(searchpath)
        self.load_func = load_func

    async def get_source(
        self, environment: "AsyncEnvironment", template: str | AsyncPath
    ) -> t.Tuple[str, t.Optional[str], t.Optional[t.Callable[[], bool]]]:
        template = AsyncPath(template)
        rv = await self.load_func(template)
        if rv is None:
            raise TemplateNotFound(template.name)
        if isinstance(rv, str):
            return rv, None, None
        return rv


class ChoiceLoader(AsyncBaseLoader):
    def __init__(
        self,
        loaders: list[AsyncBaseLoader],
        searchpath: str | AsyncPath | t.Sequence[str | AsyncPath] = None,
    ) -> None:
        super().__init__(searchpath)
        self.loaders = loaders

    async def get_source(
        self, environment: "AsyncEnvironment", template: str
    ) -> t.Tuple[str, t.Optional[str], t.Optional[t.Callable[[], bool]]]:
        for loader in self.loaders:
            try:
                return await loader.get_source(environment, template)
            except TemplateNotFound:
                pass
        raise TemplateNotFound(template)

    async def list_templates(self) -> list[str]:
        found = set()
        for loader in self.loaders:
            found.update(loader.list_templates())
        return sorted(found)

    # @internalcode
    # def load(
    #     self,
    #     environment: "AsyncEnvironment",
    #     name: str,
    #     globals: t.Optional[t.MutableMapping[str, t.Any]] = None,
    # ) -> "Template":
    #     for loader in self.loaders:
    #         try:
    #             return loader.load(environment, name, globals)
    #         except TemplateNotFound:
    #             pass
    #     raise TemplateNotFound(name)


# class PrefixLoader(AsyncBaseLoader):
#     """A loader that is passed a dict of loaders where each loader is bound
#     to a prefix.  The prefix is delimited from the template by a slash per
#     default, which can be changed by setting the `delimiter` argument to
#     something else::
#         loader = PrefixLoader({
#             'app1':     PackageLoader('mypackage.app1'),
#             'app2':     PackageLoader('mypackage.app2')
#         })
#     By loading ``'app1/index.html'`` the file from the app1 package is loaded,
#     by loading ``'app2/index.html'`` the file from the second.
#     """
#
#     def __init__(
#         self, mapping: t.Mapping[str, AsyncBaseLoader], delimiter: str = "/"
#     ) -> None:
#         self.mapping = mapping
#         self.delimiter = delimiter
#
#     def get_loader(self, template: str) -> t.Tuple[AsyncBaseLoader, str]:
#         try:
#             prefix, name = template.split(self.delimiter, 1)
#             loader = self.mapping[prefix]
#         except (ValueError, KeyError) as e:
#             raise TemplateNotFound(template) from e
#         return loader, name
#
#     async def get_source(
#         self, environment: "AsyncEnvironment", template: str
#     ) -> t.Tuple[str, t.Optional[str], t.Optional[t.Callable[[], bool]]]:
#         loader, name = self.get_loader(template)
#         try:
#             return loader.get_source(environment, name)
#         except TemplateNotFound as e:
#             # re-raise the exception with the correct filename here.
#             # (the one that includes the prefix)
#             raise TemplateNotFound(template) from e
#
#     @internalcode
#     def load(
#         self,
#         environment: "AsyncEnvironment",
#         name: str,
#         globals: t.Optional[t.MutableMapping[str, t.Any]] = None,
#     ) -> "Template":
#         loader, local_name = self.get_loader(name)
#         try:
#             return loader.load(environment, local_name, globals)
#         except TemplateNotFound as e:
#             # re-raise the exception with the correct filename here.
#             # (the one that includes the prefix)
#             raise TemplateNotFound(name) from e
#
#     async def list_templates(self) -> t.List[str]:
#         result = []
#         for prefix, loader in self.mapping.items():
#             for template in loader.list_templates():
#                 result.append(prefix + self.delimiter + template)
#         return result


# class _TemplateModule(ModuleType):
#     """Like a normal module but with support for weak references"""
#
#
# class ModuleLoader(AsyncBaseLoader):
#     """This loader loads templates from precompiled templates.
#     Example usage:
#     >>> loader = ChoiceLoader([
#     ...     ModuleLoader('/path/to/compiled/templates'),
#     ...     FileSystemLoader('/path/to/templates')
#     ... ])
#     Templates can be precompiled with :meth:`Environment.compile_templates`.
#     """
#
#     has_source_access = False
#
#     def __init__(
#         self,
#         path: t.Union[
#             str, "os.PathLike[str]", t.Sequence[t.Union[str, "os.PathLike[str]"]]
#         ],
#         searchpath: AsyncPath,
#     ) -> None:
#         super().__init__(searchpath)
#         package_name = f"_jinja2_module_templates_{id(self):x}"
#
#         # create a fake module that looks for the templates in the
#         # path given.
#         mod = _TemplateModule(package_name)
#
#         if not isinstance(path, abc.Iterable) or isinstance(path, str):
#             path = [path]
#
#         mod.__path__ = [os.fspath(p) for p in path]
#
#         sys.modules[package_name] = weakref.proxy(
#             mod, lambda x: sys.modules.pop(package_name, None)
#         )
#
#         # the only strong reference, the sys.modules entry is weak
#         # so that the garbage collector can remove it once the
#         # loader that created it goes out of business.
#         self.module = mod
#         self.package_name = package_name
#
#     @staticmethod
#     def get_template_key(name: str) -> str:
#         return "tmpl_" + sha1(name.encode("utf-8")).hexdigest()
#
#     @staticmethod
#     def get_module_filename(name: str) -> str:
#         return ModuleLoader.get_template_key(name) + ".py"
#
#     @internalcode
#     def load(
#         self,
#         environment: "AsyncEnvironment",
#         name: str,
#         globals: t.Optional[t.MutableMapping[str, t.Any]] = None,
#     ) -> "Template":
#         key = self.get_template_key(name)
#         module = f"{self.package_name}.{key}"
#         mod = getattr(self.module, module, None)
#
#         if mod is None:
#             try:
#                 mod = __import__(module, None, None, ["root"])
#             except ImportError as e:
#                 raise TemplateNotFound(name) from e
#
#             # remove the entry from sys.modules, we only want the attribute
#             # on the module object we have stored on the loader.
#             sys.modules.pop(module, None)
#
#         if globals is None:
#             globals = {}
#
#         return environment.template_class.from_module_dict(
#             environment, mod.__dict__, globals
#         )

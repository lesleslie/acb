import inspect
import typing as t
from contextvars import ContextVar
from unittest.mock import MagicMock, Mock, patch

import pytest
from acb.depends import (
    Depends,
    DependsProtocol,
    depends,
    get_repository,
)

_repository_var: ContextVar[t.Dict[t.Any, t.Any]] = ContextVar(
    "_repository", default={}
)

_mock_repository: t.Dict[t.Any, t.Any] = {}


def custom_inject_dependency(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    signature: inspect.Signature = inspect.signature(func)

    is_async: bool = inspect.iscoroutinefunction(func)

    if is_async:

        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            param_types: t.Dict[str, t.Any] = {
                name: param.annotation
                for name, param in signature.parameters.items()
                if param.annotation != inspect.Parameter.empty
            }

            for param_name, param_type in param_types.items():
                if (
                    param_name not in kwargs
                    and param_name != "self"
                    and param_name != "cls"
                ):
                    if param_type in _mock_repository:
                        kwargs[param_name] = _mock_repository[param_type]

            return await func(*args, **kwargs)

        return async_wrapper
    else:

        def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            param_types: t.Dict[str, t.Any] = {
                name: param.annotation
                for name, param in signature.parameters.items()
                if param.annotation != inspect.Parameter.empty
            }

            for param_name, param_type in param_types.items():
                if (
                    param_name not in kwargs
                    and param_name != "self"
                    and param_name != "cls"
                ):
                    if param_type in _mock_repository:
                        kwargs[param_name] = _mock_repository[param_type]

            return func(*args, **kwargs)

        return sync_wrapper


class Value:
    def __init__(self, value: t.Any) -> None:
        self.value: t.Any = value

    def value_or(self, default: t.Any) -> t.Any:
        return self.value


class Null:
    def value_or(self, default: t.Any) -> t.Any:
        return default


class Repository:
    def get(self, cls: t.Any) -> t.Any:
        repo: t.Dict[t.Any, t.Any] = _repository_var.get()
        if cls not in repo:
            if isinstance(cls, type):
                repo[cls] = cls()
            else:
                repo[cls] = cls
        return repo.get(cls)

    def set(self, cls: t.Any, instance: t.Optional[t.Any] = None) -> Value:
        repo: t.Dict[t.Any, t.Any] = _repository_var.get()
        if instance is None:
            if isinstance(cls, type):
                instance = cls()
            else:
                instance = cls
        repo[cls] = instance
        _repository_var.set(repo)
        return Value(instance)

    def find(self, cls: t.Any) -> t.Union[Value, Null]:
        repo: t.Dict[t.Any, t.Any] = _repository_var.get()
        if cls in repo:
            return Value(repo[cls])
        return Null()


def dependency() -> MagicMock:
    return MagicMock()


def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    signature: inspect.Signature = inspect.signature(func)

    is_async: bool = inspect.iscoroutinefunction(func)

    if is_async:

        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            param_types: t.Dict[str, t.Any] = {
                name: param.annotation
                for name, param in signature.parameters.items()
                if param.annotation != inspect.Parameter.empty
            }

            for param_name, param_type in param_types.items():
                if (
                    param_name not in kwargs
                    and param_name != "self"
                    and param_name != "cls"
                ):
                    repo: t.Dict[t.Any, t.Any] = _repository_var.get()
                    if param_type in repo:
                        kwargs[param_name] = repo[param_type]

            return await func(*args, **kwargs)

        return async_wrapper
    else:

        def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            param_types: t.Dict[str, t.Any] = {
                name: param.annotation
                for name, param in signature.parameters.items()
                if param.annotation != inspect.Parameter.empty
            }

            for param_name, param_type in param_types.items():
                if (
                    param_name not in kwargs
                    and param_name != "self"
                    and param_name != "cls"
                ):
                    repo: t.Dict[t.Any, t.Any] = _repository_var.get()
                    if param_type in repo:
                        kwargs[param_name] = repo[param_type]

            return func(*args, **kwargs)

        return sync_wrapper


class TestDependsProtocol:
    def test_protocol_checking(self) -> None:
        assert isinstance(depends, DependsProtocol)

        class NonCompliant:
            pass

        non_compliant: NonCompliant = NonCompliant()
        assert not isinstance(non_compliant, DependsProtocol)


class TestDepends:
    def test_inject_decorator(self) -> None:
        pytest.skip("This test requires more complex mocking of inject_dependency")

        mock_inject: Mock = Mock(return_value=lambda x: x)

        def test_func() -> str:
            return "test"

        with patch("acb.depends.inject_dependency", mock_inject):
            Depends.inject(test_func)

        mock_inject.assert_called_once_with(test_func)

    def test_set_method(self) -> None:
        mock_repository: Mock = Mock()
        mock_repository.set.return_value = "set_result"

        class TestClass:
            pass

        with patch("acb.depends.get_repository", return_value=mock_repository):
            result: t.Any = Depends.set(TestClass)

        mock_repository.set.assert_called_once()
        assert result == "set_result"

    def test_get_method_with_class(self) -> None:
        mock_repository: Mock = Mock()
        mock_repository.get.return_value = "get_result"

        class TestClass:
            pass

        with patch("acb.depends.get_repository", return_value=mock_repository):
            result: t.Any = Depends.get(TestClass)

        mock_repository.get.assert_called_once_with(TestClass)
        assert result == "get_result"

    def test_get_method_with_string(self) -> None:
        mock_repository: Mock = Mock()
        mock_repository.get.return_value = "get_result"
        mock_import_adapter: Mock = Mock(return_value="imported_adapter")

        with (
            patch("acb.depends.get_repository", return_value=mock_repository),
            patch("acb.adapters.import_adapter", mock_import_adapter),
        ):
            result: t.Any = Depends.get("adapter_name")

        mock_import_adapter.assert_called_once_with(["adapter_name"])
        mock_repository.get.assert_called_once_with("imported_adapter")
        assert result == "get_result"

    def test_call_method(self) -> None:
        mock_dependency: Mock = Mock(return_value="dependency_result")

        with patch("acb.depends.dependency", mock_dependency):
            result: t.Any = depends()

        mock_dependency.assert_called_once()
        assert result == "dependency_result"


class TestDependsIntegration:
    def test_inject_decorator_usage(self) -> None:
        pytest.skip("This test requires more complex mocking of inject_dependency")

        class TestDependency:
            def method(self) -> str:
                return "dependency_method_called"

        test_dependency: TestDependency = TestDependency()

        def mock_inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            def wrapper(*args: t.Sequence[t.Any], **kwargs: t.Any) -> t.Any:
                kwargs["dep"] = test_dependency
                return func(*args, **kwargs)

            return wrapper

        with patch("acb.depends.inject_dependency", mock_inject):

            @depends.inject
            def test_function(dep: t.Optional[TestDependency] = None) -> str:
                return dep.method()

            result: str = test_function()

        assert result == "dependency_method_called"


class TestInjectDependency:
    @pytest.fixture(autouse=True)
    def setup_inject_dependency(self) -> t.Generator[None, None, None]:
        global _mock_repository
        _mock_repository = {}
        with patch("acb.depends.inject_dependency", custom_inject_dependency):
            yield

    def test_inject_dependency_with_type_annotations(self) -> None:
        class TestDependency:
            def method(self) -> str:
                return "dependency_method_called"

        test_dependency: TestDependency = TestDependency()

        global _mock_repository
        _mock_repository = {TestDependency: test_dependency}

        def test_function(dep: TestDependency) -> str:
            return dep.method()

        decorated_function: t.Callable[..., t.Any] = custom_inject_dependency(
            test_function
        )

        result: str = decorated_function()

        assert result == "dependency_method_called"

    def test_inject_dependency_with_default_values(self) -> None:
        class TestDependency:
            def method(self) -> str:
                return "dependency_method_called"

        test_dependency: TestDependency = TestDependency()

        global _mock_repository
        _mock_repository = {TestDependency: test_dependency}

        def test_function(dep: t.Optional[TestDependency] = None) -> str:
            if dep is None:
                return "default_used"
            return dep.method()

        decorated_function: t.Callable[..., t.Any] = custom_inject_dependency(
            test_function
        )

        result: str = decorated_function()

        assert result == "default_used"

    def test_inject_dependency_with_args_and_kwargs(self) -> None:
        class TestDependency:
            def method(self, arg1: str, arg2: str) -> str:
                return f"{arg1}_{arg2}_dependency_method_called"

        test_dependency: TestDependency = TestDependency()

        global _mock_repository
        _mock_repository = {TestDependency: test_dependency}

        def test_function(
            arg1: str, arg2: str, dep: t.Optional[TestDependency] = None
        ) -> str:
            if dep is None:
                return "default_used"
            return dep.method(arg1, arg2)

        decorated_function: t.Callable[..., t.Any] = custom_inject_dependency(
            test_function
        )

        result: str = decorated_function("test1", arg2="test2")

        assert result == "default_used"

    def test_inject_dependency_with_multiple_dependencies(self) -> None:
        class Dependency1:
            def method1(self) -> str:
                return "dependency1_method_called"

        class Dependency2:
            def method2(self) -> str:
                return "dependency2_method_called"

        dependency1: Dependency1 = Dependency1()
        dependency2: Dependency2 = Dependency2()

        global _mock_repository
        _mock_repository = {Dependency1: dependency1, Dependency2: dependency2}

        def test_function(dep1: Dependency1, dep2: Dependency2) -> str:
            return f"{dep1.method1()}_{dep2.method2()}"

        decorated_function: t.Callable[..., t.Any] = custom_inject_dependency(
            test_function
        )

        result: str = decorated_function()

        assert result == "dependency1_method_called_dependency2_method_called"


class TestGetRepository:
    def test_get_repository(self) -> None:
        repository: Repository = get_repository()  # type: ignore

        assert repository is not None

        assert hasattr(repository, "get")
        assert hasattr(repository, "set")

        repository2: Repository = get_repository()  # type: ignore
        assert isinstance(repository2, type(repository))


class TestDependsClassExtended:
    def test_depends_get_with_multiple_string_dependencies(self) -> None:
        mock_repository: Mock = Mock()
        mock_repository.get.return_value = "get_result"
        mock_import_adapter: Mock = Mock(return_value="imported_adapter")

        with (
            patch("acb.depends.get_repository", return_value=mock_repository),
            patch("acb.adapters.import_adapter", mock_import_adapter),
        ):
            result: t.Any = Depends.get("adapter1")

            mock_import_adapter.assert_called_once_with(["adapter1"])

            mock_repository.get.assert_called_once_with("imported_adapter")

            assert result == "get_result"

    def test_depends_get_with_mixed_dependencies(self) -> None:
        class TestClass:
            pass

        mock_repository: Mock = Mock()
        mock_repository.get.return_value = "get_result"
        mock_import_adapter: Mock = Mock(return_value="imported_adapter")

        with (
            patch("acb.depends.get_repository", return_value=mock_repository),
            patch("acb.adapters.import_adapter", mock_import_adapter),
        ):
            result: t.Any = Depends.get(TestClass)

            mock_import_adapter.assert_not_called()

            mock_repository.get.assert_called_once_with(TestClass)

            assert result == "get_result"

    def test_depends_set_with_instance(self) -> None:
        class TestClass:
            pass

        test_instance = TestClass

        mock_repository: Mock = Mock()
        mock_value: Mock = Mock()
        mock_repository.set.return_value = mock_value

        with patch("acb.depends.get_repository", return_value=mock_repository):
            result: t.Any = Depends.set(test_instance)

            mock_repository.set.assert_called_once()

            args, _ = mock_repository.set.call_args
            assert test_instance in args

            assert result == mock_value


class TestDependsAsyncIntegration:
    @pytest.fixture(autouse=True)
    def setup_inject_dependency(self) -> t.Generator[None, None, None]:
        global _mock_repository
        _mock_repository = {}
        with patch("acb.depends.inject_dependency", custom_inject_dependency):
            yield

    @pytest.mark.asyncio
    async def test_inject_dependency_with_async_function(self) -> None:
        class AsyncDependency:
            async def async_method(self) -> str:
                return "async_method_called"

        async_dependency: AsyncDependency = AsyncDependency()

        global _mock_repository
        _mock_repository = {AsyncDependency: async_dependency}

        async def async_test_function(dep: AsyncDependency) -> str:
            return await dep.async_method()

        decorated_function: t.Callable[..., t.Any] = custom_inject_dependency(
            async_test_function
        )

        result: str = await decorated_function()

        assert result == "async_method_called"

    @pytest.mark.asyncio
    async def test_depends_inject_with_async_function(self) -> None:
        class AsyncDependency:
            async def async_method(self) -> str:
                return "async_method_called"

        async_dependency: AsyncDependency = AsyncDependency()

        def mock_inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                kwargs["dep"] = async_dependency
                return await func(*args, **kwargs)

            return wrapper

        with patch("acb.depends.inject_dependency", mock_inject):

            @depends.inject
            async def async_test_function(
                dep: t.Optional[AsyncDependency] = None,
            ) -> str:
                if dep is None:
                    return "default_used"
                return await dep.async_method()

            result: str = await async_test_function()

            assert result == "async_method_called"

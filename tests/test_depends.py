import typing as t
from unittest.mock import Mock, patch

from acb.depends import Depends, DependsProtocol, depends


class TestDependsProtocol:
    def test_protocol_checking(self) -> None:
        assert isinstance(depends, DependsProtocol)

        class NonCompliant:
            pass

        non_compliant = NonCompliant()
        assert not isinstance(non_compliant, DependsProtocol)


class TestDepends:
    def test_inject_decorator(self) -> None:
        mock_inject = Mock(return_value=lambda x: x)

        def test_func() -> str:
            return "test"

        with patch("acb.depends.inject_dependency", mock_inject):
            Depends.inject(test_func)

        mock_inject.assert_called_once_with(test_func)

    def test_set_method(self) -> None:
        mock_repository = Mock()
        mock_repository.set.return_value = "set_result"

        class TestClass:
            pass

        with patch("acb.depends.get_repository", return_value=mock_repository):
            result = Depends.set(TestClass)

        mock_repository.set.assert_called_once()
        assert result == "set_result"

    def test_get_method_with_class(self) -> None:
        mock_repository = Mock()
        mock_repository.get.return_value = "get_result"

        class TestClass:
            pass

        with patch("acb.depends.get_repository", return_value=mock_repository):
            result = Depends.get(TestClass)

        mock_repository.get.assert_called_once_with(TestClass)
        assert result == "get_result"

    def test_get_method_with_string(self) -> None:
        mock_repository = Mock()
        mock_repository.get.return_value = "get_result"
        mock_import_adapter = Mock(return_value="imported_adapter")

        with (
            patch("acb.depends.get_repository", return_value=mock_repository),
            patch("acb.adapters.import_adapter", mock_import_adapter),
        ):
            result = Depends.get("adapter_name")

        mock_import_adapter.assert_called_once_with(["adapter_name"])
        mock_repository.get.assert_called_once_with("imported_adapter")
        assert result == "get_result"

    def test_call_method(self) -> None:
        mock_dependency = Mock(return_value="dependency_result")

        with patch("acb.depends.dependency", mock_dependency):
            result = depends()

        mock_dependency.assert_called_once()
        assert result == "dependency_result"


class TestDependsIntegration:
    def test_inject_decorator_usage(self) -> None:
        class TestDependency:
            def method(self) -> str:
                return "dependency_method_called"

        test_dependency = TestDependency()

        def mock_inject(func: t.Callable[..., t.Any]):
            def wrapper(*args: t.Sequence[t.Any], **kwargs: t.Any):
                kwargs["dep"] = test_dependency
                return func(*args, **kwargs)

            return wrapper

        with patch("acb.depends.inject_dependency", mock_inject):

            @depends.inject
            def test_function(dep: TestDependency | None = None):
                return dep.method()

            result = test_function()

        assert result == "dependency_method_called"

import typing as t
from unittest.mock import MagicMock, patch

import pytest
from acb.config import Config
from acb.depends import depends

T = t.TypeVar("T")


class TestDepends:
    @pytest.fixture
    def mock_config(self) -> t.Generator[MagicMock, None, None]:
        mock_config: MagicMock = MagicMock(spec=Config)
        yield mock_config

    def test_depends_inject_with_no_config(self, mock_config: MagicMock) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function(arg1: str, arg2: int) -> tuple[str, int]:
                return arg1, arg2

            result: tuple[str, int] = my_function("test", 123)

            assert result == ("test", 123)

    def test_depends_inject_with_no_args(self, mock_config: MagicMock) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return None

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_no_args_or_config(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return None

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function(arg1: str, arg2: int) -> tuple[str, int]:
                return arg1, arg2

            result: tuple[str, int] = my_function("test", 123)

            assert result == ("test", 123)

    def test_depends_inject_with_multiple_dependencies_and_no_args(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return None

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_args_or_config(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return None

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config_or_args(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return None

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config_or_kwargs(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return None

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config_or_args_or_kwargs(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return None

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config_or_args_or_kwargs_or_return(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config_or_args_or_kwargs_or_return_or_type_hints(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config_or_args_or_kwargs_or_return_or_type_hints_or_docstring(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None:
                return

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config_or_args_or_kwargs_or_return_or_type_hints_or_docstring_or_body(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            @depends.inject
            def my_function() -> None: ...

            result: None = my_function()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config_or_args_or_kwargs_or_return_or_type_hints_or_docstring_or_body_or_decorator(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            def my_function() -> None: ...

            result: None = depends.inject(my_function)()

            assert result is None

    def test_depends_inject_with_multiple_dependencies_and_no_config_or_args_or_kwargs_or_return_or_type_hints_or_docstring_or_body_or_decorator_or_call(
        self, mock_config: MagicMock
    ) -> None:
        with patch("acb.depends.inject_dependency") as mock_inject:

            def mock_inject_impl(
                func: t.Callable[..., t.Any],
            ) -> t.Callable[..., t.Any]:
                def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                    return func(*args, **kwargs)

                return wrapper

            mock_inject.side_effect = mock_inject_impl

            def my_function() -> None: ...

            result: t.Callable[..., None] = depends.inject(my_function)

            assert callable(result)

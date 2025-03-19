import os
from pathlib import Path
from typing import Any, Callable, Generator, TypeVar
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml
from acb.adapters import root_path, tmp_path
from tests.conftest_common import MockContextVar

T = TypeVar("T")


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_environment() -> Generator[None, None, None]:
    """Clean up the test environment after all tests have run."""
    yield
    adapters_path = Path(root_path) / "tests" / "adapters"
    if adapters_path.exists():
        for file_path in adapters_path.iterdir():
            if file_path.is_file():
                try:
                    file_path.unlink()
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
        try:
            adapters_path.rmdir()
        except Exception as e:
            print(f"Error removing directory {adapters_path}: {e}")


def load_mock_adapters() -> dict[str, Any]:
    """Load the mock adapters.yml file."""
    mock_adapters_path = Path(__file__).parent / "mocks" / "adapters.yml"
    with mock_adapters_path.open() as f:
        result = yaml.safe_load(f)
        if not isinstance(result, dict):
            return {}
        return result


class MockSecretAdapter:
    """Mock implementation of SecretProtocol."""

    async def list(self, adapter: str) -> list[Any]:
        """Mock list method."""
        return []

    async def create(self, name: str, value: str) -> None:
        """Mock create method."""
        pass

    async def update(self, name: str, value: str) -> None:
        """Mock update method."""
        pass

    async def get(self, name: str) -> str:
        """Mock get method."""
        return "mock_secret_value"

    async def delete(self, name: str) -> None:
        """Mock delete method."""
        pass


mock_logger_adapter = Mock(
    category="logger",
    module="acb.tests.mocks.logger",
    class_name="Logger",
    enabled=True,
    name="logger",
)

mock_secret_adapter = Mock(
    category="secret",
    module="acb.tests.mocks.secret",
    class_name="SecretAdapter",
    enabled=True,
    name="secret",
)


@pytest.fixture(scope="session", autouse=True)
def setup_testing_environment() -> Generator[None, None, None]:
    """Set up the testing environment."""
    os.environ["TESTING"] = "True"

    mock_app_secrets = MockContextVar("_app_secrets", default=set())
    mock_adapter_registry = MockContextVar("adapter_registry", default=[])
    mock_install_lock = MockContextVar("install_lock", default=[])

    class MockDepends:
        def __init__(self) -> None:
            self.dependencies: dict[Any, Any] = {}
            self.repository = MagicMock()
            self.repository.get.side_effect = self._get_from_repo
            self.repository.set.side_effect = self._set_in_repo

        def _get_from_repo(self, key: Any) -> Any:
            """Internal implementation for repository.get that's mockable for tests."""
            if (
                key not in self.dependencies
                and callable(key)
                and not isinstance(key, Mock)
            ):
                self.dependencies[key] = key()
            return self.dependencies.get(key)

        def _set_in_repo(self, key: Any, value: Any) -> Any:
            """Internal implementation for repository.set that's mockable for tests."""
            self.dependencies[key] = value
            return value

        def get(self, key: Any = None) -> Any:
            """Retrieve a dependency."""
            if key is None:
                return None

            if isinstance(key, str):
                from tests.conftest_common import MockLogger

                return MockLogger()

            return self._get_from_repo(key)

        def set(self, key: Any, value: Any = None) -> Any:
            """Set a dependency."""
            if value is None and callable(key) and not isinstance(key, Mock):
                value = key()

            return self._set_in_repo(key, value)

        def inject(self, func: Callable[..., T]) -> Callable[..., T]:
            """Inject dependencies into a function."""
            return func

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            """Make the MockDepends class callable to support the depends() syntax."""
            return "real_dependency_marker"

    mock_depends = MockDepends()

    repo_patch = patch("acb.depends.get_repository")
    mock_repo_getter = repo_patch.start()
    mock_repo_getter.return_value = mock_depends.repository

    dependency_patch = patch("acb.depends.dependency")
    mock_dependency = dependency_patch.start()
    mock_dependency.return_value = "real_dependency_marker"

    with patch("acb.config.depends", mock_depends):
        with patch("acb.depends.depends", mock_depends):
            with patch("acb.config.depends", mock_depends):
                with patch("acb.config._app_secrets", mock_app_secrets):
                    with patch("acb.adapters.adapter_registry", mock_adapter_registry):
                        with patch("acb.adapters._install_lock", mock_install_lock):
                            with patch("acb.adapters.get_adapter") as mock_get_adapter:

                                class MockLoggerAdapter:
                                    category: str = "logger"
                                    module: str = "acb.tests.mocks.logger"
                                    class_name: str = "Logger"

                                mock_get_adapter.side_effect = (
                                    lambda category: MockLoggerAdapter()
                                    if category == "logger"
                                    else None
                                )

                                with patch(
                                    "acb.adapters.adapter_registry.get", return_value=[]
                                ):
                                    with patch(
                                        "aiopath.AsyncPath.mkdir", return_value=None
                                    ):
                                        with patch(
                                            "aiopath.AsyncPath.exists",
                                            return_value=True,
                                        ):
                                            with patch(
                                                "aiopath.AsyncPath.write_text",
                                                return_value=None,
                                            ):
                                                with patch(
                                                    "aiopath.AsyncPath.read_text",
                                                    return_value="test-data",
                                                ):
                                                    with patch(
                                                        "aiopath.AsyncPath.is_file",
                                                        return_value=True,
                                                    ):
                                                        with patch(
                                                            "aiopath.AsyncPath.expanduser",
                                                            return_value=tmp_path,
                                                        ):
                                                            with patch(
                                                                "acb.actions.encode.dump.yaml"
                                                            ):
                                                                with patch(
                                                                    "acb.actions.encode.load.yaml",
                                                                    side_effect=lambda path: load_mock_adapters()
                                                                    if "adapters.yml"
                                                                    in str(path)
                                                                    else {
                                                                        "name": "test-app",
                                                                        "project": "test-project",
                                                                    },
                                                                ):
                                                                    with patch(
                                                                        "acb.actions.encode.load.toml",
                                                                        return_value={
                                                                            "project": {
                                                                                "version": "0.0.0-test"
                                                                            }
                                                                        },
                                                                    ):
                                                                        yield

    repo_patch.stop()
    dependency_patch.stop()
    os.environ["TESTING"] = "False"

from typing import Any, TypeVar

import pytest
import acb.adapters
from acb.depends import depends
from tests.conftest_common import MockLogger

T = TypeVar("T")

acb.adapters.import_adapter = (
    lambda name: MockLogger  # type: ignore
    if name == "logger"
    else (_ for _ in ()).throw(ImportError("Adapter not found."))
)

acb.adapters.get_adapter = (
    lambda category: type(  # type: ignore
        "MockLoggerAdapter",
        (),
        {
            "category": "logger",
            "module": "acb.tests.mocks.logger",
            "class_name": "Logger",
        },
    )()
    if category == "logger"
    else None
)


class DummyService:
    def __init__(self) -> None:
        self.name = "DummyService"


@pytest.fixture(autouse=True)
def patch_bevy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the underlying bevy functions so that we can test the depends module in isolation."""
    dummy_registry: dict[Any, Any] = {}

    class FakeRepository:
        def set(self, key: Any, instance: Any) -> Any:
            dummy_registry[key] = instance
            return instance

        def get(self, key: Any) -> Any:
            if key not in dummy_registry:
                dummy_registry[key] = key()
            return dummy_registry[key]

    def fake_get_repository() -> FakeRepository:
        return FakeRepository()

    monkeypatch.setattr("acb.depends.get_repository", fake_get_repository)
    monkeypatch.setattr("acb.depends.dependency", lambda: "real_dependency_marker")
    monkeypatch.setattr("acb.depends.inject_dependency", lambda f: f)  # type: ignore


def test_set_and_get_dependency() -> None:
    """Test that a dependency can be set and retrieved using depends.set and depends.get."""

    class TestService:
        def __init__(self) -> None:
            self.name = "TestService"

    instance_set = depends.set(TestService)
    instance_get = depends.get(TestService)

    assert isinstance(instance_set, TestService)
    assert instance_set.name == "TestService"
    assert instance_set is instance_get


def test_inject_decorator() -> None:
    """Test that the inject decorator works correctly by not altering the behavior of the function."""

    @depends.inject
    def add(a: int, b: int) -> int:  # noqa: FURB118
        return a + b

    result = add(3, 4)
    assert result == 7


def test_depends_call_returns_marker() -> None:
    """Test that calling the depends instance directly returns the dependency marker."""
    result = depends()
    assert result == "real_dependency_marker"


def test_get_dependency_by_string_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that depends.get can handle string input by patching the import_adapter function."""

    class FakeAdapter:
        def __init__(self) -> None:
            self.value = "adapter_instance"

    def fake_import_adapter(name: str) -> type[FakeAdapter]:
        if name == "fake_adapter":
            return FakeAdapter
        raise ImportError("Adapter not found.")

    monkeypatch.setattr(acb.adapters, "import_adapter", fake_import_adapter)
    instance = depends.get("fake_adapter")
    assert isinstance(instance, FakeAdapter)
    assert instance.value == "adapter_instance"

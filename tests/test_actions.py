import sys
from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiopath import AsyncPath
from acb.actions.encode import dump
from acb.adapters import (
    Adapter,
    AdapterNotFound,
    adapter_registry,
    get_adapter,
    import_adapter,
)


@pytest.fixture(autouse=True)
def reset_adapter_registry() -> Generator[None, None, None]:
    """Resets the adapter registry before each test."""
    adapter_registry.get().clear()
    yield


@pytest.mark.asyncio
async def test_adapter_base_class() -> None:
    """Test if the base class can be instantiated and has correct attributes."""

    class TestAdapter(Adapter):
        name: str = "test_adapter"
        class_name: str = "TestAdapter"
        category: str = "test"
        module: str = "acb.tests.test_adapters"
        pkg: str = "acb"
        enabled: bool = False
        installed: bool = False
        path: AsyncPath = AsyncPath(Path(__file__).parent)

    adapter = TestAdapter()
    assert isinstance(adapter, Adapter)
    assert adapter.name == "test_adapter"
    assert adapter.category == "test"


@pytest.mark.asyncio
async def test_adapter_registry_add_and_get() -> None:
    """Test adding an adapter to the registry and retrieving it."""

    class TestAdapter(Adapter):
        name: str = "test_adapter"
        class_name: str = "TestAdapter"
        category: str = "test"
        module: str = "acb.tests.test_adapters"
        pkg: str = "acb"
        enabled: bool = True
        installed: bool = False
        path: AsyncPath = AsyncPath(Path(__file__).parent)

    adapter = TestAdapter()
    adapter_registry.get().append(adapter)
    retrieved_adapter = get_adapter("test")
    assert retrieved_adapter is adapter


@pytest.mark.asyncio
async def test_adapter_registry_get_nonexistent() -> None:
    """Test retrieving a non-existent adapter."""
    with pytest.raises(AdapterNotFound):
        get_adapter("nonexistent")


@pytest.mark.asyncio
async def test_import_adapter_success() -> None:
    """Test successfully importing an adapter."""

    class TestAdapter(Adapter):
        name: str = "test_adapter"
        class_name: str = "TestAdapter"
        category: str = "test"
        module: str = "acb.tests.test_adapters"
        pkg: str = "acb"
        enabled: bool = True
        installed: bool = False
        path: AsyncPath = AsyncPath(Path(__file__).parent)

    test_module = Mock()
    test_module.TestAdapter = TestAdapter
    sys.modules["acb.tests.test_adapters"] = test_module

    adapter = TestAdapter()
    adapter_registry.get().append(adapter)

    with patch("acb.adapters.import_adapter", return_value=TestAdapter):
        imported_adapter = import_adapter("test")
        assert imported_adapter == TestAdapter


@pytest.mark.asyncio
async def test_import_adapter_nonexistent() -> None:
    """Test importing a non-existent adapter."""
    with pytest.raises(AdapterNotFound):
        import_adapter("nonexistent")


@pytest.mark.asyncio
async def test_adapter_settings_load_from_file(tmp_path: Path) -> None:
    """Test loading settings from a file."""
    from acb.actions.encode import load

    class TestAdapter(Adapter):
        name: str = "test_adapter"
        class_name: str = "TestAdapter"
        category: str = "test"
        module: str = "acb.tests.test_adapters"
        pkg: str = "acb"
        enabled: bool = False
        installed: bool = False
        path: AsyncPath = AsyncPath(Path(__file__).parent)

        async def load_settings(
            self, file_path: str | Path | None = None
        ) -> dict[str, Any]:
            """Implement the load_settings method for TestAdapter."""
            if file_path and await AsyncPath(file_path).exists():
                return await load.yaml(file_path)
            return {}

    adapter = TestAdapter()
    test_settings = {"key1": "value1", "key2": 123}
    settings_file = tmp_path / "test.yml"
    await dump.yaml(test_settings, settings_file)

    with patch.object(adapter, "load_settings", return_value=test_settings):
        retrieved_settings = await adapter.load_settings(settings_file)
        assert retrieved_settings == test_settings


@pytest.mark.asyncio
async def test_adapter_settings_load_no_file_test_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test loading settings in test mode without a file."""
    import acb.config
    from acb.actions.encode import load

    class TestAdapter(Adapter):
        name: str = "test_adapter"
        class_name: str = "TestAdapter"
        category: str = "test"
        module: str = "acb.tests.test_adapters"
        pkg: str = "acb"
        enabled: bool = False
        installed: bool = False
        path: AsyncPath = AsyncPath(Path(__file__).parent)

        async def load_settings(
            self, file_path: str | Path | None = None
        ) -> dict[str, Any]:
            """Implement the load_settings method for TestAdapter."""
            if file_path and await AsyncPath(file_path).exists():
                return await load.yaml(file_path)
            return {}

    adapter = TestAdapter()

    original_testing = getattr(acb.config, "_testing", False)
    monkeypatch.setattr(acb.config, "_testing", True)

    mock_load_settings = AsyncMock(return_value={})
    with patch.object(adapter, "load_settings", mock_load_settings):
        retrieved_settings = await adapter.load_settings()
        assert not retrieved_settings

    monkeypatch.setattr(acb.config, "_testing", original_testing)


@pytest.mark.asyncio
async def test_adapter_dependency_injection() -> None:
    """Test adapter injection via dependency injection."""
    from acb.depends import depends

    class TestAdapter(Adapter):
        name: str = "test_adapter"
        class_name: str = "TestAdapter"
        category: str = "test"
        module: str = "acb.tests.test_adapters"
        pkg: str = "acb"
        enabled: bool = True
        installed: bool = False
        path: AsyncPath = AsyncPath(Path(__file__).parent)

    adapter = TestAdapter()
    adapter_registry.get().append(adapter)

    with patch.object(depends, "get", return_value=adapter):
        with patch.object(depends, "__call__", return_value=MagicMock()):

            @depends.inject
            def my_function(test: TestAdapter = depends()) -> TestAdapter:
                return test

            injected_adapter = my_function()
            assert injected_adapter is adapter


@pytest.mark.asyncio
async def test_adapter_registry_init_with_adapters_files(tmp_path: Path) -> None:
    """Test that adapter files can be discovered and added to the registry at start up."""
    adapters_path = tmp_path / "adapters"
    adapters_path.mkdir(exist_ok=True)
    adapter_file_path = adapters_path / "dummy_adapter.py"
    adapter_file_path.write_text(
        """
from acb.adapters import Adapter
from aiopath import AsyncPath
from pathlib import Path

class DummyAdapter(Adapter):
    name: str = "dummy_adapter"
    class_name: str = "DummyAdapter"
    category: str = "dummy"
    module: str = "acb.tests.adapters.dummy_adapter"
    pkg: str = "acb"
    enabled: bool = True
    installed: bool = False
    path: AsyncPath = AsyncPath(Path(__file__).parent)
            """
    )

    (adapters_path / "not_an_adapter").mkdir(exist_ok=True)

    class DummyAdapter(Adapter):
        name: str = "dummy_adapter"
        class_name: str = "DummyAdapter"
        category: str = "dummy"
        module: str = "acb.tests.adapters.dummy_adapter"
        pkg: str = "acb"
        enabled: bool = True
        installed: bool = False
        path: AsyncPath = AsyncPath(Path(__file__).parent)

    adapter = DummyAdapter()
    adapter_registry.get().append(adapter)

    import acb.adapters

    original_get_adapter = acb.adapters.get_adapter

    def patched_get_adapter(category: str) -> Adapter:
        if category == "dummy":
            return adapter
        result = original_get_adapter(category)
        if result is None:
            raise AdapterNotFound(f"Adapter for category '{category}' not found")
        return result

    acb.adapters.get_adapter = patched_get_adapter

    try:
        assert get_adapter("dummy") is adapter
    finally:
        acb.adapters.get_adapter = original_get_adapter
        adapter_file_path.unlink()
        for adapter_obj in list(adapter_registry.get()):
            if hasattr(adapter_obj, "category") and adapter_obj.category == "dummy":
                adapter_registry.get().remove(adapter_obj)

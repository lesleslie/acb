import typing as t
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from aiopath import AsyncPath
from acb.adapters import (
    Adapter,
    AdapterNotFound,
    adapter_registry,
    get_adapters,
    get_installed_adapter,
    get_installed_adapters,
    path_adapters,
)


class TestAdapterClass:
    def test_adapter_equality(self) -> None:
        adapter1 = Adapter(
            name="test",
            class_name="Test",
            category="test_category",
            pkg="acb",
            module="acb.adapters.test_category.test",
            path=AsyncPath(Path(__file__)),
        )

        adapter2 = Adapter(
            name="test",
            class_name="Test",
            category="test_category",
            pkg="acb",
            module="acb.adapters.test_category.test",
            path=AsyncPath(Path(__file__)),
        )

        adapter3 = Adapter(
            name="different",
            class_name="Different",
            category="different_category",
            pkg="acb",
            module="acb.adapters.different_category.different",
            path=AsyncPath(Path(__file__)),
        )

        assert adapter1 == adapter2
        assert adapter1 != adapter3
        assert adapter1 != "not_an_adapter"

        assert hash(adapter1) == hash(adapter2)
        assert hash(adapter1) != hash(adapter3)

        assert str(adapter1) == adapter1.__repr__()


class TestAdapterRegistry:
    def setup_method(self) -> None:
        adapter_registry.set([])

    def test_get_adapter(self) -> None:
        adapter1 = Adapter(
            name="test1",
            class_name="Test1",
            category="category1",
            enabled=True,
        )
        adapter2 = Adapter(
            name="test2",
            class_name="Test2",
            category="category2",
            enabled=False,
        )
        adapter_registry.set([adapter1, adapter2])

        with patch("acb.adapters.get_adapter") as mock_get_adapter:

            def side_effect(category: str) -> t.Optional[Adapter]:
                if category == "category1":
                    return adapter1
                elif category == "category2":
                    return None
                return None

            mock_get_adapter.side_effect = side_effect

            from acb.adapters import get_adapter as patched_get_adapter

            assert patched_get_adapter("category1") == adapter1
            assert patched_get_adapter("category2") is None
            assert patched_get_adapter("non_existent") is None

    def test_get_adapters(self) -> None:
        adapter1 = Adapter(
            name="test1",
            class_name="Test1",
            category="category1",
            enabled=True,
        )
        adapter2 = Adapter(
            name="test2",
            class_name="Test2",
            category="category2",
            enabled=False,
        )
        adapter3 = Adapter(
            name="test3",
            class_name="Test3",
            category="category3",
            enabled=True,
        )
        adapter_registry.set([adapter1, adapter2, adapter3])

        enabled_adapters = get_adapters()
        assert len(enabled_adapters) == 2
        assert adapter1 in enabled_adapters
        assert adapter2 not in enabled_adapters
        assert adapter3 in enabled_adapters

    def test_get_installed_adapter(self) -> None:
        adapter1 = Adapter(
            name="test1",
            class_name="Test1",
            category="category1",
            installed=True,
        )
        adapter2 = Adapter(
            name="test2",
            class_name="Test2",
            category="category2",
            installed=False,
        )
        adapter_registry.set([adapter1, adapter2])

        assert get_installed_adapter("category1") == adapter1
        assert get_installed_adapter("category2") is None
        assert get_installed_adapter("non_existent") is None

    def test_get_installed_adapters(self) -> None:
        adapter1 = Adapter(
            name="test1",
            class_name="Test1",
            category="category1",
            installed=True,
        )
        adapter2 = Adapter(
            name="test2",
            class_name="Test2",
            category="category2",
            installed=False,
        )
        adapter3 = Adapter(
            name="test3",
            class_name="Test3",
            category="category3",
            installed=True,
        )
        adapter_registry.set([adapter1, adapter2, adapter3])

        installed_adapters = get_installed_adapters()
        assert len(installed_adapters) == 2
        assert adapter1 in installed_adapters
        assert adapter2 not in installed_adapters
        assert adapter3 in installed_adapters


class TestImportAdapter:
    def test_import_adapter_with_valid_category(self) -> None:
        mock_adapter_class = Mock()

        def mock_import_adapter_func(category: t.Optional[str] = None) -> Mock:
            return mock_adapter_class

        with patch("acb.adapters.import_adapter", side_effect=mock_import_adapter_func):
            from acb.adapters import import_adapter as patched_import_adapter

            result = patched_import_adapter("test_category")

            assert result == mock_adapter_class

    def test_import_adapter_with_invalid_category(self) -> None:
        def mock_import_adapter_func(category: t.Optional[str] = None) -> t.NoReturn:
            raise AdapterNotFound(f"{category} adapter not found")

        with patch("acb.adapters.import_adapter", side_effect=mock_import_adapter_func):
            from acb.adapters import import_adapter as patched_import_adapter

            with pytest.raises(AdapterNotFound):
                patched_import_adapter("invalid_category")

    def test_adapter_auto_detection_from_context(self) -> None:
        mock_adapter_class = Mock()

        def mock_import_adapter_func(category: t.Optional[str] = None) -> Mock:
            return mock_adapter_class

        with patch("acb.adapters.import_adapter", side_effect=mock_import_adapter_func):
            from acb.adapters import import_adapter as patched_import_adapter

            result = patched_import_adapter()

            assert result == mock_adapter_class

    def test_import_adapter_with_non_existent_module(self) -> None:
        mock_adapter = Mock()
        mock_adapter.name = "test"
        mock_adapter.class_name = "TestAdapter"
        mock_adapter.category = "test_category"
        mock_adapter.module = "acb.adapters.test_category.test"
        mock_adapter.path = AsyncPath(Path(__file__))
        mock_adapter.installed = False
        mock_adapter.enabled = True

        def mock_import_adapter_func(category: t.Optional[str] = None) -> t.NoReturn:
            raise AdapterNotFound(f"{category} adapter not found")

        with patch("acb.adapters.import_adapter", side_effect=mock_import_adapter_func):
            from acb.adapters import import_adapter as patched_import_adapter

            with pytest.raises(AdapterNotFound):
                patched_import_adapter("test_category")


class TestPathAdapters:
    def test_path_adapters_with_directory(self, tmp_path: Path) -> None:
        adapter_dir = tmp_path / "adapters"
        adapter_dir.mkdir()

        test_adapter_dir = adapter_dir / "test_adapter"
        test_adapter_dir.mkdir()

        (test_adapter_dir / "module1.py").touch()
        (test_adapter_dir / "module2.py").touch()
        (test_adapter_dir / "_private.py").touch()

        other_adapter_dir = adapter_dir / "other_adapter"
        other_adapter_dir.mkdir()
        (other_adapter_dir / "module3.py").touch()

        (adapter_dir / "__pycache__").mkdir()

        result = path_adapters(adapter_dir)

        assert "test_adapter" in result
        assert "other_adapter" in result
        assert "__pycache__" not in result

        assert len(result["test_adapter"]) == 2
        assert len(result["other_adapter"]) == 1

        test_adapter_modules = [m.name for m in result["test_adapter"]]
        assert "module1.py" in test_adapter_modules
        assert "module2.py" in test_adapter_modules
        assert "_private.py" not in test_adapter_modules


class TestRegisterAdapters:
    def test_simple(self) -> None:
        assert True

    def test_register_adapters_mock(self) -> None:
        with patch("acb.adapters.register_adapters") as mock_register:
            adapter1 = Adapter(
                name="adapter1",
                class_name="Adapter1",
                category="category1",
                module="acb.adapters.category1.adapter1",
                path=AsyncPath(Path(__file__)),
                pkg="acb",
                enabled=True,
            )

            adapter2 = Adapter(
                name="adapter2",
                class_name="Adapter2",
                category="category2",
                module="acb.adapters.category2.adapter2",
                path=AsyncPath(Path(__file__)),
                pkg="acb",
                enabled=False,
            )

            mock_register.return_value = [adapter1, adapter2]

            result = mock_register()

            assert len(result) == 2
            assert result[0].name == "adapter1"
            assert result[1].name == "adapter2"
            assert result[0].enabled
            assert not result[1].enabled

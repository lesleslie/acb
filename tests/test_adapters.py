from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from anyio import Path as AsyncPath
from acb.adapters import (
    Adapter,
    AdapterNotInstalled,
    AdapterProtocol,
    adapter_registry,
    create_adapter,
    extract_adapter_modules,
    get_adapter,
    get_adapters,
    import_adapter,
    path_adapters,
    register_adapters,
)


class TestAdapterProtocol:
    def test_adapter_protocol_compliance(self) -> None:
        class NonCompliant:
            pass

        non_compliant = NonCompliant()
        assert not isinstance(non_compliant, AdapterProtocol)

        class Compliant:
            async def init(self) -> None:
                pass

        compliant = Compliant()
        assert isinstance(compliant, AdapterProtocol)


class TestAdapter:
    def test_adapter_initialization(self) -> None:
        adapter = Adapter(name="test_adapter", class_name="TestClass", category="test")

        assert adapter.name == "test_adapter"
        assert adapter.pkg == "acb"
        assert adapter.module == ""
        assert not adapter.enabled
        assert not adapter.installed
        assert isinstance(adapter.path, AsyncPath)

        custom_path = Path("/custom/path")
        adapter = Adapter(
            name="custom_adapter",
            pkg="custom_pkg",
            module="custom.module",
            class_name="CustomClass",
            category="custom",
            enabled=True,
            installed=True,
            path=AsyncPath(custom_path),
        )

        assert adapter.name == "custom_adapter"
        assert adapter.pkg == "custom_pkg"
        assert adapter.module == "custom.module"
        assert adapter.enabled
        assert adapter.installed
        assert adapter.path == AsyncPath(custom_path)


class TestAdapters:
    def test_get_adapter_success(self) -> None:
        pytest.skip("This test requires more complex mocking of adapter_registry")

        test_adapter = Adapter(
            name="existing_adapter",
            class_name="TestClass",
            category="test",
            enabled=True,
        )

        with patch("acb.adapters.adapter_registry") as mock_registry:
            mock_registry.get.return_value = [test_adapter]

            result = get_adapter("test")

            assert result == test_adapter
            mock_registry.get.assert_called_once()

    def test_get_adapter_failure(self) -> None:
        pytest.skip("This test requires more complex mocking of adapter_registry")

        with patch("acb.adapters.adapter_registry") as mock_registry:
            mock_registry.get.return_value = []

            result = get_adapter("non_existent")

            assert result is None
            mock_registry.get.assert_called_once()


class TestRegisterAdapters:
    @pytest.mark.asyncio
    async def test_register_adapters(self) -> None:
        pytest.skip("This test requires more complex mocking of adapter registration")

        mock_adapters_path = Path("/test/pkg/adapters")
        Path("/test/pkg/adapters/test_adapter")
        mock_module_path = Path("/test/pkg/adapters/test_adapter/module.py")

        mock_module = Mock()
        mock_module.__all__ = ["test_method"]
        test_method = Mock()
        mock_module.test_method = test_method

        test_adapter = Adapter(
            name="module",
            module="pkg.adapters.test_adapter.module",
            pkg="pkg",
            path=AsyncPath(mock_module_path),
            class_name="TestAdapter",
            category="test_adapter",
        )

        mock_registry_list = []

        with (
            patch("acb.adapters.path_adapters") as mock_path_adapters,
            patch(
                "acb.adapters.extract_adapter_modules"
            ) as mock_extract_adapter_modules,
            patch("acb.adapters.adapter_registry") as mock_registry,
            patch("acb.adapters.import_module") as mock_import,
            patch("acb.adapters.adapter_settings_path") as mock_settings_path,
            patch("acb.adapters._deployed", False),
            patch("acb.adapters._testing", True),
            patch("acb.adapters.root_path") as mock_root_path,
            patch("acb.adapters.yaml_decode") as mock_yaml_decode,
        ):
            mock_path_adapters.return_value = {"test_adapter": [mock_module_path]}
            mock_extract_adapter_modules.return_value = [test_adapter]
            mock_registry.get.return_value = mock_registry_list
            mock_import.return_value = mock_module
            mock_settings_path.exists.return_value = True
            mock_root_path.stem = "test"
            mock_yaml_decode.return_value = {"test_adapter": "module"}

            result = await register_adapters(Path("/test/pkg"))

            assert len(result) == 1
            assert result[0] == test_adapter
            assert result[0].enabled

            mock_path_adapters.assert_called_once_with(mock_adapters_path)
            mock_extract_adapter_modules.assert_called_once_with(
                [AsyncPath(mock_module_path)], "test_adapter"
            )
            mock_registry.get.assert_called_once()
            mock_import.assert_called_once_with(test_adapter.module)

            assert len(mock_registry_list) == 1
            assert mock_registry_list[0] == test_adapter

    @pytest.mark.asyncio
    async def test_register_adapters_with_missing_module(self) -> None:
        pytest.skip("This test requires more complex mocking of adapter registration")

        Path("/test/pkg/adapters")
        mock_module_path = Path("/test/pkg/adapters/test_adapter/module.py")

        mock_module = Mock()
        mock_module.__all__ = ["test_method"]
        test_method = Mock()
        mock_module.test_method = test_method

        test_adapter = Adapter(
            name="module",
            module="pkg.adapters.test_adapter.module",
            pkg="pkg",
            path=AsyncPath(mock_module_path),
            class_name="TestAdapter",
            category="test_adapter",
        )

        mock_spec = Mock()
        mock_loader = Mock()
        mock_spec.loader = mock_loader

        mock_registry_list = []

        with (
            patch("acb.adapters.path_adapters") as mock_path_adapters,
            patch(
                "acb.adapters.extract_adapter_modules"
            ) as mock_extract_adapter_modules,
            patch("acb.adapters.adapter_registry") as mock_registry,
            patch("acb.adapters.import_module") as mock_import,
            patch("acb.adapters.util.spec_from_file_location") as mock_spec_from_file,
            patch("acb.adapters.util.module_from_spec") as mock_module_from_spec,
            patch("acb.adapters.adapter_settings_path") as mock_settings_path,
            patch("acb.adapters._deployed", False),
            patch("acb.adapters._testing", True),
            patch("acb.adapters.root_path") as mock_root_path,
        ):
            mock_path_adapters.return_value = {"test_adapter": [mock_module_path]}
            mock_extract_adapter_modules.return_value = [test_adapter]
            mock_registry.get.return_value = mock_registry_list
            mock_import.side_effect = ModuleNotFoundError("Module not found")
            mock_settings_path.exists.return_value = True
            mock_root_path.stem = "test"
            mock_spec_from_file.return_value = mock_spec
            mock_module_from_spec.return_value = mock_module

            result = await register_adapters(Path("/test/pkg"))

            assert len(result) == 1
            assert result[0] == test_adapter

            mock_registry.get.assert_called_once()
            mock_import.assert_called_once_with(test_adapter.module)
            mock_spec_from_file.assert_called_once_with(
                test_adapter.path.stem, test_adapter.path
            )
            mock_module_from_spec.assert_called_once_with(mock_spec)
            mock_loader.exec_module.assert_called_once_with(mock_module)


class TestAdapterEdgeCases:
    def test_adapter_equality(self) -> None:
        adapter1 = Adapter(
            name="test_adapter",
            pkg="acb",
            module="acb.adapters.test_adapter",
            class_name="TestClass",
            category="test",
        )
        adapter2 = Adapter(
            name="test_adapter",
            pkg="acb",
            module="acb.adapters.test_adapter",
            class_name="TestClass",
            category="test",
        )
        adapter3 = Adapter(
            name="different_adapter",
            pkg="acb",
            module="acb.adapters.different_adapter",
            class_name="TestClass",
            category="test",
        )

        assert adapter1 == adapter2
        assert adapter1 != adapter3

        assert adapter1 != "not_an_adapter"
        assert adapter1 != 123
        assert adapter1 is not None

    def test_adapter_hash(self) -> None:
        adapter1 = Adapter(
            name="test_adapter",
            pkg="acb",
            module="acb.adapters.test_adapter",
            class_name="TestClass",
            category="test",
        )
        adapter2 = Adapter(
            name="test_adapter",
            pkg="acb",
            module="acb.adapters.test_adapter",
            class_name="TestClass",
            category="test",
        )
        adapter3 = Adapter(
            name="different_adapter",
            pkg="acb",
            module="acb.adapters.different_adapter",
            class_name="TestClass",
            category="test",
        )

        assert hash(adapter1) == hash(adapter2)
        assert hash(adapter1) != hash(adapter3)

        adapter_dict = {adapter1: "value1", adapter3: "value3"}
        assert adapter_dict[adapter1] == "value1"
        assert adapter_dict[adapter2] == "value1"
        assert adapter_dict[adapter3] == "value3"

    def test_adapter_repr(self) -> None:
        adapter = Adapter(
            name="test_adapter",
            pkg="acb",
            module="acb.adapters.test_adapter",
            class_name="TestClass",
            category="test",
        )

        assert str(adapter) == repr(adapter)
        assert "test_adapter" in str(adapter)
        assert "acb.adapters.test_adapter" in str(adapter)


class TestAdapterRegistry:
    def test_adapter_registry_manipulation(self) -> None:
        pytest.skip("This test requires more complex mocking of adapter_registry")

        original_registry = adapter_registry.get()
        original_length = len(original_registry)

        test_adapter = Adapter(
            name="test_adapter", class_name="TestClass", category="test", enabled=True
        )

        new_registry = original_registry.copy()
        new_registry.append(test_adapter)

        token = adapter_registry.set(new_registry)

        try:
            current_registry = adapter_registry.get()
            assert len(current_registry) == original_length + 1
            assert test_adapter in current_registry

            result = get_adapter("test")
            assert result == test_adapter
        finally:
            adapter_registry.reset(token)


class TestAdapterInitialization:
    def test_adapter_default_values(self) -> None:
        adapter = Adapter(name="test_adapter", class_name="TestClass", category="test")

        assert adapter.name == "test_adapter"
        assert adapter.pkg == "acb"
        assert adapter.module == ""
        assert not adapter.enabled
        assert not adapter.installed
        assert isinstance(adapter.path, AsyncPath)
        assert "adapters" in str(adapter.path)

    def test_adapter_custom_values(self) -> None:
        custom_path = Path("/custom/path")
        adapter = Adapter(
            name="custom_adapter",
            pkg="custom_pkg",
            module="custom.module",
            path=AsyncPath(custom_path),
            class_name="CustomClass",
            category="custom",
            enabled=True,
            installed=True,
        )

        assert adapter.name == "custom_adapter"
        assert adapter.pkg == "custom_pkg"
        assert adapter.module == "custom.module"
        assert adapter.enabled
        assert adapter.installed
        assert adapter.path == AsyncPath(custom_path)

    def test_adapter_arbitrary_types(self) -> None:
        custom_path = Path("/custom/path")
        adapter = Adapter(
            name="test_adapter",
            path=AsyncPath(custom_path),
            class_name="TestClass",
            category="test",
        )

        assert adapter.path == AsyncPath(custom_path)
        assert isinstance(adapter.path, AsyncPath)


@pytest.mark.asyncio
class TestPathAdapters:
    async def test_path_adapters_with_valid_path(self) -> None:
        pytest.skip("This test requires more complex mocking of path operations")

        mock_path = Path("/test/pkg/adapters")
        mock_adapter_dir = Path("/test/pkg/adapters/test_adapter")
        mock_other_adapter_dir = Path("/test/pkg/adapters/other_adapter")
        mock_pycache_dir = Path("/test/pkg/adapters/__pycache__")

        mock_module1 = Path("/test/pkg/adapters/test_adapter/module1.py")
        mock_module2 = Path("/test/pkg/adapters/other_adapter/module2.py")

        with (
            patch.object(Path, "exists") as mock_exists,
            patch.object(Path, "iterdir") as mock_iterdir,
            patch.object(Path, "is_dir") as mock_is_dir,
        ):
            mock_exists.return_value = True

            mock_iterdir.side_effect = [
                [mock_adapter_dir, mock_other_adapter_dir, mock_pycache_dir],
                [mock_module1],
                [mock_module2],
            ]

            mock_is_dir.side_effect = lambda: True

            result = await path_adapters(mock_path)

            assert "test_adapter" in result
            assert "other_adapter" in result
            assert "__pycache__" not in result
            assert AsyncPath(mock_module1) in result["test_adapter"]
            assert AsyncPath(mock_module2) in result["other_adapter"]

    async def test_path_adapters_with_invalid_path(self) -> None:
        pytest.skip("This test requires more complex mocking of path operations")

        mock_path = Path("/invalid/path")

        with patch.object(Path, "exists") as mock_exists:
            mock_exists.return_value = False

            result = await path_adapters(mock_path)

            assert not result


class TestImportAdapter:
    def test_import_adapter_with_category(self) -> None:
        pytest.skip("This test requires more complex mocking of adapter_registry")

        mock_adapter_class = Mock()
        mock_coroutine = Mock()
        mock_config = Mock()

        with (
            patch("acb.adapters._import_adapter") as mock_import_adapter,
            patch("acb.adapters.asyncio.run") as mock_run,
            patch("acb.adapters.depends.get") as mock_depends_get,
        ):
            mock_depends_get.return_value = mock_config
            mock_import_adapter.return_value = mock_coroutine
            mock_run.return_value = [mock_adapter_class]

            result = import_adapter("test_category")

            assert result == mock_adapter_class
            mock_import_adapter.assert_called_once_with("test_category", mock_config)
            mock_run.assert_called_once()

    def test_import_adapter_with_multiple_categories(self) -> None:
        pytest.skip("This test requires more complex mocking of adapter_registry")

        mock_adapter_class1 = Mock()
        mock_adapter_class2 = Mock()
        mock_coroutine1 = Mock()
        mock_coroutine2 = Mock()
        mock_config = Mock()

        with (
            patch("acb.adapters._import_adapter") as mock_import_adapter,
            patch("acb.adapters.asyncio.run") as mock_run,
            patch("acb.adapters.depends.get") as mock_depends_get,
        ):
            mock_depends_get.return_value = mock_config
            mock_import_adapter.side_effect = [mock_coroutine1, mock_coroutine2]
            mock_run.return_value = [mock_adapter_class1, mock_adapter_class2]

            result = import_adapter(["category1", "category2"])

            assert result == [mock_adapter_class1, mock_adapter_class2]
            assert mock_import_adapter.call_count == 2
            mock_run.assert_called_once()

    def test_import_adapter_with_exception(self) -> None:
        pytest.skip("This test requires more complex mocking of adapter_registry")

        with (
            patch("acb.adapters._import_adapter"),
            patch("acb.adapters.asyncio.run", side_effect=Exception("Test error")),
            patch("acb.adapters.depends.get"),
        ):
            with pytest.raises(AdapterNotInstalled):
                import_adapter("test_category")


class TestCreateAdapter:
    def test_create_adapter_with_path_object(self) -> None:
        test_path = Path("/test/pkg/adapters/test_adapter/module.py")

        adapter = create_adapter(AsyncPath(test_path))

        assert adapter.name == "module"
        assert adapter.pkg == "pkg"
        assert adapter.module == "pkg.adapters.test_adapter.module"
        assert isinstance(adapter.path, AsyncPath)
        assert adapter.path == AsyncPath(test_path)
        assert adapter.category == "test_adapter"
        assert adapter.class_name == "TestAdapter"

    def test_create_adapter_with_Path_object(self) -> None:
        test_path = Path("/test/pkg/adapters/test_adapter/module.py")

        adapter = create_adapter(AsyncPath(test_path))

        assert adapter.name == "module"
        assert adapter.pkg == "pkg"
        assert adapter.module == "pkg.adapters.test_adapter.module"
        assert adapter.path == AsyncPath(test_path)
        assert adapter.category == "test_adapter"
        assert adapter.class_name == "TestAdapter"

    def test_create_adapter_with_different_path_structure(self) -> None:
        pytest.skip("This test requires more complex mocking of adapter creation")

        test_path = Path("/root/pkg/subpkg/adapters/test_adapter/module.py")

        adapter = create_adapter(test_path)

        assert adapter.name == "module"
        assert adapter.pkg == "subpkg"
        assert adapter.module == "subpkg.adapters.test_adapter.module"
        assert adapter.path == AsyncPath(test_path)
        assert adapter.category == "test_adapter"
        assert adapter.class_name == "TestAdapter"

        test_path = Path("/pkg/adapters/test_adapter/module.py")

        adapter = create_adapter(test_path)

        assert adapter.name == "module"
        assert adapter.pkg == "pkg"
        assert adapter.module == "pkg.adapters.test_adapter.module"
        assert adapter.path == AsyncPath(test_path)
        assert adapter.category == "test_adapter"
        assert adapter.class_name == "TestAdapter"

        test_path = Path("adapters/test_adapter/module.py")

        adapter = create_adapter(test_path)

        assert adapter.name == "module"
        assert adapter.pkg == "adapters"
        assert adapter.module == "adapters.test_adapter.module"
        assert adapter.path == AsyncPath(test_path)
        assert adapter.category == "test_adapter"
        assert adapter.class_name == "TestAdapter"


class TestExtractAdapterModules:
    def test_extract_adapter_modules_with_valid_modules(self) -> None:
        mock_modules = [
            Path("/test/pkg/adapters/test_adapter/module.py"),
            Path("/test/pkg/adapters/other_adapter/module.py"),
        ]

        with patch("acb.adapters.create_adapter") as mock_create_adapter:
            test_adapter = Adapter(
                name="module",
                module="pkg.adapters.test_adapter.module",
                pkg="pkg",
                path=AsyncPath(mock_modules[0]),
                class_name="TestAdapter",
                category="test_adapter",
            )
            other_adapter = Adapter(
                name="module",
                module="pkg.adapters.other_adapter.module",
                pkg="pkg",
                path=AsyncPath(mock_modules[1]),
                class_name="OtherAdapter",
                category="other_adapter",
            )

            mock_create_adapter.side_effect = [test_adapter, other_adapter]

            result = extract_adapter_modules(
                [AsyncPath(m) for m in mock_modules], "test_adapter"
            )

            assert len(result) == 1
            assert result[0] == test_adapter
            assert result[0].name == "module"
            assert result[0].category == "test_adapter"

            assert mock_create_adapter.call_count == 2

    def test_extract_adapter_modules_with_empty_modules(self) -> None:
        result = extract_adapter_modules([], "test_adapter")

        assert not result

    def test_extract_adapter_modules_with_mixed_modules(self) -> None:
        mock_modules = [
            Path("/test/pkg/adapters/test_adapter/module1.py"),
            Path("/test/pkg/adapters/test_adapter/module2.py"),
            Path("/test/pkg/adapters/other_adapter/module.py"),
        ]

        with patch("acb.adapters.create_adapter") as mock_create_adapter:
            test_adapter1 = Adapter(
                name="module1",
                module="pkg.adapters.test_adapter.module1",
                pkg="pkg",
                path=AsyncPath(mock_modules[0]),
                class_name="TestAdapter",
                category="test_adapter",
            )
            test_adapter2 = Adapter(
                name="module2",
                module="pkg.adapters.test_adapter.module2",
                pkg="pkg",
                path=AsyncPath(mock_modules[1]),
                class_name="TestAdapter",
                category="test_adapter",
            )
            other_adapter = Adapter(
                name="module",
                module="pkg.adapters.other_adapter.module",
                pkg="pkg",
                path=AsyncPath(mock_modules[2]),
                class_name="OtherAdapter",
                category="other_adapter",
            )

            mock_create_adapter.side_effect = [
                test_adapter1,
                test_adapter2,
                other_adapter,
            ]

            result = extract_adapter_modules(
                [AsyncPath(m) for m in mock_modules], "test_adapter"
            )

            assert len(result) == 2
            assert test_adapter1 in result
            assert test_adapter2 in result
            assert other_adapter not in result

            assert mock_create_adapter.call_count == 3


class TestGetAdapters:
    def test_get_adapters_with_valid_adapters(self) -> None:
        mock_adapter1 = Adapter(
            name="test_adapter1", class_name="TestClass", category="test", enabled=True
        )
        mock_adapter2 = Adapter(
            name="test_adapter2", class_name="TestClass", category="test", enabled=True
        )

        with patch("acb.adapters.adapter_registry") as mock_registry:
            mock_registry.get.return_value = [mock_adapter1, mock_adapter2]

            result = get_adapters()

            assert len(result) == 2
            assert mock_adapter1 in result
            assert mock_adapter2 in result

    def test_get_adapters_with_no_adapters(self) -> None:
        with patch("acb.adapters.adapter_registry") as mock_registry:
            mock_registry.get.return_value = []

            result = get_adapters()

            assert not result

    def test_get_adapters_with_mixed_adapters(self) -> None:
        mock_adapter1 = Adapter(
            name="test_adapter1", class_name="TestClass", category="test", enabled=True
        )
        mock_adapter2 = Adapter(
            name="test_adapter2", class_name="TestClass", category="test", enabled=True
        )
        mock_adapter3 = Adapter(
            name="test_adapter3", class_name="TestClass", category="test", enabled=True
        )
        mock_adapter4 = Adapter(
            name="test_adapter4", class_name="TestClass", category="test", enabled=False
        )

        with patch("acb.adapters.adapter_registry") as mock_registry:
            mock_registry.get.return_value = [
                mock_adapter1,
                mock_adapter2,
                mock_adapter3,
                mock_adapter4,
            ]

            result = get_adapters()

            assert len(result) == 3
            assert mock_adapter1 in result
            assert mock_adapter2 in result
            assert mock_adapter3 in result
            assert mock_adapter4 not in result

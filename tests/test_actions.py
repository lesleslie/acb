from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from aiopath import AsyncPath
from acb.actions import (
    Action,
    ActionNotFound,
    ActionProtocol,
    Actions,
    action_registry,
    actions,
    create_action,
    register_actions,
)


class TestAction:
    def test_action_initialization(self) -> None:
        action = Action(name="test_action")

        assert action.name == "test_action"
        assert action.pkg == "acb"
        assert action.module == ""
        assert not action.methods
        assert isinstance(action.path, AsyncPath)

        custom_path = AsyncPath("/custom/path")
        action = Action(
            name="custom_action",
            pkg="custom_pkg",
            module="custom.module",
            methods=["method1", "method2"],
            path=custom_path,
        )

        assert action.name == "custom_action"
        assert action.pkg == "custom_pkg"
        assert action.module == "custom.module"
        assert action.methods == ["method1", "method2"]
        assert action.path == custom_path


class TestCreateAction:
    def test_create_action(self) -> None:
        test_path = Path("/test/pkg/actions/test_action")

        action = create_action(test_path)

        assert action.name == "test_action"
        assert action.pkg == "test"
        assert action.module == "pkg.actions.test_action"
        assert isinstance(action.path, AsyncPath)
        assert action.path == AsyncPath(test_path)


class TestActions:
    def test_getattr_success(self) -> None:
        test_actions = Actions()

        test_action = Action(name="existing_action")
        test_actions.__dict__["existing_action"] = test_action

        result = test_actions.existing_action

        assert result == test_action

    def test_getattr_failure(self) -> None:
        test_actions = Actions()

        with pytest.raises(ActionNotFound) as exc_info:
            test_actions.non_existent_action

        assert "Action non_existent_action not found" in str(exc_info.value)


class TestActionRegistry:
    def test_action_registry_context_var(self) -> None:
        registry = action_registry.get()

        assert isinstance(registry, list)

        original_length = len(registry)

        test_action = Action(name="test_action")
        token = action_registry.set([test_action])

        new_registry = action_registry.get()
        assert len(new_registry) == 1
        assert new_registry[0] == test_action

        action_registry.reset(token)

        reset_registry = action_registry.get()
        assert isinstance(reset_registry, list)
        assert len(reset_registry) == original_length


class TestActionProtocol:
    def test_action_protocol_compliance(self) -> None:
        assert isinstance(actions, ActionProtocol)

        class NonCompliant:
            pass

        non_compliant = NonCompliant()
        assert not isinstance(non_compliant, ActionProtocol)

        class Compliant:
            def __getattr__(self, item: str) -> Action:
                return Action(name=item)

        compliant = Compliant()
        assert isinstance(compliant, ActionProtocol)


class TestRegisterActions:
    def test_register_actions(self) -> None:
        mock_caller_file = "/test/pkg/main.py"
        mock_actions_path = Path("/test/pkg/actions")
        mock_action_dir = Path("/test/pkg/actions/test_action")

        mock_dirs = {"test_action": mock_action_dir}

        mock_module = Mock()
        mock_module.__all__ = ["test_method"]

        test_method = Mock()
        mock_module.test_method = test_method

        mock_registry_list = []

        with (
            patch("acb.actions.currentframe") as mock_frame,
            patch("acb.actions.Path") as mock_path_cls,
            patch("acb.actions.action_registry") as mock_registry,
            patch("acb.actions.import_module") as mock_import,
            patch("acb.actions.create_action") as mock_create_action,
            patch.object(Path, "exists") as mock_exists,
            patch.object(Path, "iterdir") as mock_iterdir,
            patch.object(Path, "is_dir") as mock_is_dir,
        ):
            mock_frame.return_value.f_back.f_back.f_code.co_filename = mock_caller_file
            mock_path_cls.return_value = mock_actions_path
            mock_exists.return_value = True

            mock_iterdir.return_value = [
                Path(f"{mock_actions_path}/{name}") for name in mock_dirs.keys()
            ]

            mock_is_dir.return_value = True

            mock_registry.get.return_value = mock_registry_list

            test_action = Action(
                name="test_action",
                module="pkg.actions.test_action",
                pkg="pkg",
                path=AsyncPath(mock_action_dir),
            )
            mock_create_action.return_value = test_action

            mock_import.return_value = mock_module

            result = register_actions()

            assert len(result) == 1
            assert result[0] == test_action

            mock_registry.get.assert_called_once()
            assert len(mock_registry_list) == 1
            assert mock_registry_list[0] == test_action

            mock_import.assert_called_once_with(test_action.module)

            assert hasattr(actions, "test_method")

    def test_register_actions_with_missing_module(self) -> None:
        mock_caller_file = "/test/pkg/main.py"
        mock_actions_path = Path("/test/pkg/actions")
        mock_action_dir = Path("/test/pkg/actions/test_action")

        mock_dirs = {"test_action": mock_action_dir}

        mock_spec = Mock()
        mock_loader = Mock()
        mock_spec.loader = mock_loader

        mock_module = Mock()
        mock_module.__all__ = ["test_method"]

        test_method = Mock()
        mock_module.test_method = test_method

        mock_registry_list = []

        with (
            patch("acb.actions.currentframe") as mock_frame,
            patch("acb.actions.Path") as mock_path_cls,
            patch("acb.actions.action_registry") as mock_registry,
            patch("acb.actions.import_module") as mock_import,
            patch("acb.actions.util.spec_from_file_location") as mock_spec_from_file,
            patch("acb.actions.util.module_from_spec") as mock_module_from_spec,
            patch("acb.actions.create_action") as mock_create_action,
            patch.object(Path, "exists") as mock_exists,
            patch.object(Path, "iterdir") as mock_iterdir,
            patch.object(Path, "is_dir") as mock_is_dir,
        ):
            mock_frame.return_value.f_back.f_back.f_code.co_filename = mock_caller_file
            mock_path_cls.return_value = mock_actions_path
            mock_exists.return_value = True

            mock_iterdir.return_value = [
                Path(f"{mock_actions_path}/{name}") for name in mock_dirs.keys()
            ]

            mock_is_dir.return_value = True

            mock_registry.get.return_value = mock_registry_list

            test_action = Action(
                name="test_action",
                module="pkg.actions.test_action",
                pkg="pkg",
                path=AsyncPath(mock_action_dir),
            )
            mock_create_action.return_value = test_action

            mock_import.side_effect = ModuleNotFoundError("Module not found")

            mock_spec_from_file.return_value = mock_spec

            mock_module_from_spec.return_value = mock_module

            result = register_actions()

            assert len(result) == 1
            assert result[0] == test_action

            mock_registry.get.assert_called_once()
            assert len(mock_registry_list) == 1
            assert mock_registry_list[0] == test_action

            mock_spec_from_file.assert_called_once_with(
                test_action.path.stem, test_action.path
            )
            mock_module_from_spec.assert_called_once_with(mock_spec)
            mock_loader.exec_module.assert_called_once_with(mock_module)

            assert hasattr(actions, "test_method")

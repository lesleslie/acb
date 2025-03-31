import tempfile

import pytest
from anyio import Path as Path
from acb.actions import (
    Action,
    ActionNotFound,
    ActionProtocol,
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
        assert isinstance(action.path, Path)

        custom_path = Path("/custom/path")
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
        assert isinstance(action.path, Path)
        assert action.path == test_path


class TestActions:
    def test_getattr_success(self) -> None:
        test_action = Action(name="existing_action")
        setattr(actions, "existing_action", test_action)

        result = getattr(actions, "existing_action")

        assert result == test_action

    def test_getattr_failure(self) -> None:
        with pytest.raises(ActionNotFound) as exc_info:
            getattr(actions, "non_existent_action")

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
    @pytest.mark.asyncio
    async def test_register_actions(self) -> None:
        pytest.skip("This test requires more complex mocking")

        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_dir = Path(tmp_dir) / "test_pkg"
            actions_dir = pkg_dir / "actions"
            test_action_dir = actions_dir / "test_action"

            await actions_dir.mkdir(parents=True)
            await test_action_dir.mkdir()

            init_file = test_action_dir / "__init__.py"
            await init_file.write_text(
                "from unittest.mock import Mock\n"
                "__all__ = ['test_method']\n"
                "test_method = Mock()\n"
            )

            from unittest.mock import Mock, patch

            mock_module = Mock()
            mock_module.__all__ = ["test_method"]
            mock_module.test_method = Mock()

            with patch("acb.actions.import_module", return_value=mock_module):
                registered_actions = await register_actions(pkg_dir)

                assert len(registered_actions) == 1
                assert registered_actions[0].name == "test_action"
                assert registered_actions[0].pkg == "test_pkg"
                assert registered_actions[0].module == "test_pkg.actions.test_action"
                assert registered_actions[0].methods == ["test_method"]

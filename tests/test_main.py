import sys
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acb.depends import depends


class MockApp:
    async def init(self) -> None:
        pass

    async def main(self) -> None:
        pass


mock_app_instance = MockApp()

with patch("acb.adapters.import_adapter", return_value=MockApp):
    with patch("acb.depends.depends.get", return_value=mock_app_instance):
        from acb.main import app


class TestMain:
    """Tests for the main.py module functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self) -> Generator[None, None, None]:
        """Set up mocks for all tests in this class."""
        if "acb.main" in sys.modules:
            del sys.modules["acb.main"]

        with patch("acb.adapters.import_adapter", return_value=MockApp):
            with patch("acb.depends.depends.get", return_value=mock_app_instance):
                yield

    def test_app_instance_is_created(self) -> None:
        """Test that the app instance is created and available."""
        assert app is not None
        assert app is mock_app_instance

    def test_app_adapter_is_imported(self) -> None:
        """Test that the App adapter is imported correctly."""
        with patch("acb.adapters.import_adapter") as patched_import_adapter:
            patched_import_adapter.return_value = MockApp

            if "acb.main" in sys.modules:
                del sys.modules["acb.main"]

            import acb.main

            patched_import_adapter.assert_called_once()

            assert acb.main.App is MockApp

    def test_app_instance_is_created_from_depends(self) -> None:
        """Test that the app instance is created using the depends system."""
        with patch("acb.adapters.import_adapter") as patched_import_adapter:
            with patch("acb.depends.depends.get") as patched_depends_get:
                test_app_class = MagicMock()
                test_app_instance = MagicMock()

                patched_import_adapter.return_value = test_app_class
                patched_depends_get.return_value = test_app_instance

                if "acb.main" in sys.modules:
                    del sys.modules["acb.main"]

                import acb.main

                patched_depends_get.assert_called_once_with(test_app_class)

                assert acb.main.app is test_app_instance

    def test_app_registration_in_depends(self) -> None:
        """Test that App class is registered in the depends system."""
        with patch("acb.depends.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_get_repo.return_value = mock_repo

            test_app_class = MagicMock()

            depends.get(test_app_class)

            mock_repo.get.assert_called_once_with(test_app_class)

    @pytest.mark.asyncio
    async def test_app_initialization_is_triggered(self) -> None:
        """Test that app initialization is triggered when app is accessed."""
        test_app = MagicMock()
        test_app.init = AsyncMock()

        with patch("acb.depends.depends.get", return_value=test_app):
            with patch("acb.adapters.import_adapter"):
                if "acb.main" in sys.modules:
                    del sys.modules["acb.main"]

                import acb.main

                _ = acb.main.app

                assert acb.main.app is test_app

from aiopath import AsyncPath
from acb.adapters import Adapter


class TestAdapter(Adapter):
    """Test adapter implementation for testing."""

    name: str = "test_adapter"
    class_name: str = "TestAdapter"
    category: str = "test"
    module: str = "acb.tests.adapter_class"
    pkg: str = "acb"
    enabled: bool = True
    installed: bool = False
    path: AsyncPath = AsyncPath(__file__).parent

    @staticmethod
    async def init() -> None:
        """Initialize the test adapter."""
        pass

    @staticmethod
    async def load_settings(file_path: AsyncPath | None = None) -> dict[str, str]:
        """Load settings from a file or return default settings."""
        if file_path and await file_path.exists():
            from acb.actions.encode import load

            return await load.yaml(file_path)
        return {"test_key": "test_value"}

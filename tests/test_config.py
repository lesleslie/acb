from pathlib import Path
from typing import Final

import pytest
from pydantic import BaseModel
from acb.config import (
    Config,
    DebugSettings,
    InitSettingsSource,
    PydanticSettingsSource,
    get_version,
)

TEST_CONFIG_PATH: Final[Path] = Path("tests/fixtures/config")
TEST_PASSWORD_LENGTH: Final[int] = 16


class TestSettings(BaseModel):
    test_value: str = "test"


@pytest.fixture
def config() -> Config:
    return Config()


@pytest.mark.unit
class TestConfig:
    @pytest.mark.asyncio
    async def test_config_initialization(self, config: Config) -> None:
        assert isinstance(config, Config)
        assert config.debug is not None
        assert isinstance(config.debug, DebugSettings)

    @pytest.mark.asyncio
    async def test_settings_source_init(self) -> None:
        source = InitSettingsSource(
            settings_cls=TestSettings,  # type: ignore
            init_kwargs={},
        )
        assert isinstance(source, PydanticSettingsSource)

    @pytest.mark.asyncio
    async def test_version_retrieval(self) -> None:
        version = await get_version()
        assert isinstance(version, str)
        assert "." in version

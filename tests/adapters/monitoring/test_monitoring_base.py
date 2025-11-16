"""Tests for the Monitoring Base adapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from acb.adapters.monitoring._base import MonitoringBase, MonitoringBaseSettings


class MockMonitoringBaseSettings(MonitoringBaseSettings):
    pass


class MockMonitoring(MonitoringBase):
    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()

    async def _set_user(self, user_id: str) -> None:
        pass

    async def _set_extra(self, key: str, value: str) -> None:
        pass

    async def _set_tag(self, key: str, value: str) -> None:
        pass

    async def _log_error(self, error: Exception) -> None:
        pass

    async def _log_info(self, message: str) -> None:
        pass

    async def _log_debug(self, message: str) -> None:
        pass

    async def _log_warning(self, message: str) -> None:
        pass

    async def _capture_exception(self, exception: Exception) -> None:
        pass

    async def set_user(self, user_id: str) -> None:
        await self._set_user(user_id)

    async def set_extra(self, key: str, value: str) -> None:
        await self._set_extra(key, value)

    async def set_tag(self, key: str, value: str) -> None:
        await self._set_tag(key, value)

    async def log_debug(self, message: str) -> None:
        await self._log_debug(message)

    async def log_info(self, message: str) -> None:
        await self._log_info(message)

    async def log_warning(self, message: str) -> None:
        await self._log_warning(message)

    async def log_error(self, error: Exception) -> None:
        await self._log_error(error)

    async def capture_exception(self, exception: Exception) -> None:
        await self._capture_exception(exception)


class TestMonitoringBaseSettings:
    def test_init(self) -> None:
        settings = MockMonitoringBaseSettings(traces_sample_rate=0.5)
        assert settings.traces_sample_rate == 0.5


class TestMonitoringBase:
    @pytest.fixture
    def monitoring(self) -> MockMonitoring:
        return MockMonitoring()

    @pytest.mark.asyncio
    async def test_log_error(self, monitoring: MockMonitoring) -> None:
        error = Exception("Test error")
        monitoring._log_error = AsyncMock()

        await monitoring.log_error(error)

        monitoring._log_error.assert_called_once_with(error)

    @pytest.mark.asyncio
    async def test_log_warning(self, monitoring: MockMonitoring) -> None:
        message = "Test warning"
        monitoring._log_warning = AsyncMock()

        await monitoring.log_warning(message)

        monitoring._log_warning.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_log_info(self, monitoring: MockMonitoring) -> None:
        message = "Test info"
        monitoring._log_info = AsyncMock()

        await monitoring.log_info(message)

        monitoring._log_info.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_log_debug(self, monitoring: MockMonitoring) -> None:
        message = "Test debug"
        monitoring._log_debug = AsyncMock()

        await monitoring.log_debug(message)

        monitoring._log_debug.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_capture_exception(self, monitoring: MockMonitoring) -> None:
        error = Exception("Test error")
        monitoring._capture_exception = AsyncMock()

        await monitoring.capture_exception(error)

        monitoring._capture_exception.assert_called_once_with(error)

    @pytest.mark.asyncio
    async def test_set_tag(self, monitoring: MockMonitoring) -> None:
        key = "test_key"
        value = "test_value"
        monitoring._set_tag = AsyncMock()

        await monitoring.set_tag(key, value)

        monitoring._set_tag.assert_called_once_with(key, value)

    @pytest.mark.asyncio
    async def test_set_user(self, monitoring: MockMonitoring) -> None:
        user_id = "test_user"
        monitoring._set_user = AsyncMock()

        await monitoring.set_user(user_id)

        monitoring._set_user.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_set_extra(self, monitoring: MockMonitoring) -> None:
        key = "test_key"
        value = "test_value"
        monitoring._set_extra = AsyncMock()

        await monitoring.set_extra(key, value)

        monitoring._set_extra.assert_called_once_with(key, value)

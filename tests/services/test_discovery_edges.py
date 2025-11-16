"""Additional edge tests for service discovery paths."""

from __future__ import annotations

import builtins
from unittest.mock import patch

import pytest

from acb.services.discovery import (
    ServiceNotFound,
    ServiceNotInstalled,
    create_service_metadata_template,
    enable_service,
    get_service_class,
    get_service_info,
)


@pytest.mark.unit
def test_get_service_class_wrong_name_raises() -> None:
    # Ensure category is enabled with a known service
    enable_service("performance", "performance_optimizer")
    # Request a non-existent name within a valid category
    with pytest.raises(ServiceNotFound):
        get_service_class("performance", "does_not_exist")


@pytest.mark.unit
def test_get_service_class_import_error_maps_to_not_installed() -> None:
    enable_service("performance", "performance_optimizer")
    # Patch importlib.import_module to force ImportError inside get_service_class
    with patch("importlib.import_module", side_effect=ImportError("nope")):
        with pytest.raises(ServiceNotInstalled):
            get_service_class("performance", "performance_optimizer")


@pytest.mark.unit
def test_load_service_settings_yaml_import_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force ImportError when importing yaml inside the loader
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # type: ignore[override]
        if name == "yaml":
            raise ImportError("yaml not installed")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        from acb.services.discovery import _load_service_settings, get_service_override

        _load_service_settings.cache_clear()
        settings = _load_service_settings()
        assert settings == {}
        assert get_service_override("performance") is None


@pytest.mark.unit
def test_get_service_info_with_class_metadata() -> None:
    # Create a fake service class that defines SERVICE_METADATA
    metadata = create_service_metadata_template(
        name="X", category="test", service_type="stub", author="me", description="d"
    )

    class FakeService:  # noqa: D401 - simple stub for discovery
        """Stub service for discovery info."""

        SERVICE_METADATA = metadata

    info = get_service_info(FakeService)
    assert info["class_name"] == "FakeService"
    assert info["module"] == FakeService.__module__
    assert "metadata" in info and info["metadata"]["name"] == "X"
